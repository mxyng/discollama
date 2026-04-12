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
from ollama import Tool, WebSearchResponse, WebFetchResponse

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
  def __init__(self, ollama, discord, redis, model, enable_web_search=False):
    self.ollama = ollama
    self.discord = discord
    self.redis = redis
    self.model = model
    self.enable_web_search = enable_web_search

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

    # Get messages around
    context_parts = []
    async for msg in channel.history(limit=4, before=message):
      context_parts.append(msg.content)

    if context_parts:
      content = '\n'.join(
        [
          content,
          'Use this to answer the question if it is relevant, otherwise ignore it:',
          *context_parts,
        ]
      )

    if not context:
      context = await self.load(channel_id=channel.id)

    r = Response(message)
    task = asyncio.create_task(self.thinking(message))
    async for text in self.generate(content, context):
      task.cancel()

      await r.write(text, end='...')

    await r.write('')
    await self.save(r.channel.id, message.id, [])

  async def thinking(self, message, timeout=999):
    try:
      await message.add_reaction('🤔')
      async with message.channel.typing():
        await asyncio.sleep(timeout)
    except Exception:
      pass
    finally:
      await message.remove_reaction('🤔', self.discord.user)

  def format_web_results(self, results, query):
    output = []
    if isinstance(results, WebSearchResponse):
      output.append(f'Search results for "{query}":')
      for result in results.results:
        if result.title:
          output.append(f'- {result.title}')
        if result.url:
          output.append(f'  URL: {result.url}')
        if result.content:
          output.append(f'  {result.content}')
    elif isinstance(results, WebFetchResponse):
      output.append(f'Fetched content from "{query}":')
      if results.title:
        output.append(f'Title: {results.title}')
      if results.content:
        output.append(f'Content: {results.content}')
      if results.links:
        output.append(f'Links: {", ".join(results.links)}')
    return '\n'.join(output) if output else f'No results for "{query}"'

  async def generate(self, content, context):
    messages = [{'role': 'user', 'content': content}]
    tools = [Tool(function=Tool.Function(name='web_search', description='Search the web for current information, ALWAYS use this to find answers to questions'))] if self.enable_web_search else None

    sb = io.StringIO()

    t = datetime.now()
    response = await self.ollama.chat(model=self.model, messages=messages, tools=tools, keep_alive=-1, stream=True)

    async for part in response:
      if content := part.message.content:
        sb.write(content)

      if part.done or datetime.now() - t > timedelta(seconds=1):
        if sb.getvalue():
          yield sb.getvalue()
          t = datetime.now()
          sb.seek(0, io.SEEK_SET)
          sb.truncate()

      if tool_calls := part.message.tool_calls:
        for tool_call in tool_calls:
          func_name = tool_call.function.name
          args = tool_call.function.arguments or {}

          if func_name == 'web_search' and 'query' in args:
            result = await self.ollama.web_search(args['query'])
            formatted = self.format_web_results(result, args['query'])
            messages.append({'role': 'tool', 'content': formatted})

            async for text in self.generate(formatted, context):
              yield text
            return

          elif func_name == 'web_fetch' and 'url' in args:
            result = await self.ollama.web_fetch(args['url'])
            formatted = self.format_web_results(result, args['url'])
            messages.append({'role': 'tool', 'content': formatted})

            async for text in self.generate(formatted, context):
              yield text
            return

    # Yield any remaining content
    if remaining := sb.getvalue():
      yield remaining

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

  parser.add_argument('--ollama-model', default=os.getenv('OLLAMA_MODEL', 'qwen3.5'), type=str)

  parser.add_argument('--redis-host', default=os.getenv('REDIS_HOST', '127.0.0.1'), type=str)
  parser.add_argument('--redis-port', default=os.getenv('REDIS_PORT', 6379), type=int)

  parser.add_argument('--buffer-size', default=32, type=int)
  parser.add_argument('--web-search', action='store_true', help='Enable web search tool (requires OLLAMA_API_KEY env var)')

  args = parser.parse_args()

  web_search = args.web_search or os.getenv('WEB_SEARCH', '').lower() in ('true', '1', 'yes')

  intents = discord.Intents.default()
  intents.message_content = True

  ollama_kwargs = {}
  if api_key := os.getenv('OLLAMA_API_KEY'):
    ollama_kwargs['headers'] = {'Authorization': f'Bearer {api_key}'}

  Discollama(
    ollama.AsyncClient(**ollama_kwargs),
    discord.Client(intents=intents),
    redis.Redis(host=args.redis_host, port=args.redis_port, db=0, decode_responses=True),
    model=args.ollama_model,
    enable_web_search=web_search,
  ).run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
  main()
