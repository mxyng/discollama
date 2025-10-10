import aiohttp
import asyncio
import json as json_lib
import os
import sys
import base64

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.config import DATA_DIR

from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
headers = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}


async def fetch_file(session, url, name):
  """Fetch a single file asynchronously."""
  try:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
      if response.status == 200:
        data = await response.json()
        content = base64.b64decode(data['content']).decode('utf-8')
        return name, content, data['sha']
      else:
        print(f'Failed to fetch {url}: {response.status}')
        return None
  except Exception as e:
    print(f'Error fetching {url}: {e}')
    return None


async def fetch_docs():
  docs_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')
  os.makedirs(docs_dir, exist_ok=True)
  sha_file = os.path.join(docs_dir, 'docs_sha.json')
  if os.path.exists(sha_file):
    with open(sha_file, 'r') as f:
      stored_shas = json_lib.load(f)
  else:
    stored_shas = {}
  downloaded = 0
  skipped = 0

  async with aiohttp.ClientSession(headers=headers) as session:
    api_url = 'https://api.github.com/repos/ollama/ollama/contents/docs'
    async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
      if response.status == 200:
        files = await response.json()
        print(f'Found {len(files)} files')

        # Fetch files concurrently
        tasks = []
        for file in files:
          if file['name'].endswith('.md'):
            key = f'ollama/ollama/docs/{file["name"]}'
            if stored_shas.get(key) == file['sha']:
              print(f'Skipping {file["name"]}, up to date')
              skipped += 1
              continue
            content_url = f'https://api.github.com/repos/ollama/ollama/contents/docs/{file["name"]}'
            tasks.append(fetch_file(session, content_url, file['name']))

        results = await asyncio.gather(*tasks)
        for result in results:
          if result is not None:
            name, content, sha = result
            path = os.path.join(docs_dir, name)
            with open(path, 'w', encoding='utf-8') as f:
              f.write(content)
            stored_shas[f'ollama/ollama/docs/{name}'] = sha
            print(f'Saved {name}')
            downloaded += 1

    # Fetch READMEs
    readme_repos = [('ollama/ollama-js', 'README.md'), ('ollama/ollama-python', 'README.md')]
    for repo, file in readme_repos:
      content_url = f'https://api.github.com/repos/{repo}/contents/{file}'
      key = f'{repo}/{file}'
      result = await fetch_file(session, content_url, f'{file.replace(".md", "")}_{repo.split("/")[-1]}.md')
      if result:
        name, content, sha = result
        if stored_shas.get(key) == sha:
          print(f'Skipping {file} from {repo}, up to date')
          skipped += 1
          continue
        path = os.path.join(docs_dir, name)
        with open(path, 'w', encoding='utf-8') as f:
          f.write(content)
        stored_shas[key] = sha
        print(f'Saved {name}')
        downloaded += 1

  docs = []
  for root, _, files in os.walk(docs_dir):
    for file in files:
      if file.endswith('.md'):
        path = os.path.join(root, file)
        with open(path, 'r', encoding='utf-8') as f:
          content = f.read()
        relpath = os.path.relpath(path, docs_dir).replace(os.sep, '/')
        if file.startswith('README_'):
          repo = f'ollama/{file.split("_")[1].replace(".md", "")}'
          url = f'https://github.com/{repo}/blob/main/{relpath.replace(f"README_{repo.split('/')[-1]}.md", "README.md")}'
        else:
          repo = 'ollama/ollama'
          url = f'https://github.com/{repo}/blob/main/docs/{relpath}'
        docs.append({'title': file, 'content': content, 'url': url})

  with open(os.path.join(DATA_DIR, 'ollama_docs.json'), 'w', encoding='utf-8') as f:
    json_lib.dump(docs, f, ensure_ascii=False, indent=2)
  print(f'Saved {len(docs)} docs to JSON')

  with open(sha_file, 'w') as f:
    json_lib.dump(stored_shas, f, indent=2)
  print(f'Downloaded {downloaded} files, skipped {skipped} files')


if __name__ == '__main__':
  asyncio.run(fetch_docs())
