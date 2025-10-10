import asyncio
import datetime
import discord
import json
import logging
import re
import uuid

from .config import load_prompt, RESPONSE_TITLE, BOT_THREAD_NAME
from .response import Response
from .utils import get_embedding, get_chroma_collection
from .handlers import thinking, on_ready


class Discollama:
  def __init__(self, ollama_client, discord_client, model):
    self.ollama = ollama_client
    self.discord = discord_client
    self.model = model

    self.collection = get_chroma_collection()
    self.history_collection = get_chroma_collection(name='history')

    # Set up logging
    self.logger = logging.getLogger('discollama')
    self.logger.setLevel(logging.INFO)
    handler = logging.FileHandler('bot.log', encoding='utf-8')
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    self.logger.addHandler(handler)

    # register event handlers
    self.discord.event(self.on_ready)
    self.discord.event(self.on_message)

  async def on_ready(self):
    await on_ready(self.discord)

  async def on_message(self, message):
    if self.discord.user == message.author:
      # don't respond to ourselves
      return

    is_mentioned = self.discord.user.mentioned_in(message)
    is_in_bot_thread = message.channel.type == discord.ChannelType.public_thread and message.channel.name == BOT_THREAD_NAME and message.author != self.discord.user
    if not (is_mentioned or is_in_bot_thread):
      # don't respond to messages that don't mention us or are not in our threads
      return

    content = message.content.replace(f'<@{self.discord.user.id}>', '').strip()
    if not content:
      content = 'Hi!'

    self.logger.info(f'User input: {content}')

    # Store user message
    self.history_collection.add(ids=[str(uuid.uuid4())], documents=[content], metadatas=[{'role': 'user', 'channel_id': str(message.channel.id), 'timestamp': datetime.datetime.now().isoformat()}])

    # Fetch history from Chroma
    channel_ids = [str(message.channel.id)]
    if message.channel.type == discord.ChannelType.public_thread:
      channel_ids.append(str(message.channel.parent.id))

    all_items = []
    for ch_id in channel_ids:
      results = self.history_collection.get(where={'channel_id': ch_id}, limit=20)
      if results['documents']:
        items = list(zip(results['documents'], results['metadatas'], strict=True))
        all_items.extend(items)

    all_items.sort(key=lambda x: x[1]['timestamp'])
    history = []
    for doc, meta in all_items[:-1]:  # exclude the current user message
      history.append({'role': meta['role'], 'content': doc})

    # If already in a thread, force thread response
    if message.channel.type == discord.ChannelType.public_thread:
      create_thread = True
      thread_name = None
    else:
      create_thread = False
      thread_name = None

    system_prompt = load_prompt('system')

    response = Response(message, create_thread, thread_name)
    task = asyncio.create_task(thinking(message, self.discord))
    async with message.channel.typing():
      create_thread, thread_name, full_response = await self.generate(content, system_prompt, history)
    response.create_thread = create_thread
    response.thread_name = thread_name
    if create_thread:
      await response.send_embed(RESPONSE_TITLE, full_response)
    else:
      # For inline, chunk if needed
      if len(full_response) <= 2000:
        await response.send(full_response)
      else:
        buffer = full_response
        while buffer:
          # Find last sentence end before 2000
          matches = list(re.finditer(r'[.!?]\s', buffer[:2000]))
          if matches:
            last_match = matches[-1]
            pos = last_match.end()
            await response.send(buffer[:pos].strip())
            buffer = buffer[pos:]
          else:
            await response.send(buffer[:2000].strip())
            buffer = buffer[2000:]

    # Store assistant response
    self.history_collection.add(ids=[str(uuid.uuid4())], documents=[full_response], metadatas=[{'role': 'assistant', 'channel_id': str(message.channel.id), 'timestamp': datetime.datetime.now().isoformat()}])

    self.logger.info(f'Assistant output: {full_response}')

    task.cancel()

  async def _call_llm_with_retry(self, messages, tools):
    """Call Ollama chat with retry logic."""
    max_retries = 3
    for attempt in range(max_retries):
      try:
        async for part in await self.ollama.chat(model=self.model, messages=messages, tools=tools, stream=True, options={'temperature': 0.1}):
          yield part
        return
      except Exception as e:
        self.logger.warning(f'LLM call failed (attempt {attempt + 1}/{max_retries}): {e}')
        if attempt < max_retries - 1:
          await asyncio.sleep(2**attempt)  # Exponential backoff
        else:
          raise

  async def _handle_search_docs(self, query):
    """Handle search_docs tool call."""
    self.logger.info(f'Search query: {query}')
    query_embedding = await get_embedding(self.ollama, query)
    results = self.collection.query(query_embeddings=[query_embedding], n_results=5)
    docs = []
    if results['documents']:
      for i, doc_text in enumerate(results['documents'][0]):
        metadatas = results['metadatas'][0][i]
        url = metadatas['url']
        docs.append({'text': doc_text, 'url': url})
    # Deduplicate by URL, keep first occurrence
    unique_docs = {}
    for doc in docs:
      if doc['url'] not in unique_docs:
        unique_docs[doc['url']] = doc
    docs = list(unique_docs.values())
    self.logger.info(f'Retrieved docs: {[doc["url"] for doc in docs]}')
    return json.dumps(docs)

  async def _handle_respond_tool(self, tool_call):
    """Handle respond_inline or respond_in_thread."""
    name = tool_call['function']['name']
    if name == 'respond_inline':
      content_resp = tool_call['function']['arguments']['content']
      return False, None, content_resp.replace('—', '-')
    elif name == 'respond_in_thread':
      thread_name = tool_call['function']['arguments']['thread_name']
      content_resp = tool_call['function']['arguments']['content']
      return True, thread_name, content_resp.replace('—', '-')

  async def generate(self, content, system_prompt, history):
    messages = [{'role': 'system', 'content': system_prompt}] + history + [{'role': 'user', 'content': content}]

    tools = [
      {'type': 'function', 'function': {'name': 'search_docs', 'description': 'Search for relevant documentation about Ollama to answer questions accurately.', 'parameters': {'type': 'object', 'properties': {'query': {'type': 'string', 'description': 'The search query for finding documentation.'}}, 'required': ['query']}}},
      {'type': 'function', 'function': {'name': 'respond_inline', 'description': 'Respond inline in the channel for casual, simple, or short queries.', 'parameters': {'type': 'object', 'properties': {'content': {'type': 'string', 'description': 'The full response content.'}}, 'required': ['content']}}},
      {'type': 'function', 'function': {'name': 'respond_in_thread', 'description': 'Create a thread and respond there for technical, detailed, or complex queries.', 'parameters': {'type': 'object', 'properties': {'thread_name': {'type': 'string', 'description': 'Name for the thread.'}, 'content': {'type': 'string', 'description': 'The full response content.'}}, 'required': ['thread_name', 'content']}}},
    ]

    full_response = ''
    while True:
      tool_calls = []
      async for part in self._call_llm_with_retry(messages, tools):
        if part['message'].get('tool_calls'):
          tool_calls.extend(part['message']['tool_calls'])
        if part['message'].get('content'):
          full_response += part['message']['content']

      if tool_calls:
        self.logger.info(f'Tool calls: {tool_calls}')
        respond_tool = None
        for tool_call in tool_calls:
          name = tool_call['function']['name']
          if name == 'search_docs':
            docs_text = await self._handle_search_docs(tool_call['function']['arguments']['query'])
            messages.append({'role': 'assistant', 'content': '', 'tool_calls': [tool_call]})
            messages.append({'role': 'tool', 'content': docs_text})
          elif name in ['respond_inline', 'respond_in_thread']:
            respond_tool = tool_call
            break
        if respond_tool:
          return await self._handle_respond_tool(respond_tool)
      else:
        break
    # If no respond tool called, default to inline
    return False, None, full_response.replace('—', '-')

  def run(self, token):
    self.discord.run(token)
