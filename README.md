# discollama

`discollama` is a Discord bot powered by a local large language model backed by [Ollama](https://github.com/ollama/ollama).

## Dependencies

- Docker and Docker Compose

## Run `discollama.py`

```
DISCORD_TOKEN=xxxxx docker compose up
```

WEB_SEARCH can be set to enable web search WEB_SEARCH=true.

> [!NOTE]
> You must setup a [Discord Bot](https://discord.com/developers/applications) and set environment variable `DISCORD_TOKEN` before `discollama.py` can access Discord.

`discollama.py` requires an [Ollama](https://github.com/ollama/ollama) server. Follow the steps in [ollama/ollama](https://github.com/ollama/ollama) repository to setup Ollama.

By default, it uses `127.0.0.1:11434` which can be overwritten with `OLLAMA_HOST`.

> Note: For use of Ollama Cloud, set `OLLAMA_HOST` to `https://ollama.com` and `OLLAMA_API_KEY` to your API key.
> Note: Deploying this on Linux requires updating network configurations and `OLLAMA_HOST`.

## Customize `discollama.py`

The default LLM is `qwen3.5`. A custom personality can be added by changing the `SYSTEM` instruction in the Modelfile and running `ollama create`:

```
ollama create mymodel -f Modelfile
```

This can be changed in `compose.yaml`:

```
environment:
  - OLLAMA_MODEL=mymodel
```

See [ollama/ollama](https://github.com/ollama/ollama/blob/main/docs/modelfile.mdx) for more details.

## Activating the Bot

Discord users can interact with the bot by mentioning it in a message to start a new conversation or in a reply to a previous response to continue an ongoing conversation.
