import discord
import os
from discord.ext import commands, tasks

client = commands.Bot(command_prefix="!")
token = os.getenv("DISCORD_BOT_TOKEN")


@tasks.loop(minutes=1)
async def task(self):
    if int(datetime.now().minute) % 2 == 0:
        await ctx.send(f"The minute is now even.")


@client.event
async def on_ready():
    await client.change_presence(status = discord.Status.idle, activity=discord.Game("Listening to !help"))
    print("I am online")

@client.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong with {str(round(client.latency, 2))}")

@client.command(name="whoami")
async def whoami(ctx):
    await ctx.send(f"You are {ctx.message.author.name}")

@client.command()
async def clear(ctx, amount=3):
    await ctx.channel.purge(limit=amount)


client.run(token)
