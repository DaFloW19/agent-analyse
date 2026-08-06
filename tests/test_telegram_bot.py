import agents.analyst.telegram_bot as telegram_bot_module
from agents.analyst.telegram_bot import build_application, build_command_menu


def test_build_command_menu_includes_observe_command():
    commands = build_command_menu()

    command_names = {command.command for command in commands}
    assert command_names == {
        "start",
        "help",
        "health",
        "report",
        "weekly_report",
        "alerts",
        "optimisation_report",
        "predictive_roas",
        "cohorts",
        "conversion_api",
        "scoring_feedback",
        "ab_tests",
        "observe",
    }


def test_build_application_registers_a_command_handler_for_every_menu_command(monkeypatch):
    """A command listed in the menu but not registered as a CommandHandler is
    silently ignored by Telegram -- this is the exact bug that shipped once
    (Phase C commands added to the menu and to telegram_commands.py, but
    never wired up here), so this test pins both lists to always agree.
    """

    monkeypatch.setattr(
        telegram_bot_module.settings, "telegram_bot_token", "fake-token-for-test", raising=False
    )

    application = build_application()

    registered_commands: set[str] = set()
    for handler in application.handlers[0]:
        registered_commands |= getattr(handler, "commands", set())

    menu_commands = {command.command for command in build_command_menu()}
    assert menu_commands <= registered_commands
