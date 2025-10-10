import re
import chromadb
from typing import List, Optional
from .config import EMBEDDING_MODEL, CHROMA_PATH, OLLAMA_DOCS_COLLECTION


async def get_embedding(ollama_client, text: str) -> List[float]:
  if not isinstance(text, str) or not text.strip():
    raise ValueError('Text must be a non-empty string')
  response = await ollama_client.embeddings(model=EMBEDDING_MODEL, prompt=text)
  return response['embedding']


def hierarchical_chunk(text: str, doc_title: str = '', section_separators: Optional[List[str]] = None, chunk_size: int = 500, overlap: int = 100) -> List[str]:
  if not isinstance(text, str):
    raise ValueError('Text must be a string')
  if not isinstance(doc_title, str):
    raise ValueError('Doc title must be a string')
  if chunk_size <= 0:
    raise ValueError('Chunk size must be positive')
  if overlap < 0 or overlap >= chunk_size:
    raise ValueError('Overlap must be non-negative and less than chunk size')

  if section_separators is None:
    section_separators = ['\n# ', '\n## ', '\n### ', '\n#### ']
  """Hierarchical chunking: split by sections, then sub-chunk."""

  # Split into sections with context
  sections = []
  current_section = ''
  current_context = []
  lines = text.split('\n')
  for line in lines:
    stripped = line.strip()
    if stripped.startswith('#'):
      level = len(stripped) - len(stripped.lstrip('#'))
      header = stripped.lstrip('#').strip()
      if current_section:
        sections.append((current_section.strip(), ' > '.join(current_context)))
      # Build context path up to this level
      current_context = current_context[: level - 1] + [header]
      current_section = line
    else:
      current_section += '\n' + line
  if current_section:
    sections.append((current_section.strip(), ' > '.join(current_context)))

  # Sub-chunk each section
  chunks = []
  for section, context in sections:
    prefix = f'Document: {doc_title}\nSection: {context}\n\n' if context else f'Document: {doc_title}\n\n'
    prefixed_section = prefix + section
    if len(prefixed_section) <= chunk_size:
      chunks.append(prefixed_section)
    else:
      # Split by sentences or length on raw section, then add prefix to each chunk
      sentences = re.split(r'(?<=[.!?])\s+', section)
      current_chunk = ''
      for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size:
          if current_chunk:
            chunks.append(prefix + current_chunk.strip())
            # Overlap: start new chunk with last part
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            current_chunk = overlap_text + ' ' + sentence
          else:
            chunks.append(prefix + sentence)
            current_chunk = sentence
        else:
          current_chunk += ' ' + sentence
      if current_chunk:
        chunks.append(prefix + current_chunk.strip())

  return chunks


def get_chroma_collection(name: str = OLLAMA_DOCS_COLLECTION):
  if not isinstance(name, str) or not name.strip():
    raise ValueError('Collection name must be a non-empty string')
  client = chromadb.PersistentClient(path=CHROMA_PATH)
  return client.get_or_create_collection(name=name)
