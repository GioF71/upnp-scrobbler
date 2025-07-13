import os
import constants


def get_bool_config(env_key: str, default_value: bool) -> bool:
    cfg: str = os.getenv(env_key)
    if not cfg: return default_value
    return cfg.upper() == 'Y' or cfg.upper() == 'YES'


def get_dump_upnp_data() -> bool:
    return get_bool_config(
        env_key="DUMP_UPNP_DATA",
        default_value=constants.DEFAULT_DUMP_UPNP_DATA)


def get_dump_event_keys() -> bool:
    return get_bool_config(
        env_key="DUMP_EVENT_KEYS",
        default_value=constants.DEFAULT_DUMP_EVENT_KEYS)


def get_dump_event_key_values() -> bool:
    return get_bool_config(
        env_key="DUMP_EVENT_KEY_VALUES",
        default_value=constants.DEFAULT_DUMP_EVENT_KEY_VALUES)


def get_duration_threshold() -> int:
    duration_cfg: str = os.getenv("DURATION_THRESHOLD")
    if not duration_cfg: return constants.DEFAULT_DURATION_THRESHOLD
    return int(duration_cfg)


def get_minimum_delta() -> float:
    # not currently configurable
    return constants.DEFAULT_MINIMUM_DELTA


def get_enable_now_playing() -> bool:
    return get_bool_config(
        env_key="ENABLE_NOW_PLAYING",
        default_value=constants.DEFAULT_ENABLE_NOW_PLAYING)


def get_config_dir() -> str:
    config_dir: str = os.getenv("CONFIG_DIR")
    if not config_dir:
        config_dir = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))
    return config_dir
