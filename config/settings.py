"""Dynaconf settings loader."""

from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix=False,
    settings_files=[
        "config/settings.toml",
        "config/settings.local.toml",
        ".env",
    ],
    environments=True,
    load_dotenv=True,
)

