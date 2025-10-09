import os

from upnp_scrobbler.subsonic import get_song_id
from upnp_scrobbler.subsonic import get_subsonic_config
from upnp_scrobbler.subsonic import ScrobblerSubsonicConfiguration as ScrobblerSubsonicConfig
from upnp_scrobbler.subsonic_configuration import SubsonicConnectorConfiguration
from subsonic_connector.connector import Connector
from subsonic_connector.response import Response
from subsonic_connector.song import Song


track_uri_upmpdcli: str = "http://192.168.1.173:49139/subsonic/track/version/1/trackId/tr-105133"
track_uri_subsonic: str = os.getenv("TRACK_URI_SUBSONIC")


def test_scrobble(track_uri: str):
    subsonic_config: ScrobblerSubsonicConfig = get_subsonic_config()
    connector_config: SubsonicConnectorConfiguration = SubsonicConnectorConfiguration(subsonic_config)

    print(f"track_uri: [{track_uri}]")
    song_id: str = get_song_id(
        uri=track_uri,
        config=subsonic_config)
    print(f"song_id = [{song_id}]")
    if not song_id:
        print("No track id, bailing out.")
        exit(0)
    cn: Connector = Connector(configuration=connector_config)
    res: Response[Song]
    try:
        res = cn.getSong(song_id=song_id)
    except Exception as ex:
        print(f"Could not get song [{song_id}] due to [{type(ex)}] [{ex}]")
        exit(0)
    if not res.isOk():
        print("No track id, bailing out.")
        exit(0)
    # found!
    song: Song = res.getObj()
    print(f"Found song [{song.getTitle()}] from [{song.getAlbum()}] by [{song.getArtist()}]")
    cn.scrobble(song_id=song_id)
    print(f"Scrobbled song [{song_id}]")


if __name__ == "__main__":
    test_scrobble(track_uri_subsonic)
    test_scrobble(track_uri_upmpdcli)
    print("Everything passed")
