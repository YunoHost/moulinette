"""Moulinette global configuration core."""

from os import environ


def init_moulinette_env():
    return {
        "DATA_DIR": environ.get("MOULINETTE_DATA_DIR", "/usr/share/moulinette"),
        "LIB_DIR": environ.get("MOULINETTE_LIB_DIR", "/usr/lib/moulinette"),
        "LOCALES_DIR": environ.get(
            "MOULINETTE_LOCALES_DIR", "/usr/share/moulinette/locale"
        ),
        "CACHE_DIR": environ.get("MOULINETTE_CACHE_DIR", "/var/cache/moulinette"),
    }
