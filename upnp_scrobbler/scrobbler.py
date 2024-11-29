#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name

import asyncio
import json
import sys
import time
import xmltodict
import os
import datetime
import pylast

from typing import Optional, Sequence, Union

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable, UpnpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpResponseError, UpnpConnectionError
from async_upnp_client.profiles.dlna import dlna_handle_notify_last_change
from async_upnp_client.utils import get_local_ip

key_title: str = "dc:title"
key_subtitle: str = "dc:subtitle"
key_artist: str = "upnp:artist"
key_album: str = "upnp:album"
key_duration: tuple[str, str] = ["res", "@duration"]

item_path: list[str] = ["DIDL-Lite", "item"]

DEFAULT_DURATION_THRESHOLD: int = 240
DEFAULT_DUMP_UPNP_DATA: bool = False
DEFAULT_ENABLE_NOW_PLAYING: bool = True


def get_bool_config(env_key: str, default_value: bool) -> bool:
    cfg: str = os.getenv(env_key)
    if not cfg: return default_value
    return cfg.upper() == 'Y' or cfg.upper() == 'YES'


def get_enable_now_playing() -> bool:
    return get_bool_config(
        env_key="ENABLE_NOW_PLAYING",
        default_value=DEFAULT_ENABLE_NOW_PLAYING)


def get_dump_upnp_data() -> bool:
    return get_bool_config(
        env_key="DUMP_UPNP_DATA",
        default_value=DEFAULT_DUMP_UPNP_DATA)


def get_duration_threshold() -> int:
    duration_cfg: str = os.getenv("DURATION_THRESHOLD")
    if not duration_cfg: return DEFAULT_DURATION_THRESHOLD
    return int(duration_cfg)


def duration_str_to_sec(duration: str) -> float:
    # print(f"duration_str_to_sec duration=[{duration}] ...")
    by_dot: list[str] = duration.split(".")
    len_by_dot: int = len(by_dot) if by_dot else 0
    if len_by_dot == 0 or len_by_dot > 2:
        if len_by_dot > 2:
            print(f"Duration split by [.] resulting in more [{len_by_dot}] elements (more than 2).")
        return float(0)
    # print(f"duration_str_to_sec duration=[{duration}] -> by_dot:[{by_dot}] ...")
    if len_by_dot == 1:
        # so we have one string after splitting by "."
        one_segment: str = by_dot[0]
        # case 1, no ":" -> "millis"
        if ":" not in one_segment:
            millis = one_segment
            left = ""
        # case 2, we have ":" -> "hh:mm:ss"
        else:
            millis = ""
            left = one_segment
    else:
        # we should be dealing with hh:mm:ss.nnn
        left = by_dot[0]
        millis = by_dot[1]
    # print(f"duration_str_to_sec duration=[{duration}] -> left:[{left}] millis:[{millis}]...")
    left_split: list[str] = left.split(":") if left else list()
    left_split_len: int = len(left_split)
    if left_split_len > 3:
        print(f"Left part [{left}] splitted by "":"" in {left_split_len} elements (more than 3)")
        return float(0)
    # seconds is last, if available
    milliseconds: float = float(int(millis)) if millis and len(millis) > 0 else float(0)
    seconds_str: str = left_split[left_split_len - 1] if left_split_len > 0 else "0"
    minutes_str: str = left_split[len(left_split) - 2] if left_split_len > 1 else "0"
    hours_str = left_split[left_split_len - 3] if left_split_len > 2 else "0"
    # print(f"duration_str_to_sec duration=[{duration}] -> "
    #       f"h:[{hours_str}] "
    #       f"m:[{minutes_str}] "
    #       f"s:[{seconds_str}] "
    #       f"millis:[{millis}] ...")
    result: float = ((milliseconds / 1000.0) +
                     float(int(seconds_str)) +
                     float(int(minutes_str) * 60.0) +
                     float(int(hours_str) * 3600.0))
    print(f"duration_str_to_sec [{duration}] -> [{result}] (sec)")
    return result


class CurrentSong:

    def __init__(self):
        # keep track of creation time
        self._playback_start: float = time.time()
        self._title: str = None
        self._subtitle: str = None
        self._artist: str = None
        self._album: str = None
        self._duration: float = None

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


def same_song(left: CurrentSong, right: CurrentSong) -> bool:
    return (left.album == right.album and
            left.artist == right.artist and
            left.duration == right.duration and
            left.subtitle == right.subtitle and
            left.title == right.title)


def copy_current_song(current_song: CurrentSong) -> CurrentSong:
    copied: CurrentSong = CurrentSong()
    copied.album = current_song.album
    copied.artist = current_song.artist
    copied.duration = current_song.duration
    copied.playback_start = current_song.playback_start
    copied.subtitle = current_song.subtitle
    copied.title = current_song.title
    return copied


the_current_song: CurrentSong = None
last_scrobbled: CurrentSong = None

items: dict = {}

event_handler = None
playing = False


