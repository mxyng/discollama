import discord
from .config import RESPONSE_FOOTER, BOT_THREAD_NAME, RESPONSE_TITLE


class Response:
  def __init__(self, message, create_thread=False, thread_name=None):
    self.message = message
    self.channel = message.channel
    self.thread_created = False
    self.create_thread = create_thread
    self.thread_name = thread_name or BOT_THREAD_NAME

  async def send(self, content):
    if self.create_thread and not self.thread_created and self.channel.type == discord.ChannelType.text:
      self.channel = await self.channel.create_thread(name=self.thread_name, message=self.message, auto_archive_duration=60)
      self.thread_created = True
      await self.channel.send(content)
    elif self.create_thread and self.channel.type == discord.ChannelType.public_thread:
      await self.message.reply(content)
    else:
      await self.message.reply(content)

  async def send_embed(self, title, description, color=0x3498DB):
    if self.create_thread and not self.thread_created and self.channel.type == discord.ChannelType.text:
      self.channel = await self.channel.create_thread(name=self.thread_name, message=self.message, auto_archive_duration=60)
      self.thread_created = True
      embed = discord.Embed(title=RESPONSE_TITLE, description=description, color=color)
      embed.set_footer(text=RESPONSE_FOOTER)
      await self.channel.send(embed=embed)
    elif self.create_thread and self.channel.type == discord.ChannelType.public_thread:
      if len(description) > 2048:
        description = description[:2045] + '...'
      embed = discord.Embed(title=RESPONSE_TITLE, description=description, color=color)
      embed.set_footer(text=RESPONSE_FOOTER)
      await self.message.reply(embed=embed)
    else:
      if len(description) > 2048:
        description = description[:2045] + '...'
      embed = discord.Embed(title=RESPONSE_TITLE, description=description, color=color)
      embed.set_footer(text=RESPONSE_FOOTER)
      await self.message.reply(embed=embed)
