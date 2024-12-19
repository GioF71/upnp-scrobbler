from enum import Enum


class EventName(Enum):
    TRANSPORT_STATE = "TransportState"
    CURRENT_PLAY_MODE = "CurrentPlayMode"
    CURRENT_TRACK_META_DATA = "CurrentTrackMetaData"
    AV_TRANSPORT_URI_META_DATA = "AVTransportURIMetaData"
    CURRENT_TRACK_URI = "CurrentTrackURI"