async def create_device(description_url: str) -> UpnpDevice:
    """Create UpnpDevice."""
    timeout: int = 60
    non_strict: bool = True
    requester: UpnpRequester = AiohttpRequester(timeout)
    factory: UpnpFactory = UpnpFactory(requester, non_strict=non_strict)
    return await factory.async_create_device(description_url)


def get_timestamp() -> Union[str, float]:
    """Timestamp depending on configuration."""
    return time.time()


def service_from_device(
        device: UpnpDevice,
        service_name: str) -> Optional[UpnpService]:
    """Get UpnpService from UpnpDevice by name or part or abbreviation."""
    for service in device.all_services:
        part = service.service_id.split(":")[-1]
        abbr = "".join([c for c in part if c.isupper()])
        if service_name in (service.service_type, part, abbr):
            return service
    return None


# we accept new scrobbles for the same song after (seconds) ...
minimum_delta: float = 10.0


def maybe_scrobble(current_song: CurrentSong):
    global last_scrobbled
    global the_current_song
    if last_scrobbled and same_song(current_song, last_scrobbled):
        # too close in time?
        delta: float = current_song.playback_start - last_scrobbled.playback_start
        if delta < minimum_delta:
            print("Requesting a new scrobble for the same song again too early, not scrobbling")
            return
    if execute_scrobble(current_song):
        last_scrobbled = copy_current_song(current_song)
    # the_current_song = None


def execute_scrobble(current_song: CurrentSong) -> bool:
    now: float = time.time()
    # if we have no duration, we assume 4 m, so we scrobble at 2 minutes
    song_duration: float = current_song.duration if current_song.duration else float(120)
    duration_estimated: bool = current_song.duration is None
    elapsed: float = now - current_song.playback_start
    if elapsed >= get_duration_threshold() or elapsed >= (song_duration / 2.0):
        print(f"execute_scrobble we can scrobble [{current_song.title}] "
              f"from [{current_song.album}] "
              f"by [{current_song.artist}]")
        last_fm_scrobble(current_song=current_song)
        return True
    else:
        print(f"execute_scrobble cannot scrobble [{current_song.title}] "
              f"from [{current_song.album}] "
              f"by [{current_song.artist}], "
              f"elapsed: [{elapsed}] duration: [{song_duration}] "
              f"estimated [{duration_estimated}]")
        return False


def create_last_fm_network() -> pylast.LastFMNetwork:
    last_fm_key: str = os.getenv("LAST_FM_API_KEY")
    last_fm_secret: str = os.getenv("LAST_FM_SHARED_SECRET")
    last_fm_username: str = os.getenv("LAST_FM_USERNAME")
    last_fm_password_hash: str = os.getenv("LAST_FM_PASSWORD_HASH")
    if not last_fm_password_hash:
        # try cleartext
        password: str = os.getenv("LAST_FM_PASSWORD")
        last_fm_password_hash = pylast.md5(password)
    network: pylast.LastFMNetwork = pylast.LastFMNetwork(
        api_key=last_fm_key,
        api_secret=last_fm_secret,
        username=last_fm_username,
        password_hash=last_fm_password_hash)
    return network


def last_fm_update_now_playing(current_song: CurrentSong):
    network: pylast.LastFMNetwork = create_last_fm_network()
    network.update_now_playing(
        artist=get_first_artist(current_song.artist),
        title=current_song.title,
        album=current_song.album,
        duration=int(current_song.duration) if current_song.duration else None)


def last_fm_scrobble(current_song: CurrentSong):
    network: pylast.LastFMNetwork = create_last_fm_network()
    unix_timestamp: int = int(time.mktime(datetime.datetime.now().timetuple()))
    network.scrobble(
        artist=get_first_artist(current_song.artist),
        title=current_song.title,
        timestamp=unix_timestamp)


def get_first_artist(artist: str) -> str:
    if not artist: return None
    artist_list: list[str] = artist.split(",")
    return artist_list[0] if artist_list and len(artist_list) > 0 else None


def metadata_to_new_current_song(items: dict[str, any]) -> CurrentSong:
    current_song: CurrentSong = CurrentSong()
    current_song.title = items[key_title] if key_title in items else None
    current_song.subtitle = items[key_subtitle] if key_subtitle in items else None
    current_song.album = items[key_album] if key_album in items else None
    current_song.artist = items[key_artist] if key_artist in items else None
    duration_str: str = (items[key_duration[0]][key_duration[1]]
                         if key_duration[0] in items and key_duration[1] in items[key_duration[0]]
                         else None)
    if duration_str: current_song.duration = duration_str_to_sec(duration_str)
    return current_song


