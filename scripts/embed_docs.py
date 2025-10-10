import asyncio
import json
import os
import sys
import chromadb
import ollama
from dotenv import load_dotenv
from tqdm.asyncio import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.config import CHROMA_PATH, EMBEDDING_MODEL, DATA_DIR

load_dotenv()


def load_docs(filename=None):
  """Load docs from JSON file."""
  if filename is None:
    filename = os.path.join(DATA_DIR, 'ollama_docs.json')
  with open(filename, 'r', encoding='utf-8') as f:
    return json.load(f)


async def embed_batch(client, batch_docs):
  """Embed a batch of docs asynchronously."""
  tasks = [client.embeddings(model=EMBEDDING_MODEL, prompt=doc['content']) for doc in batch_docs]
  responses = await asyncio.gather(*tasks)
  return [response['embedding'] for response in responses]


async def embed_and_store(docs, batch_size=10):
  """Embed docs and store in ChromaDB asynchronously."""
  client = chromadb.PersistentClient(path=CHROMA_PATH)
  collection = client.get_or_create_collection(name='ollama_docs')
  existing_ids = set(collection.get()['ids']) if collection.count() > 0 else set()
  new_ids = set()

  ollama_client = ollama.AsyncClient()

  for i in tqdm(range(0, len(docs), batch_size), desc='Embedding batches'):
    batch = docs[i : i + batch_size]
    embeddings = await embed_batch(ollama_client, batch)

    ids = [f'chunk_{i + j}' for j in range(len(batch))]
    metadatas = [doc['metadata'] for doc in batch]
    documents = [doc['content'] for doc in batch]

    collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
    new_ids.update(ids)

  to_delete = existing_ids - new_ids
  if to_delete:
    collection.delete(ids=list(to_delete))
    print(f'Deleted {len(to_delete)} old chunks')

  print(f'Embedded and stored {len(new_ids)} chunks')


async def main():
  docs = load_docs()
  await embed_and_store(docs)


if __name__ == '__main__':
  asyncio.run(main())
