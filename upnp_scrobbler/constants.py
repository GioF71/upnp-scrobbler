from enum import Enum


class Constants(Enum):
    APP_NAME = "upnp-scrobbler"
    LAST_FM = "last.fm"
    LAST_FM_SESSION_KEY = "last_fm_session_key"
    LAST_FM_CONFIG = "last_fm_config.env"


class _ConfigParamData:

    def __init__(self, key: str, default_value: any):
        self.__key: str = key
        self.__default_value: any = default_value

    @property
    def key(self) -> str:
        return self.__key

    @property
    def default_value(self) -> any:
        return self.__default_value


class ConfigParam(Enum):
    pass


DEFAULT_DURATION_THRESHOLD: int = 240
DEFAULT_DUMP_UPNP_DATA: bool = False
DEFAULT_DUMP_EVENT_KEYS: bool = False
DEFAULT_DUMP_EVENT_KEY_VALUES: bool = False
DEFAULT_ENABLE_NOW_PLAYING: bool = True

# we accept new scrobbles for the same song after (seconds) ...
DEFAULT_MINIMUM_DELTA: float = 10.0
