import asyncio
import discord
from .config import TYPING_TIMEOUT


async def on_ready(discord_client):
  activity = discord.Activity(name='Discollama', state='Ask me anything!', type=discord.ActivityType.custom)
  await discord_client.change_presence(activity=activity)

  app_id = discord_client.user.id
  invite_url = f'https://discord.com/api/oauth2/authorize?client_id={app_id}&permissions=2048&scope=bot'
  print(f'Invite link: {invite_url}')


async def thinking(message, discord_client, timeout=TYPING_TIMEOUT):
  try:
    await message.add_reaction('🤔')
    await asyncio.sleep(timeout)
  except Exception:
    pass
  finally:
    await message.remove_reaction('🤔', discord_client.user)
