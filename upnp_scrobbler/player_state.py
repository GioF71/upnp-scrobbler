from enum import Enum


class PlayerState(Enum):
    UNKNOWN = ""
    PLAYING = "PLAYING"
    PAUSED_PLAYBACK = "PAUSED_PLAYBACK"
    STOPPED = "STOPPED"
    TRANSITIONING = "TRANSITIONING"


def get_player_state(transport_state: str) -> PlayerState:
    for _, member in PlayerState.__members__.items():
        if transport_state == member.value:
            print(f"get_player_state {transport_state} -> {member.value}")
            return member
    print(f"get_player_state state for {transport_state} not found")
    return PlayerState.UNKNOWN
