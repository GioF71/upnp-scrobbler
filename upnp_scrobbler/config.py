import os
import constants
import dotenv
import platformdirs
from util import is_true


def load_env_file(file_name: str):
    if os.path.exists(file_name):
        dotenv.load_dotenv(dotenv_path=file_name)


def get_config(config_param: constants.ConfigParam) -> str:
    key_list: list[str] = config_param.key
    key: str
    for key in key_list:
        v: any = os.getenv(key)
        if v:
            return v
    return config_param.default_value


def is_last_fm_configured() -> bool:
    last_fm_key: str = os.getenv("LAST_FM_API_KEY")
    last_fm_secret: str = os.getenv("LAST_FM_SHARED_SECRET")
    return last_fm_key is not None and last_fm_secret is not None


def get_bool_config(env_key: str, default_value: bool) -> bool:
    cfg: str = os.getenv(env_key)
    if not cfg: return default_value
    return is_true(cfg)


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


def get_config_section_dir(config_subdir: str) -> str:
    p = os.path.join(get_app_config_dir(), config_subdir)
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)
    return p


def get_lastfm_config_dir() -> str:
    return get_config_section_dir(constants.Constants.LAST_FM_CONFIG_DIR_NAME.value)


def get_subsonic_config_dir() -> str:
    return get_config_section_dir(constants.Constants.SUBSONIC_CONFIG_DIR_NAME.value)


def get_app_config_dir() -> str:
    p = os.path.join(get_config_dir(), constants.Constants.APP_NAME.value)
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)
    return p


def get_config_dir() -> str:
    config_dir: str = os.getenv("CONFIG_DIR")
    if not config_dir:
        config_dir = platformdirs.user_config_dir()
    return config_dir
