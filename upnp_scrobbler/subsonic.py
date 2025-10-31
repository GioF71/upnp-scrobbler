import os
import constants
import config
from util import is_true
from util import joined_words
from util import joined_words_lower
from subsonic_connector.song import Song as SubsonicSong
from subsonic_connector.connector import Connector as SubsonicConnector
from subsonic_connector.response import Response as SubsonicResponse
from subsonic_connector.search_result import SearchResult as SubsonicSearchResult
from subsonic_configuration import SubsonicConnectorConfiguration
from subsonic_configuration import ScrobblerSubsonicConfiguration

from urllib.parse import urlparse
from urllib.parse import parse_qs
from util import print
import dotenv


def get_subsonic_config_key_count() -> int:
    return len(get_subsonic_config_keys())


def get_subsonic_config_keys() -> list[str]:
    ssf_dict: dict[str, list[str]] = config.find_subsonic_env_files()
    return list(ssf_dict.keys()) if ssf_dict else []


def get_single_subsonic_config(subsonic_key: str) -> ScrobblerSubsonicConfiguration:
    ssf_dict: dict[str, list[str]] = config.find_subsonic_env_files()
    lst: list[str] = ssf_dict[subsonic_key] if subsonic_key in ssf_dict else None
    if not lst:
        return None
    # build ScrobblerSubsonicConfiguration
    cfg_dict: dict[str, str] = {}
    file_name: str
    for file_name in lst:
        fp: str = os.path.join(config.get_subsonic_config_dir(), file_name)
        val_dict: dict[str, any] = dotenv.dotenv_values(dotenv_path=fp)
        for k, v in val_dict.items():
            cfg_dict[k] = v
    # cfg_dict
    base_url: str = __cfg_value_or_default_value(
        from_dict=cfg_dict,
        key=constants.ConfigParam.SUBSONIC_BASE_URL)
    username: str = __cfg_value_or_default_value(
        from_dict=cfg_dict,
        key=constants.ConfigParam.SUBSONIC_USERNAME)
    password: str = __cfg_value_or_default_value(
        from_dict=cfg_dict,
        key=constants.ConfigParam.SUBSONIC_PASSWORD)
    if not (base_url and username and password):
        return None
    # good to go.
    port: str = __cfg_value_or_default_value(
        from_dict=cfg_dict,
        key=constants.ConfigParam.SUBSONIC_PORT)
    server_path: str = __cfg_value_or_default_value(
        from_dict=cfg_dict,
        key=constants.ConfigParam.SUBSONIC_SERVER_PATH)
    legacy_auth: bool = is_true(
        v=__cfg_value_or_default_value(
            from_dict=cfg_dict,
            key=constants.ConfigParam.SUBSONIC_LEGACY_AUTH))
    enable_now_playing: bool = is_true(
        v=__cfg_value_or_default_value(
            from_dict=cfg_dict,
            key=constants.ConfigParam.SUBSONIC_ENABLE_NOW_PLAYING))
    allow_match: bool = is_true(
        v=__cfg_value_or_default_value(
            from_dict=cfg_dict,
            key=constants.ConfigParam.SUBSONIC_ENABLE_SONG_MATCH))
    return ScrobblerSubsonicConfiguration(
        subsonic_key=subsonic_key,
        base_url=base_url,
        port=int(port) if port else None,
        username=username,
        password=password,
        server_path=server_path,
        legacy_auth=legacy_auth,
        enable_now_playing=enable_now_playing,
        allow_match=allow_match)


def __cfg_value_or_default_value(from_dict: dict[str, any], key: constants.ConfigParam) -> str:
    curr_key: str
    for curr_key in key.key:
        if curr_key in from_dict:
            return from_dict[curr_key]
    return key.default_value


def scrobble_song(
        song: SubsonicSong,
        config: ScrobblerSubsonicConfiguration,
        submission: bool = True):
    subsonic_config: SubsonicConnectorConfiguration = SubsonicConnectorConfiguration(cfg=config)
    cn: SubsonicConnector = SubsonicConnector(configuration=subsonic_config)
    cn.scrobble(
        song_id=song.getId(),
        submission=submission)


def get_song_by_id(song_id: str, config: ScrobblerSubsonicConfiguration) -> SubsonicSong:
    subsonic_config: SubsonicConnectorConfiguration = SubsonicConnectorConfiguration(cfg=config)
    cn: SubsonicConnector = SubsonicConnector(configuration=subsonic_config)
    subsonic_song_res: SubsonicResponse[SubsonicSong] = None
    try:
        subsonic_song_res = cn.getSong(song_id=song_id)
    except Exception as ex:
        print(f"get_song_by_id subsonic_key [{config.subsonic_key}] "
              f"cannot get song_id [{song_id}] due to [{type(ex)}] [{ex}]")
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
        if not len(splitted_path) == 2:
            # not an upmpdcli path
            # print(f"get_song_id uri: [{uri}] we expect 2 elements in path")
            return None
        left: str = splitted_path[0]
        right: str = splitted_path[1]
        if not left == "/subsonic/track/version/1/trackId":
            # print(f"get_song_id uri: [{uri}] is not an upmpdcli uri")
            return None
        return right


