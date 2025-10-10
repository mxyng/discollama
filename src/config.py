import os


def load_prompt(name):
  path = os.path.join(os.path.dirname(__file__), f'../prompts/{name}.md')
  with open(path, 'r', encoding='utf-8') as f:
    return f.read().strip()


EMBEDDING_MODEL = os.getenv('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text')
CHROMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/chroma_db'))
OLLAMA_DOCS_COLLECTION = 'ollama_docs'
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
RESPONSE_TITLE = 'Discollama Response'
RESPONSE_FOOTER = 'Powered by Ollama'
BOT_THREAD_NAME = 'Discollama Says'
TYPING_TIMEOUT = 999
