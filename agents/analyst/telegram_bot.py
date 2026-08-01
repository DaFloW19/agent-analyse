"""Telegram long-polling entrypoint for the Analyst Phase B bot."""

from __future__ import annotations

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from agents.analyst.scheduler import start_scheduler
from agents.analyst.telegram_commands import handle_text_command
from config.settings import settings


def build_command_menu() -> list[BotCommand]:
    """Build the Telegram command menu shown by the client.

    Returns:
        list[BotCommand]: Commands registered with Telegram at bot startup.
    """

    return [
        BotCommand("start", "Start the Analyst bot"),
        BotCommand("help", "Show available commands"),
        BotCommand("health", "Check Analyst status"),
        BotCommand("report", "Show the Phase B KPI report"),
        BotCommand("weekly_report", "Show weekly KPIs and alerts"),
        BotCommand("alerts", "Check conversion drops above 50%"),
        BotCommand("optimisation_report", "Preview the weekly scale/pause/rewrite recommendations"),
        BotCommand("observe", "Observe another agent task"),
    ]


async def register_command_menu(application: Application) -> None:
    """Register the bot command menu with Telegram.

    Args:
        application: Configured Telegram application.
    """

    await application.bot.set_my_commands(build_command_menu())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming Telegram messages and reply with Analyst output.

    Args:
        update: Telegram update object.
        context: Telegram callback context.
    """

    if update.effective_chat is None or update.message is None or update.message.text is None:
        return

    allowed_chat_id = str(getattr(settings, "telegram_allowed_chat_id", "") or "")
    if allowed_chat_id and str(update.effective_chat.id) != allowed_chat_id:
        await update.message.reply_text("This chat is not allowed to use this Analyst bot.")
        return

    response = handle_text_command(update.message.text)
    await update.message.reply_text(response)


async def _on_startup(application: Application) -> None:
    """Register the command menu and start the weekly optimisation report job (B6).

    Args:
        application: Configured Telegram application.
    """

    await register_command_menu(application)

    async def send_to_operator(text: str) -> None:
        """Send text to the operator's allowed Telegram chat, if configured."""

        chat_id = getattr(settings, "telegram_allowed_chat_id", "") or ""
        if chat_id:
            await application.bot.send_message(chat_id=chat_id, text=text)

    start_scheduler(send_to_operator)


def build_application() -> Application:
    """Build the Telegram application with Phase B command handlers.

    Also starts the weekly optimisation report scheduler (B6), which sends
    every Monday at 08:00 to the allowed chat. Never called from tests, so
    test runs never start a real scheduler.

    Returns:
        Application: Configured python-telegram-bot application.

    Raises:
        RuntimeError: If `TELEGRAM_BOT_TOKEN` is missing or still set to the placeholder.
    """

    token = getattr(settings, "telegram_bot_token", "")
    if not token or token == "ton_token_ici":
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in .env before starting the Telegram bot.")

    application = Application.builder().token(token).post_init(_on_startup).build()
    application.add_handler(CommandHandler("start", handle_message))
    application.add_handler(CommandHandler("help", handle_message))
    application.add_handler(CommandHandler("health", handle_message))
    application.add_handler(CommandHandler("report", handle_message))
    application.add_handler(CommandHandler("weekly_report", handle_message))
    application.add_handler(CommandHandler("alerts", handle_message))
    application.add_handler(CommandHandler("optimisation_report", handle_message))
    application.add_handler(CommandHandler("observe", handle_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


def main() -> None:
    """Run the Analyst Telegram bot using long polling."""

    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
