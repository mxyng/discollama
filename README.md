# discollama

## Dependencies

```
python3 -m pip install poetry
poetry install
```

## Run `discollama.py`

```
poetry run python discollama.py
```

_Note: You must setup a [Discord Bot](https://discord.com/developers/applications) and set environment variable `DISCORD_TOKEN` before `discollama.py` can access Discord._

`discollama.py` requires an [Ollama](https://github.com/jmorganca/ollama) server. By default, it uses `127.0.0.1:11434` but this can be configured with command line parameters `--ollama-host` and `--ollama-port`.

The default LLM is `llama2` but this can be configured with `--ollama-model`. A custom personality can be created by changing the `SYSTEM` instruction in the Modelfile and running `ollama create discollama -f Modelfile`. It can be referenced in `discollama.py` with `--ollama-model discollama`, e.g. `poetry run python discollama.py --ollama-model discollama`.
