import os
import constants
import config
from util import is_true
from subsonic_connector.song import Song as SubsonicSong
from subsonic_connector.connector import Connector as SubsonicConnector
from subsonic_connector.response import Response as SubsonicResponse
from subsonic_configuration import SubsonicConnectorConfiguration
from subsonic_configuration import ScrobblerSubsonicConfiguration

from urllib.parse import urlparse
from urllib.parse import parse_qs


def get_subsonic_config() -> ScrobblerSubsonicConfiguration | None:
    base_url: str = config.get_config(constants.ConfigParam.SUBSONIC_BASE_URL)
    username: str = config.get_config(constants.ConfigParam.SUBSONIC_USERNAME)
    password: str = config.get_config(constants.ConfigParam.SUBSONIC_PASSWORD)
    if not (base_url and username and password):
        return None
    # good to go.
    port: str = config.get_config(constants.ConfigParam.SUBSONIC_PORT)
    server_path: str = config.get_config(constants.ConfigParam.SUBSONIC_SERVER_PATH)
    legacy_auth: bool = is_true(config.get_config(constants.ConfigParam.SUBSONIC_LEGACY_AUTH))
    return ScrobblerSubsonicConfiguration(
        base_url=base_url,
        port=int(port) if port else None,
        username=username,
        password=password,
        server_path=server_path,
        legacy_auth=legacy_auth)


def scrobble_song(song: SubsonicSong, config: ScrobblerSubsonicConfiguration):
    subsonic_config: SubsonicConnectorConfiguration = SubsonicConnectorConfiguration(cfg=config)
    cn: SubsonicConnector = SubsonicConnector(configuration=subsonic_config)
    cn.scrobble(song_id=song.getId())


def get_song_by_id(song_id: str, config: ScrobblerSubsonicConfiguration) -> SubsonicSong:
    subsonic_config: SubsonicConnectorConfiguration = SubsonicConnectorConfiguration(cfg=config)
    cn: SubsonicConnector = SubsonicConnector(configuration=subsonic_config)
    subsonic_song_res: SubsonicResponse[SubsonicSong] = None
    try:
        subsonic_song_res = cn.getSong(song_id=song_id)
    except Exception as ex:
        print(f"subsonic_scrobble cannot get song_id [{song_id}] due to [{type(ex)}] [{ex}]")
    return subsonic_song_res.getObj() if subsonic_song_res and subsonic_song_res.isOk() else None


def get_song_id(uri: str, config: ScrobblerSubsonicConfiguration) -> str | None:
    parsed_url = urlparse(uri)
    host: str = f"{parsed_url.scheme}://{parsed_url.hostname}:{parsed_url.port}"
    config_port: int = (config.port if config.port is not None else
                        (443 if config.base_url.lower().startswith("https") else 80))
    cmp_host: str = f"{config.base_url}:{config_port}"
    if host == cmp_host:
        # it's a subsonic server url
        parse_result = parse_qs(parsed_url.query)
        return parse_result["id"][0] if "id" in parse_result and len(parse_result["id"]) == 1 else None
    else:
        # is it from upmpdcli?
        # is server whitelisted?
        path: str = parsed_url.path
        splitted_path: list[str] = os.path.split(path) if path else []
        print(f"splitted_path: [{splitted_path}]")
        if not len(splitted_path) == 2:
            # not a path
            print("we need a valid upmpdcli path here.")
            return None
        left: str = splitted_path[0]
        right: str = splitted_path[1]
        if not left == "/subsonic/track/version/1/trackId":
            print("Not an upmpdcli url, bailing out.")
            return None
        return right