def get_song_item_as_str(song: SubsonicSong, item_key: str) -> str:
    v: any = song.getItem().getByName(item_key)
    # should be a string
    if isinstance(v, str):
        return v
    return None


def get_song_item_list_dict_value(
        song: SubsonicSong,
        item_key: str,
        dict_key: str = "name") -> str:
    result: list[str] = []
    v: any = song.getItem().getListByName(item_key)
    # should be a list
    if isinstance(v, list):
        # go on.
        item_array: list = v
        for a_dict in item_array:
            # should be a dict
            if isinstance(a_dict, dict):
                for dict_k, dict_v in a_dict.items():
                    # k should be str of course
                    if (not (isinstance(dict_k, str))):
                        continue
                    if (dict_k != dict_key):
                        continue
                    # dict_v should be a string
                    if not isinstance(dict_v, str):
                        continue
                    # store value.
                    result.append(dict_v)
    return result


def get_artist_list(song: SubsonicSong) -> list[str]:
    result: list[str] = []
    # add artist if available
    if song.getArtist():
        result.append(song.getArtist())
    # displayAlbumArtist, displayArtist -> str
    display_album_artist: any = get_song_item_as_str(song, "displayAlbumArtist")
    if display_album_artist and display_album_artist not in result:
        result.append(display_album_artist)
    display_artist: any = get_song_item_as_str(song, "displayArtist")
    if display_artist and display_artist not in result:
        result.append(display_artist)
    # artists and albumArtists -> dict -> use "name"
    curr: str
    artists: list[str] = get_song_item_list_dict_value(
        song=song,
        item_key="artists",
        dict_key="name")
    for curr in artists if artists else []:
        if curr not in result:
            result.append(curr)
    album_artists: list[str] = get_song_item_list_dict_value(
        song=song,
        item_key="albumArtists",
        dict_key="name")
    for curr in album_artists if album_artists else []:
        if curr not in result:
            result.append(curr)
    return result


def match_artist_using_splitter(song_artist_list: list[str], provided_artist: str, splitter: str) -> bool:
    raw_splitted_artist: list[str] = list(map(lambda x: x.lower().strip(), provided_artist.split(splitter)))
    # we have more than one artist
    if len(raw_splitted_artist) < 2:
        return False
    # avoid duplications
    curr_splitted: str
    splitted_artist: list[str] = []
    for curr_splitted in raw_splitted_artist:
        if curr_splitted not in splitted_artist:
            splitted_artist.append(curr_splitted)
    # we could split artists, see if the splitted values match
    curr_splitted: str
    for curr_splitted in splitted_artist:
        if joined_words_lower(curr_splitted) not in song_artist_list:
            return False
    return True


def match_song_with_artist(song: SubsonicSong, artist: str) -> bool:
    artist_words: str = joined_words_lower(artist)
    if song.getArtist() and joined_words_lower(song.getArtist()) == artist_words:
        # exact match
        return True
    # split artists
    song_artist_list: list[str] = list(map(lambda x: joined_words_lower(x), get_artist_list(song)))
    # is artist_words in any of song_artist_list?
    if artist_words in song_artist_list:
        # match, provided artist is in the list of artists from the song
        return True
    # no match yet, try splitting
    if match_artist_using_splitter(song_artist_list=song_artist_list, provided_artist=artist, splitter="/"):
        return True
    if match_artist_using_splitter(song_artist_list=song_artist_list, provided_artist=artist, splitter=","):
        return True
    return False


def find_song(
        config: ScrobblerSubsonicConfiguration,
        song_title: str,
        song_artist: str,
        song_album: str = None,
        initial_search_size: int = 10,
        next_search_size: int = 30,
        max_search_size: int = 100) -> SubsonicSong:
    cmp_song_album: str = joined_words_lower(song_album) if song_album else None
    subsonic_config: SubsonicConnectorConfiguration = SubsonicConnectorConfiguration(cfg=config)
    cn: SubsonicConnector = SubsonicConnector(configuration=subsonic_config)
    search_counter: int = 0
    search_song_title: str = joined_words_lower(song_title)
    while (search_counter < max_search_size):
        search_size: int = None
        search_offset: int = None
        if search_counter == 0:
            # min between initial and max_search_size so we honor max
            search_size = min(initial_search_size, max_search_size)
            search_offset = 0
        else:
            search_size = min(next_search_size, (max_search_size - search_counter))
            search_offset = search_counter
        if search_size == 0:
            # we're finished without a match
            return None
        sr: SubsonicSearchResult = cn.search(
            query=search_song_title,
            songCount=search_size,
            artistCount=0,
            albumCount=0,
            songOffset=search_offset)
        if len(sr.getSongs()) == 0:
            # no more entries we're finished without a match
            return None
        current_song: SubsonicSong
        for current_song in sr.getSongs():
            search_counter += 1
            # must match title
            match: bool = search_song_title == joined_words_lower(current_song.getTitle())
            # must match artist(s)
            match = match and match_song_with_artist(current_song, song_artist)
            # match album if required
            if match and (not song_album or joined_words_lower(current_song.getAlbum()) == cmp_song_album):
                # album match not required, or album matches, so we return this song
                return current_song
    return None
