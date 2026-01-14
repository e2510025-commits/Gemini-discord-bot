"""Discord bot entrypoint — loads cogs and initializes DB
"""
import os
import logging
import asyncio
from dotenv import load_dotenv

from discord.ext import commands

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

intents = commands.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (id: {bot.user.id})")
    logger.info("------")


async def main():
    # Dynamically load cogs
    try:
        await bot.load_extension("bot.cogs.ai_commands")
    except Exception as e:
        logger.exception("Failed to load cog: %s", e)

    # Start the bot
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