def on_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    """Handle a UPnP event."""
    global playing
    global items
    global the_current_song
    # special handling for DLNA LastChange state variable
    if (len(service_variables) == 1 and
            service_variables[0].name == "LastChange"):
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)
    else:
        for sv in service_variables:
            # PAUSED, PLAYING, STOPPED, TRANSITIONING, etc
            if sv.name == "TransportState":
                print(f"Event [{sv.name}] = [{sv.value}]")
                if sv.value == "PLAYING":
                    playing = True
                else:
                    playing = False
                    if sv.value == "STOPPED" and the_current_song:
                        print(f"Scrobbling because: [{sv.value}]")
                        maybe_scrobble(the_current_song)
            # Grab and print the metadata
            if (sv.name in ["CurrentTrackMetaData", "AVTransportURIMetaData"]):
                metadata: bool = sv.name == "CurrentTrackMetaData"
                # Convert XML to beautiful JSON
                parsed: dict[str, any]
                try:
                    parsed = xmltodict.parse(sv.value)
                except Exception as ex:
                    print(f"on_event parse failed due to [{type(ex)}] [{ex}]")
                    return
                didl_lite = parsed[item_path[0]] if item_path[0] in parsed else dict()
                items = didl_lite[item_path[1]] if item_path[1] in didl_lite else None
                if items is None:
                    print(f"Event [{sv.name}] -> no data.")
                    return
                if get_dump_upnp_data():
                    # Print the entire mess
                    print(json.dumps(items, indent=4))
                if the_current_song and metadata:
                    # song changed -> scrobble!
                    maybe_new: CurrentSong = metadata_to_new_current_song(items)
                    song_changed: bool = not same_song(maybe_new, the_current_song)
                    print(f"Event [{sv.name}] Song changed = [{song_changed}]")
                    if song_changed:
                        print(f"Event [{sv.name}] -> We want to scrobble because the song changed: "
                              f"was [{the_current_song.title}] "
                              f"now [{maybe_new.title}]")
                        maybe_scrobble(the_current_song)
                # start creating a new CurrentSong instance
                current_song: CurrentSong = CurrentSong()
                current_song.title = items[key_title] if key_title in items else None
                current_song.subtitle = items[key_subtitle] if key_subtitle in items else None
                current_song.album = items[key_album] if key_album in items else None
                current_song.artist = items[key_artist] if key_artist in items else None
                duration_str: str = (items[key_duration[0]][key_duration[1]]
                                     if key_duration[0] in items and key_duration[1] in items[key_duration[0]]
                                     else None)
                # patch: reset duration_str
                # duration_str = None
                if duration_str: current_song.duration = duration_str_to_sec(duration_str)
                if (metadata and (not the_current_song or not same_song(current_song, the_current_song))):
                    print(f"[{sv.name}] => Setting current_song with "
                          f"[{current_song.title}] from [{current_song.album}] "
                          f"by [{current_song.artist}]")
                    the_current_song = current_song
                    # update now playing anyway (even if there is no duration)
                    update_now_playing: bool = get_enable_now_playing()
                    print(f"Updating [now playing] [{'yes' if update_now_playing else 'no'}] for new song "
                          f"[{current_song.title}] from [{current_song.album}] "
                          f"by [{get_first_artist(current_song.artist)}]")
                    if update_now_playing: last_fm_update_now_playing(current_song)
                # else:
                #     print(f"Sticking with the same current_song [{sv.name}]")


async def subscribe(description_url: str, service_names: any) -> None:
    """Subscribe to service(s) and output updates."""
    global event_handler  # pylint: disable=global-statement
    device = None
    firstException: UpnpConnectionError = None
    while device is None:
        try:
            device = await create_device(description_url)
            if firstException:
                print("subscribe successful.")
        except UpnpConnectionError as ex:
            # TODO some logging?
            if firstException is None:
                print(f"subscribe exception [{type(ex)}] [{ex}]")
                firstException = ex
            time.sleep(5)
    # start notify server/event handler
    source = (get_local_ip(device.device_url), 0)
    server = AiohttpNotifyServer(device.requester, source=source)
    await server.async_start_server()
    # gather all wanted services
    if "*" in service_names:
        service_names = device.services.keys()
    services = []
    for service_name in service_names:
        service = service_from_device(device, service_name)
        if not service:
            print(f"Unknown service: {service_name}")
            sys.exit(1)
        service.on_event = on_event
        services.append(service)
    # subscribe to services
    event_handler = server.event_handler
    for service in services:
        try:
            await event_handler.async_subscribe(service)
        except UpnpResponseError as ex:
            print(f"Unable to subscribe to {service}: {ex}")
    s = 0
    # keep the webservice running
    while True:
        await asyncio.sleep(10)
        s = s + 1
        if s >= 12:
            await event_handler.async_resubscribe_all()
            s = 0


async def async_main() -> None:
    """Async main."""
    #  Your device's IP and port go here
    device = os.getenv("DEVICE_URL")
    if not device:
        raise Exception("The variable DEVICE_URL is mandatory")
    service = ["AVTransport"]
    await subscribe(
        description_url=device,
        service_names=service)


def main() -> None:
    """Set up async loop and run the main program."""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(async_main())
    except KeyboardInterrupt:
        if event_handler:
            loop.run_until_complete(event_handler.async_unsubscribe_all())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
