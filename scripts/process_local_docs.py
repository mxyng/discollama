import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.config import DATA_DIR
from src.utils import hierarchical_chunk


def recursive_split(text, separators, chunk_size=1000, overlap=200):
  if not separators:
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]

  separator = separators[0]
  parts = text.split(separator)
  chunks = []
  current_chunk = ''

  for part in parts:
    if len(current_chunk) + len(part) + len(separator) > chunk_size:
      if current_chunk:
        chunks.append(current_chunk.strip())
        current_chunk = part + separator
      else:
        chunks.append(part[:chunk_size])
        current_chunk = part[chunk_size:] + separator
    else:
      current_chunk += part + separator

  if current_chunk:
    chunks.append(current_chunk.strip())

  # Recurse on smaller separators if needed
  final_chunks = []
  for chunk in chunks:
    if len(chunk) > chunk_size:
      final_chunks.extend(recursive_split(chunk, separators[1:], chunk_size, overlap))
    else:
      final_chunks.append(chunk)

  return final_chunks


def chunk_markdown(content, url, title):
  chunks = hierarchical_chunk(content, doc_title=title, chunk_size=1000, overlap=200)

  chunked_docs = []
  for i, chunk in enumerate(chunks):
    # Extract section from prefix
    lines = chunk.split('\n')
    section = title
    if len(lines) > 1 and lines[0].startswith('Document:') and lines[1].startswith('Section:'):
      section_part = lines[1].split(': ', 1)
      if len(section_part) > 1:
        section = section_part[1]
    else:
      # Fallback to finding # header
      for line in lines[:5]:
        if line.startswith('#'):
          section = line.lstrip('#').strip()
          break

    metadata = {'url': url, 'title': title, 'section': section, 'chunk_index': i}
    chunked_docs.append({'content': chunk, 'metadata': metadata})

  return chunked_docs


def process_docs():
  with open(os.path.join(DATA_DIR, 'ollama_docs.json'), 'r', encoding='utf-8') as f:
    docs = json.load(f)

  # Check if already chunked (has 'metadata' key)
  if docs and 'metadata' in docs[0]:
    print('Docs are already chunked, skipping processing.')
    return docs

  chunked_docs = []
  for doc in docs:
    print(f'Processing {doc["title"]}')
    chunks = chunk_markdown(doc['content'], doc['url'], doc['title'])
    chunked_docs.extend(chunks)
    print(f'Created {len(chunks)} chunks for {doc["title"]}')

  return chunked_docs


if __name__ == '__main__':
  docs = process_docs()
  with open(os.path.join(DATA_DIR, 'ollama_docs.json'), 'w', encoding='utf-8') as f:
    json.dump(docs, f, ensure_ascii=False, indent=2)
  print(f'Saved {len(docs)} chunks to ollama_docs.json')
