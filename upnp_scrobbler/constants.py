from enum import Enum


class SubsonicConfigFileType(Enum):
    SERVER = "server"
    CREDENTIALS = "credentials"
    ADDITIONAL = "additional"


class Constants(Enum):
    APP_NAME = "upnp-scrobbler"
    LAST_FM_CONFIG_DIR_NAME = "last.fm"
    SUBSONIC_CONFIG_DIR_NAME = "subsonic"
    LAST_FM_SESSION_KEY = "last_fm_session_key"
    LAST_FM_CONFIG = "last_fm_config.env"
    SUBSONIC_SERVER = f"subsonic.{SubsonicConfigFileType.SERVER.value}.env"
    SUBSONIC_CREDENTIALS = f"subsonic.{SubsonicConfigFileType.CREDENTIALS.value}.env"


class _ConfigParamData:

    def __init__(self, key: list[str], default_value: any = None):
        self.__key: list[str] = key
        self.__default_value: any = default_value

    @property
    def key(self) -> list[str]:
        return self.__key

    @property
    def default_value(self) -> any:
        return self.__default_value


class ConfigParam(Enum):
    SUBSONIC_BASE_URL = _ConfigParamData(key=["SUBSONIC_BASE_URL"])
    SUBSONIC_PORT = _ConfigParamData(key=["SUBSONIC_PORT"])
    SUBSONIC_USERNAME = _ConfigParamData(key=["SUBSONIC_USERNAME", "SUBSONIC_USER"])
    SUBSONIC_PASSWORD = _ConfigParamData(key=["SUBSONIC_PASSWORD"])
    SUBSONIC_LEGACY_AUTH = _ConfigParamData(key=["SUBSONIC_LEGACY_AUTH", "SUBSONIC_LEGACYAUTH"], default_value=False)
    SUBSONIC_SERVER_PATH = _ConfigParamData(key=["SUBSONIC_SERVER_PATH"], default_value="")
    SUBSONIC_ENABLE_NOW_PLAYING = _ConfigParamData(key=["SUBSONIC_ENABLE_NOW_PLAYING"], default_value=True)
    SUBSONIC_ENABLE_SONG_MATCH = _ConfigParamData(key=["SUBSONIC_ENABLE_SONG_MATCH"], default_value=True)

    @property
    def key(self) -> list[str]:
        return self.value.key

    @property
    def default_value(self) -> any:
        return self.value.default_value


DEFAULT_DURATION_THRESHOLD: int = 240
DEFAULT_DUMP_UPNP_DATA: bool = False
DEFAULT_DUMP_EVENT_KEYS: bool = False
DEFAULT_DUMP_EVENT_KEY_VALUES: bool = False
DEFAULT_ENABLE_NOW_PLAYING: bool = True

# we accept new scrobbles for the same song after (seconds) ...
DEFAULT_MINIMUM_DELTA: float = 10.0
