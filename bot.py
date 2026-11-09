"""Standalone clothing showcase Discord bot."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

import clothing_showcase

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env", override=False)

TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip()
GUILD_ID = (os.getenv("DISCORD_GUILD_ID") or "").strip()
SETTINGS_FILE = APP_DIR / "showcase-settings.json"
ASSETS_DIR = APP_DIR / "assets"
LOG = logging.getLogger("resources-managament")


class ShowcaseBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        clothing_showcase.setup(self, SETTINGS_FILE, ASSETS_DIR)
        if GUILD_ID.isdigit():
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            self.tree.add_command(clothing_showcase.showcase_group, guild=guild)
            await self.tree.sync(guild=guild)
            LOG.info("Synced showcase commands to guild %s", GUILD_ID)
        else:
            self.tree.add_command(clothing_showcase.showcase_group)
            await self.tree.sync()
            LOG.warning("DISCORD_GUILD_ID is empty; commands were synced globally.")

    async def on_ready(self):
        LOG.info("Logged in as %s", self.user)


logging.basicConfig(level=logging.INFO)
bot = ShowcaseBot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    LOG.exception("Slash command failed", exc_info=error)
    message = "The showcase command failed. Check the bot host logs for details."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        LOG.warning("Could not report the command error; the interaction has expired.")


if __name__ == "__main__":
    if not TOKEN or TOKEN.startswith("PASTE_"):
        raise SystemExit("Set DISCORD_TOKEN in the standalone bot's .env file.")
    bot.run(TOKEN)
