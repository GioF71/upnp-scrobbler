import time


class Song:

    def __init__(self):
        # keep track of creation time
        self._playback_start: float = time.time()
        self._title: str = None
        self._subtitle: str = None
        self._artist: str = None
        self._album: str = None
        self._duration: float = None
        self._track_uri: str = None

    @property
    def playback_start(self) -> float:
        return self._playback_start

    @playback_start.setter
    def playback_start(self, value: float):
        self._playback_start: str = value

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str):
        self._title: str = value

    @property
    def subtitle(self) -> str:
        return self._subtitle

    @subtitle.setter
    def subtitle(self, value: str):
        self._subtitle: str = value

    @property
    def artist(self) -> str:
        return self._artist

    @artist.setter
    def artist(self, value: str):
        self._artist: str = value

    @property
    def album(self) -> str:
        return self._album

    @album.setter
    def album(self, value: str):
        self._album: str = value

    @property
    def duration(self) -> float:
        return self._duration

    @duration.setter
    def duration(self, value: float):
        self._duration: str = value

    @property
    def track_uri(self) -> str:
        return self._track_uri

    @track_uri.setter
    def track_uri(self, value: str):
        self._track_uri = value


def same_song(left: Song, right: Song) -> bool:
    return (left.album == right.album and
            left.artist == right.artist and
            left.duration == right.duration and
            left.subtitle == right.subtitle and
            left.title == right.title and
            left.track_uri == right.track_uri)


def copy_song(song: Song) -> Song:
    copied: Song = Song()
    copied.album = song.album
    copied.artist = song.artist
    copied.duration = song.duration
    copied.playback_start = song.playback_start
    copied.subtitle = song.subtitle
    copied.title = song.title
    copied.track_uri = song.track_uri
    return copied
