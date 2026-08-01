from agents.analyst.telegram_bot import build_command_menu


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
        "observe",
    }
