import argparse
import asyncio
import os
import discord
import subprocess
import sys

from src.bot import Discollama
import ollama


async def run_script(script_path):
  """Run a script asynchronously with error handling."""
  try:
    process = await asyncio.create_subprocess_exec(sys.executable, script_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = await process.communicate()
    if process.returncode != 0:
      print(f'Error running {script_path}: {stderr.decode()}')
      raise RuntimeError(f'Script {script_path} failed')
  except Exception as e:
    print(f'Failed to run {script_path}: {e}')
    raise


async def update():
  print('Starting update process...')
  try:
    print('Step 1/3: Fetching docs...')
    await run_script('scripts/fetch_docs.py')
    print('Step 2/3: Processing docs...')
    await run_script('scripts/process_local_docs.py')
    print('Step 3/3: Embedding docs...')
    await run_script('scripts/embed_docs.py')
    print('Update complete!')
  except Exception as e:
    print(f'Update failed: {e}')
    raise


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--ollama-model', default=os.getenv('OLLAMA_MODEL', 'gpt-oss:20b-cloud'), type=str)
  parser.add_argument('--update', action='store_true', help='Update docs and embeddings')

  args = parser.parse_args()

  if args.update:
    asyncio.run(update())
    return

  try:
    token = os.environ['DISCORD_TOKEN']
  except KeyError:
    print('Error: DISCORD_TOKEN environment variable not set')
    return

  intents = discord.Intents.default()
  intents.message_content = True

  try:
    Discollama(
      ollama.AsyncClient(),
      discord.Client(intents=intents),
      model=args.ollama_model,
    ).run(token)
  except Exception as e:
    print(f'Failed to start bot: {e}')


if __name__ == '__main__':
  main()
