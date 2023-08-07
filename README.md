# discollama

`discollama` is a Discord bot powered by a local large language model backed by [Ollama](https://github.com/jmorganca/ollama) with memory backed by [Redislite](https://github.com/yahoo/redislite).

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

`discollama.py` requires an [Ollama](https://github.com/jmorganca/ollama) server. Follow the steps in the [Ollama](https://github.com/jmorganca/ollama) repository to setup Ollama.

By default, it uses `127.0.0.1:11434` but this can be configured with command line parameters `--ollama-host` and `--ollama-port`.

## Customize `discollama.py`

The default LLM is `llama2`. A custom personality can be added by changing the `SYSTEM` instruction in the Modelfile and running `ollama create`:

```
ollama create discollama -f Modelfile
```

This is set in `discollama.py` through `--ollama-model`:

```
poetry run python discollama.py --ollama-model discollama
```

Additional LLM parameters can be set in the same Modelfile through `PARAMETER` instructions:

```
FROM llama2

PARAMETER temperature 2
PARAMETER stop [INST]
PARAMETER stop [/INST]
PARAMETER stop <<SYS>>
PARAMETER stop <</SYS>>
```

If customizing the system prompt is not enough, you can configure the full prompt template:

```
FROM llama2

TEMPLATE """[INST] {{ if .First }}<<SYS>>{{ .System }}<</SYS>>

{{ end }} Tweet: 'I hate it when my phone battery dies.' [/INST] Sentiment: Negative </s><s>[INST] Tweet: 'My day has been 👍' [/INST] Sentiment: Positive </s><s> [INST] Tweet: 'This is the link to the article' [/INST] Sentiment: Neutral </s><s> [INST] Tweet: '{{ .Prompt }}' [/INST] Sentiment: """
```

This model replies with the sentiment of the the input prompt: positive, negative, or neutral.

## Activating the Bot

Discord users can interact with the bot by mentioning it in a message to start a new conversation or in a reply to a previous response to continue an ongoing conversation.
