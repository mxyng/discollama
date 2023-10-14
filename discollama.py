import os
import json
import aiohttp
import discord
import argparse
from redis import Redis

import logging

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
  logging.info(
    'Ready! Invite URL: %s',
    discord.utils.oauth_url(
      client.application_id,
      permissions=discord.Permissions(read_messages=True, send_messages=True),
      scopes=['bot'],
    ))


async def generate_response(prompt, context=[]):
  body = {
    key: value
    for key, value in {
      'model': args.ollama_model,
      'prompt': prompt,
      'context': context,
    }.items() if value
  }

  async with aiohttp.ClientSession() as session:
    async with session.post(
        f'http://{args.ollama_host}:{args.ollama_port}/api/generate',
        json=body) as r:
      async for line in r.content:
        yield json.loads(line)


async def buffered_generate_response(prompt, context=[]):
  buffer = ''
  async for part in generate_response(prompt, context):
    if part['done']:
      yield buffer, part
      break

    buffer += part['response']
    if len(buffer) >= args.buffer_size:
      yield buffer, part
      buffer = ''


def save_session(response, part):
  context = part.get('context', [])
  redis.json().set(f'ollama:{response.id}', '$', {'context': context})

  redis.expire(f'ollama:{response.id}', 60 * 60 * 24 * 7)
  logging.info('saving message=%s: len(context)=%d', response.id, len(context))


def load_session(reference):
  kwargs = {}
  if reference:
    context = redis.json().get(f'ollama:{reference.message_id}', '.context')
    kwargs['context'] = context or []

  if kwargs.get('context'):
    logging.info(
      'loading message=%s: len(context)=%d',
      reference.message_id,
      len(kwargs['context']),
    )

  return kwargs


@client.event
async def on_message(message):
  if message.author == client.user:
    return

  if client.user.id in message.raw_mentions:
    raw_content = message.content.replace(f'<@{client.user.id}>', '').strip()
    if raw_content.strip() == '':
      raw_content = 'Tell me about yourself.'

    response = None
    response_content = ''
    async with message.channel.typing():
      await message.add_reaction('🤔')

      context = []
      if reference := message.reference:
        if session := load_session(message.reference):
          context = session.get('context', [])
        else:
          reference_message = await message.channel.fetch_message(
            reference.message_id)
          reference_content = reference_message.content
          raw_content = '\n'.join([
            raw_content,
            'Use it to answer the prompt:',
            reference_content,
          ])

      async for buffer, part in buffered_generate_response(
          raw_content,
          context=context,
      ):
        response_content += buffer
        if part['done']:
          save_session(response, part)
          break

        if not response:
          response = await message.reply(response_content)
          await message.remove_reaction('🤔', client.user)
          continue

        if len(response_content) + 3 >= 2000:
          response = await response.reply(buffer)
          response_content = buffer
          continue

        await response.edit(content=response_content + '...')

    await response.edit(content=response_content)


default_ollama_host = os.getenv('OLLAMA_HOST', '127.0.0.1')
default_ollama_port = os.getenv('OLLAMA_PORT', 11434)
default_ollama_model = os.getenv('OLLAMA_MODEL', 'llama2')

parser = argparse.ArgumentParser()
parser.add_argument('--ollama-host', default=default_ollama_host)
parser.add_argument('--ollama-port', default=default_ollama_port, type=int)
parser.add_argument('--ollama-model', default=default_ollama_model, type=str)

parser.add_argument('--redis-host', default='localhost')
parser.add_argument('--redis-port', default=6379)

parser.add_argument('--buffer-size', default=32, type=int)

args = parser.parse_args()

try:
  redis = Redis(host=args.redis_host, port=args.redis_port)
  client.run(os.getenv('DISCORD_TOKEN'), root_logger=True)
except KeyboardInterrupt:
  pass

redis.close()
