import os
import json
import aiohttp
import msgpack
import discord
import argparse
from redislite import Redis
from pathlib import Path

import logging
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    logging.info('ready')


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


def save_session(response, chunk):
    context = msgpack.packb(chunk['context'])
    redis.hset(f'ollama:{response.id}', 'context', context)

    redis.expire(f'ollama:{response.id}', 60 * 60 * 24 * 7)
    logging.info('saving message=%s: len(context)=%d', response.id, len(chunk['context']))

def load_session(reference):
    kwargs = {}
    if reference:
        context = redis.hget(f'ollama:{reference.message_id}', 'context')
        kwargs['context'] = msgpack.unpackb(context) if context else []

    if kwargs.get('context'):
        logging.info(
            'loading message=%s: len(context)=%d',
            reference.message_id,
            len(kwargs['context']))

    return kwargs


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if client.user.id in message.raw_mentions:
        raw_content = message.content.replace(f'<@{client.user.id}>', '').strip()
        if raw_content.strip() == '':
            await message.channel.send('What can I do for you?', reference=message)
            return

        response = await message.channel.send(':thinking:', reference=message)

        # TODO: discord has a 2000 character limit, so we need to split the response
        buffer = ''
        response_content = ''
        async for chunk in generate_response(raw_content, **load_session(message.reference)):
            if chunk['done']:
                response_content += buffer
                save_session(response, chunk)
                break

            buffer += chunk['response']

            if len(buffer) >= args.buffer_size:
                # buffer the edit so as to not call Discord API too often
                response_content += buffer
                await response.edit(content=response_content + '...')

                buffer = ''

        await response.edit(content=response_content)


parser = argparse.ArgumentParser()
parser.add_argument('--ollama-host', default='127.0.0.1')
parser.add_argument('--ollama-port', default=11434, type=int)
parser.add_argument('--ollama-model', default='llama2', type=str)

default_redis = Path.home() / '.cache' / 'discollama' / 'brain.db'
parser.add_argument('--redis', default=default_redis, type=Path)

parser.add_argument('--buffer-size', default=32, type=int)

args = parser.parse_args()

args.redis.parent.mkdir(parents=True, exist_ok=True)

try:
    redis = Redis(args.redis)
    client.run(os.getenv('DISCORD_TOKEN'))
except KeyboardInterrupt:
    pass

redis.close()
