import io
import os
import json
import asyncio
import argparse
from datetime import datetime, timedelta

import ollama
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

    if self.r:
      await self.r.edit(content=self.sb.getvalue() + end)
      return

    if self.channel.type == discord.ChannelType.text:
      self.channel = await self.channel.create_thread(name='Discollama Says', message=self.message, auto_archive_duration=60)

    self.r = await self.channel.send(self.sb.getvalue())


class Discollama:
  def __init__(self, ollama, discord, redis):
    self.ollama = ollama
    self.discord = discord
    self.redis = redis

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
    async for part in await self.ollama.generate(model='llama2', prompt=content, context=context, stream=True):
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
    except Exception:
      self.redis.close()


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

  Discollama(
    ollama.AsyncClient(base_url=f'{args.ollama_scheme}://{args.ollama_host}:{args.ollama_port}'),
    discord.Client(intents=intents),
    redis.Redis(host=args.redis_host, port=args.redis_port, db=0, decode_responses=True),
  ).run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
  main()
