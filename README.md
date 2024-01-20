
# discollama

`discollama` is an innovative Discord bot that leverages a local large language model to interact in Discord channels. It's powered by [Ollama](https://github.com/jmorganca/ollama), making it a powerful and customizable tool for Discord server administrators and enthusiasts.

## Dependencies

Before you begin, ensure you have the following installed:
- Docker
- Docker Compose

### Installing Docker

#### Linux
- Install Docker using your package manager or follow the instructions here: [Install Docker on Linux](https://docs.docker.com/engine/install/).

#### Mac
- Download and install Docker Desktop for Mac from [Docker Hub](https://hub.docker.com/editions/community/docker-ce-desktop-mac/).

#### Windows
- Download and install Docker Desktop for Windows from [Docker Hub](https://hub.docker.com/editions/community/docker-ce-desktop-windows/).

### Installing Docker Compose
- Docker Compose is included in Docker Desktop for Mac and Windows.
- For Linux, follow the instructions here: [Install Docker Compose on Linux](https://docs.docker.com/compose/install/).

## Setting Up a Discord Bot

To use `discollama`, you'll need a Discord bot token. Follow these steps to set one up:

1. **Create a Discord account**: If you don’t already have a Discord account, create one at [Discord's registration page](https://discord.com/register).
2. **Create a new application**: Visit the [Discord Developer Portal](https://discord.com/developers/applications), click on "New Application", and give it a name.
3. **Create a Bot User**: In your application, navigate to the “Bot” tab and click "Add Bot".
4. **Get your Bot Token**: Under the bot section, find the “Token” and click "Copy". This is your `DISCORD_TOKEN` which you'll use later. Keep this token private!
5. **Invite Bot to Server**: In the “OAuth2” tab, under “Scopes”, select “bot”. Choose the permissions your bot needs and use the generated URL to invite your bot to your Discord server.

## Installation and Running `discollama`

1. **Clone the Repository**: First, clone the `discollama` repository from GitHub.
   ```
   git clone https://github.com/mxyng/discollama.git
   cd discollama
   ```

2. **Setup Environment Variables**: Create a `.env` file in the root directory and add your Discord token.
   ```
   echo DISCORD_TOKEN=your_discord_bot_token > .env
   ```

3. **Running the Bot**: Use Docker Compose to build and run the bot.
   ```
   docker compose up
   ```
   > This command builds the Docker image and starts the `discollama` bot in a Docker container.

> **Note**: Ensure your `OLLAMA_HOST` is set correctly in the `compose.yaml` if you are deploying on a network other than localhost.

## Activating the Bot

Once `discollama` is running, you can interact with it in your Discord server. Just mention the bot in a message to start a new conversation, or reply to its messages to continue an ongoing conversation.

## Troubleshooting

[Common issues and solutions]

## Contributing

[Information on how others can contribute to the project]

## Contact

[Provide contact information or methods for support and feedback]

## License

`discollama` is open-source software licensed under the MIT License. [See the full license here](./LICENSE).
