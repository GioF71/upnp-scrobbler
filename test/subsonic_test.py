import os

from upnp_scrobbler.subsonic import get_song_id
from upnp_scrobbler.subsonic import get_single_subsonic_config
from upnp_scrobbler.subsonic import get_subsonic_config_keys
from upnp_scrobbler.subsonic import ScrobblerSubsonicConfiguration as ScrobblerSubsonicConfig
from upnp_scrobbler.subsonic_configuration import SubsonicConnectorConfiguration
from subsonic_connector.connector import Connector
from subsonic_connector.response import Response
from subsonic_connector.song import Song
from upnp_scrobbler.subsonic import find_song


track_uri_upmpdcli: str = "http://192.168.1.173:49139/subsonic/track/version/1/trackId/tr-105133"
track_uri_subsonic: str = os.getenv("TRACK_URI_SUBSONIC")

# track_to_match_title: str = "evermore"
# track_to_match_title: str = "On The Run (Part 1)"
# track_to_match_artist: str = "taylor swift/bon iver"
# track_to_match_artist: str = "Seamus Blake, Ari Hoenig, Mike Moreno, Sam Yahel, Seamus Blake, Ari Hoenig, Mike Moreno, Sam Yahel"
# track_to_match_album: str = "the jazz side of the moon"
# track_to_match_album: str = None


def test_scrobble_by_url(track_uri: str):
    subsonic_keys: list[str] = get_subsonic_config_keys()
    subsonic_key: str
    for subsonic_key in subsonic_keys:
        subsonic_config: ScrobblerSubsonicConfig = get_single_subsonic_config(subsonic_key=subsonic_key)
        connector_config: SubsonicConnectorConfiguration = SubsonicConnectorConfiguration(subsonic_config)
        print(f"subsonic_key [{subsonic_key}] "
              f"track_uri: [{track_uri}]")
        song_id: str = get_song_id(
            uri=track_uri,
            config=subsonic_config)
        print(f"subsonic_key [{subsonic_key}] "
              f"song_id = [{song_id}]")
        if not song_id:
            print(f"subsonic_key [{subsonic_key}] "
                  "no track id, bailing out.")
            continue
        cn: Connector = Connector(configuration=connector_config)
        res: Response[Song]
        try:
            res = cn.getSong(song_id=song_id)
        except Exception as ex:
            print(f"subsonic_key [{subsonic_key}] "
                  f"could not get song [{song_id}] "
                  f"due to [{type(ex)}] [{ex}]")
            continue
        if not res.isOk():
            print(f"subsonic_key [{subsonic_key}] "
                  f"could not get song [{song_id}] "
                  f"response is not ok")
            continue
        # found!
        song: Song = res.getObj()
        print(f"Found song [{song.getTitle()}] from [{song.getAlbum()}] by [{song.getArtist()}]")
        # cn.scrobble(song_id=song_id)
        # print(f"Scrobbled song [{song_id}]")


def test_scrobble_by_match(match_title: str, match_artist: str, match_album: str = None):
    subsonic_keys: list[str] = get_subsonic_config_keys()
    subsonic_key: str
    for subsonic_key in subsonic_keys:
        print(f"test_scrobble_by_match on [{subsonic_key}] ...")
        subsonic_config: ScrobblerSubsonicConfig = get_single_subsonic_config(subsonic_key=subsonic_key)
        matched: Song = find_song(
            config=subsonic_config,
            song_title=match_title,
            song_artist=match_artist,
            song_album=match_album,
            initial_search_size=10)
        if matched:
            print(f"Matched song [{matched.getTitle()}] "
                  f"from [{matched.getAlbum()}] "
                  f"by [{matched.getArtist()}] "
                  f"on [{subsonic_key}]")
        else:
            print(f"Song [{match_title}] by [{match_artist}] from [{match_album}] "
                  f"was not matched on [{subsonic_key}]")


to_match: list = [
    (
        "you & me",
        "The Cranberries",
        "something else"
    ),
    (
        "evermore",
        "taylor swift/bon iver",
        None
    ),
    (
        "On The Run (Part 1)",
        "Seamus Blake, Ari Hoenig, Mike Moreno, Sam Yahel, Seamus Blake, Ari Hoenig, Mike Moreno, Sam Yahel",
        None
    ),
    (
        "Fortnight",
        "Taylor Swift",
        "THE TORTURED POETS DEPARTMENT | TS The Eras Tour Setlist"
    ),
    (
        "unraveled",
        "Beth Wood",
        "Late Night Radio"
    )]

if __name__ == "__main__":
    test_scrobble_by_url(track_uri_subsonic)
    test_scrobble_by_url(track_uri_upmpdcli)
    # test_scrobble_by_match("On The Run (Part 1)", "Seamus Blake, Ari Hoenig, Mike Moreno, Sam Yahel, Seamus Blake, Ari Hoenig, Mike Moreno, Sam Yahel")
    for m in to_match:
        test_scrobble_by_match(m[0], m[1], m[2])
    print("Everything passed")
