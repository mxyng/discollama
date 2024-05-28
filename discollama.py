import io
import os
import json
import asyncio
import argparse
from datetime import datetime, timedelta

import ollama
import chromadb
import discord
import redis

from logging import getLogger

# piggy back on the logger discord.py set up
logging = getLogger('discord.discollama')


class Response:
  def __init__(self, message):
    self.message = message
    self.channel = message.channel

    self.r = None
    self.sb = io.StringIO()

  async def write(self, s, end=''):
    if self.sb.seek(0, io.SEEK_END) + len(s) + len(end) > 2000:
      self.r = None
      self.sb.seek(0, io.SEEK_SET)
      self.sb.truncate()

    self.sb.write(s)

    value = self.sb.getvalue().strip()
    if not value:
      return

    if self.r:
      await self.r.edit(content=value + end)
      return

    if self.channel.type == discord.ChannelType.text:
      self.channel = await self.channel.create_thread(name='Discollama Says', message=self.message, auto_archive_duration=60)

    self.r = await self.channel.send(value)


class Discollama:
  def __init__(self, ollama, discord, redis, model, collection):
    self.ollama = ollama
    self.discord = discord
    self.redis = redis
    self.model = model
    self.collection = collection

    # register event handlers
    self.discord.event(self.on_ready)
    self.discord.event(self.on_message)

  async def on_ready(self):
    activity = discord.Activity(name='Discollama', state='Ask me anything!', type=discord.ActivityType.custom)
    await self.discord.change_presence(activity=activity)

    logging.info(
      'Ready! Invite URL: %s',
      discord.utils.oauth_url(
        self.discord.application_id,
        permissions=discord.Permissions(
          read_messages=True,
          send_messages=True,
          create_public_threads=True,
        ),
        scopes=['bot'],
      ),
    )

  async def on_message(self, message):
    if self.discord.user == message.author:
      # don't respond to ourselves
      return

    if not self.discord.user.mentioned_in(message):
      # don't respond to messages that don't mention us
      return

    content = message.content.replace(f'<@{self.discord.user.id}>', '').strip()
    if not content:
      content = 'Hi!'

    channel = message.channel

    context = []
    if reference := message.reference:
      context = await self.load(message_id=reference.message_id)
      if not context:
        reference_message = await message.channel.fetch_message(reference.message_id)
        content = '\n'.join(
          [
            content,
            'Use this to answer the question if it is relevant, otherwise ignore it:',
            reference_message.content,
          ]
        )
    
    # retrieve relevant context from vector store
    knowledge = self.collection.query(
      query_texts=[content],
      n_results=2
    )
    # directly unpack the first list of documents if it exists, or use an empty list
    documents = knowledge.get('documents', [[]])[0]

    content = '\n'.join(
      [
        'Using the provided document, answer the user question to the best of your ability. You must try to use information from the provided document. Combine information in the document into a coherent answer.',
        'If there is nothing in the document relevant to the user question, say \'Hmm, I don\'t know about that, try referencing the docs.\', before providing any other information you know.',
        'Anything between the following `document` html blocks is retrieved from a knowledge bank, not part of the conversation with the user.',
        '<document>',
        '\n'.join(documents) if documents else '',
        '</document>',
        'Anything between the following `user` html blocks is part of the conversation with the user.',
        '<user>',
        content,
        '</user>',
      ]
    )

    if not context:
      context = await self.load(channel_id=channel.id)

    r = Response(message)
    task = asyncio.create_task(self.thinking(message))
    async for part in self.generate(content, context):
      task.cancel()

      await r.write(part['response'], end='...')

    await r.write('')
    await self.save(r.channel.id, message.id, part['context'])

  async def thinking(self, message, timeout=999):
    try:
      await message.add_reaction('🤔')
      async with message.channel.typing():
        await asyncio.sleep(timeout)
    except Exception:
      pass
    finally:
      await message.remove_reaction('🤔', self.discord.user)

  async def generate(self, content, context):
    sb = io.StringIO()

    t = datetime.now()
    async for part in await self.ollama.generate(model=self.model, prompt=content, context=context, keep_alive=-1, stream=True):
      sb.write(part['response'])

      if part['done'] or datetime.now() - t > timedelta(seconds=1):
        part['response'] = sb.getvalue()
        yield part
        t = datetime.now()
        sb.seek(0, io.SEEK_SET)
        sb.truncate()

  async def save(self, channel_id, message_id, ctx: list[int]):
    self.redis.set(f'discollama:channel:{channel_id}', message_id, ex=60 * 60 * 24 * 7)
    self.redis.set(f'discollama:message:{message_id}', json.dumps(ctx), ex=60 * 60 * 24 * 7)

  async def load(self, channel_id=None, message_id=None) -> list[int]:
    if channel_id:
      message_id = self.redis.get(f'discollama:channel:{channel_id}')

    ctx = self.redis.get(f'discollama:message:{message_id}')
    return json.loads(ctx) if ctx else []

  def run(self, token):
    try:
      self.discord.run(token)
    except Exception as e:
      logging.exception("An error occurred while running the bot: %s", e)
      self.redis.close()


def embed_data(collection):
  logging.info('embedding data...')
  documents = []
  ids = []
  # read all data from the data folder
  for filename in os.listdir('data'):
    if filename.endswith('.json'):
      filepath = os.path.join('data', filename)
      with open(filepath, 'r') as file:
        try:
          data = json.load(file)
          if isinstance(data, list):
            for index, item in enumerate(data):
              documents.append(item)
              file_id = f"{filename.rsplit('.', 1)[0]}-{index}"
              ids.append(file_id)
          else:
            logging.warning("The file {filename} is not a JSON array.")
        except json.JSONDecodeError as e:
          logging.exception(f"Error decoding JSON from file {filename}: {e}")
        except Exception as e:
          logging.exception(f"An error occurred while processing file {filename}: {e}")
  # store the data in chroma for look-up
  collection.add(
    documents=documents,
    ids=ids,
  )


def main():
  parser = argparse.ArgumentParser()

  parser.add_argument('--ollama-scheme', default=os.getenv('OLLAMA_SCHEME', 'http'), choices=['http', 'https'])
  parser.add_argument('--ollama-host', default=os.getenv('OLLAMA_HOST', '127.0.0.1'), type=str)
  parser.add_argument('--ollama-port', default=os.getenv('OLLAMA_PORT', 11434), type=int)
  parser.add_argument('--ollama-model', default=os.getenv('OLLAMA_MODEL', 'llama2'), type=str)

  parser.add_argument('--redis-host', default=os.getenv('REDIS_HOST', '127.0.0.1'), type=str)
  parser.add_argument('--redis-port', default=os.getenv('REDIS_PORT', 6379), type=int)

  parser.add_argument('--buffer-size', default=32, type=int)

  args = parser.parse_args()

  intents = discord.Intents.default()
  intents.message_content = True

  chroma = chromadb.Client()
  collection = chroma.get_or_create_collection(name='discollama')
  embed_data(collection)

  Discollama(
    ollama.AsyncClient(host=f'{args.ollama_scheme}://{args.ollama_host}:{args.ollama_port}'),
    discord.Client(intents=intents),
    redis.Redis(host=args.redis_host, port=args.redis_port, db=0, decode_responses=True),
    model=args.ollama_model,
    collection=collection,
  ).run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
  main()
