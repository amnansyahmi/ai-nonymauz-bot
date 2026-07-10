"""The command menu shown in Telegram's UI, registered on startup.

Keeps the BotFather command list in code so it's version-controlled and set
automatically via set_my_commands — no manual /setcommands step needed.
"""

from __future__ import annotations

from telegram import BotCommand

BOT_COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("help", "View available commands"),
    BotCommand("about", "About AI Nonymauz"),
    BotCommand("reset", "Reset the conversation"),
    BotCommand("jobs", "Search for job vacancies now"),
    BotCommand("watchjob", "Save a job search to check later"),
    BotCommand("myjobs", "List your saved job watches"),
    BotCommand("unwatchjob", "Remove a saved job watch"),
    BotCommand("image", "Generate an image from a description"),
    BotCommand("weather", "Get the current weather"),
]
