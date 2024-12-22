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
import socket

from typing import Optional, Sequence
# from typing import Union

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable, UpnpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpResponseError, UpnpConnectionError
from async_upnp_client.profiles.dlna import dlna_handle_notify_last_change
from async_upnp_client.utils import get_local_ip

from song import Song, copy_song, same_song
from player_state import PlayerState, get_player_state
from util import duration_str_to_sec
from event_name import EventName

import config


key_title: str = "dc:title"
key_subtitle: str = "dc:subtitle"
key_artist: str = "upnp:artist"
key_album: str = "upnp:album"
key_duration: tuple[str, str] = ["res", "@duration"]

item_path: list[str] = ["DIDL-Lite", "item"]

g_previous_song: Song = None
g_current_song: Song = None
last_scrobbled: Song = None

g_items: dict = {}

g_event_handler = None
g_player_state: PlayerState = PlayerState.UNKNOWN

_print = print


def print(*args, **kw):
    _print("[%s]" % (datetime.datetime.now()), *args, **kw)


async def create_device(description_url: str) -> UpnpDevice:
    """Create UpnpDevice."""
    timeout: int = 60
    non_strict: bool = True
    requester: UpnpRequester = AiohttpRequester(timeout)
    factory: UpnpFactory = UpnpFactory(requester, non_strict=non_strict)
    return await factory.async_create_device(description_url)


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


def maybe_scrobble(current_song: Song) -> bool:
    global last_scrobbled
    if last_scrobbled and same_song(current_song, last_scrobbled):
        # too close in time?
        delta: float = current_song.playback_start - last_scrobbled.playback_start
        if delta < config.get_minimum_delta():
            print("Requesting a new scrobble for the same song again too early, not scrobbling")
            return False
    if execute_scrobble(current_song):
        last_scrobbled = copy_song(current_song)
        return True
    return False


def execute_scrobble(current_song: Song) -> bool:
    now: float = time.time()
    # if we have no duration, we assume 4 m, so we scrobble at 2 minutes
    song_duration: float = current_song.duration if current_song.duration else float(120)
    duration_estimated: bool = current_song.duration is None
    elapsed: float = now - current_song.playback_start
    over_threshold: bool = elapsed >= config.get_duration_threshold()
    over_half: bool = elapsed >= (song_duration / 2.0)
    print(f"execute_scrobble duration [{song_duration}] now [{now}] "
          f"playback_start [{current_song.playback_start}] -> elapsed [{elapsed}] "
          f"over_threshold [{over_threshold}] over_half [{over_half}]")
    if over_threshold or over_half:
        print(f"execute_scrobble we can scrobble [{current_song.title}] "
              f"from [{current_song.album}] "
              f"by [{current_song.artist}] "
              f"elapsed [{elapsed:.2f}] "
              f"duration [{song_duration:.2f}] "
              f"threshold [{config.get_duration_threshold()}] "
              f"over_threshold [{over_threshold}] "
              f"over_half [{over_half}]")
        last_fm_scrobble(current_song=current_song)
        print(f"Scrobble success for [{current_song.title}] "
              f"from [{current_song.album}] "
              f"by [{current_song.artist}]")
        return True
    else:
        print(f"execute_scrobble cannot scrobble [{current_song.title}] "
              f"from [{current_song.album}] "
              f"by [{current_song.artist}], "
              f"elapsed: [{elapsed:.2f}] "
              f"duration: [{song_duration:.2f}] "
              f"estimated [{duration_estimated}] "
              f"over_threshold [{over_threshold}] "
              f"over_half [{over_half}]")
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


def do_update_now_playing(current_song: Song):
    last_fm_now_playing(current_song)


def last_fm_now_playing(current_song: Song):
    network: pylast.LastFMNetwork = create_last_fm_network()
    network.update_now_playing(
        artist=get_first_artist(current_song.artist),
        title=current_song.title,
        album=current_song.album,
        duration=int(current_song.duration) if current_song.duration else None)


def last_fm_scrobble(current_song: Song):
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


def metadata_to_new_current_song(items: dict[str, any], track_uri: str) -> Song:
    current_song: Song = Song()
    current_song.title = items[key_title] if key_title in items else None
    current_song.subtitle = items[key_subtitle] if key_subtitle in items else None
    current_song.album = items[key_album] if key_album in items else None
    current_song.artist = items[key_artist] if key_artist in items else None
    duration_str: str = (items[key_duration[0]][key_duration[1]]
                         if key_duration[0] in items and key_duration[1] in items[key_duration[0]]
                         else None)
    if duration_str: current_song.duration = duration_str_to_sec(duration_str)
    current_song.track_uri = track_uri
    return current_song


def on_playing(song: Song):
    update_now_playing: bool = config.get_enable_now_playing()
    song_info: str = (f"[{song.title}] from [{song.album}] "
                      f"by [{get_first_artist(song.artist)}]")
    if song:
        print(f"Updating [now playing] [{'enabled' if update_now_playing else 'disabled'}] for song {song_info}")
    if update_now_playing and song:
        do_update_now_playing(song)


def get_items(event_name: str, event_value: any) -> any:
    parsed: dict[str, any]
    try:
        parsed = xmltodict.parse(event_value)
    except Exception as ex:
        print(f"on_event parse failed due to [{type(ex)}] [{ex}]")
        return None
    didl_lite = parsed[item_path[0]] if item_path[0] in parsed else dict()
    p_items = didl_lite[item_path[1]] if item_path[1] in didl_lite else None
    if p_items is None:
        msg: str = f"Event [{event_name}] -> no data."
        print(msg)
        raise Exception(msg)
    if config.get_dump_upnp_data():
        # Print the entire mess
        print(json.dumps(p_items, indent=4))
    return p_items


def get_player_state_from_service_variables(sv_dict: dict[str, any]) -> PlayerState:
    if EventName.TRANSPORT_STATE.value in sv_dict:
        return get_player_state(sv_dict[EventName.TRANSPORT_STATE.value])
    else:
        return None


def service_variables_by_name(service_variables: Sequence[UpnpStateVariable]) -> dict[str, UpnpStateVariable]:
    result: dict[str, UpnpStateVariable] = dict()
    for sv in service_variables:
        result[sv.name] = sv.value
    return result


def song_to_string(song: Song) -> str:
    if song:
        return (f"Song [{song.title}] from [{song.album}] by [{song.artist}] "
                f"Duration [{song.duration}] PlaybackStart [{song.playback_start}] "
                f"Subtitle [{song.subtitle}] TrackUri [{song.track_uri}]")
    else:
        return "<NO_DATA>"


def on_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    """Handle a UPnP event."""
    global g_player_state
    global g_items
    global g_current_song
    global g_previous_song
    # special handling for DLNA LastChange state variable
    if config.get_dump_upnp_data():
        print(f"on_event: service_variables=[{service_variables}]")
    if (len(service_variables) == 1 and
            service_variables[0].name == "LastChange"):
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)
    else:
        now_playing_updated: bool = False
        sv_dict: dict[str, any] = service_variables_by_name(service_variables)
        # must have transport state
        previous_player_state: PlayerState = g_player_state
        current_player_state: PlayerState = get_player_state_from_service_variables(sv_dict)
        # current_player_state: PlayerState = g_player_state
        if current_player_state:
            g_player_state = current_player_state
        else:
            print(f"No new player state available, assuming unchanged [{g_player_state.value}]")
        print(f"Player state [{previous_player_state.value if previous_player_state else ''}] -> "
              f"[{g_player_state.value if g_player_state else ''}]")
        # get current track uri
        track_uri: str = (sv_dict[EventName.CURRENT_TRACK_URI.value]
                          if EventName.CURRENT_TRACK_URI.value in sv_dict else None)
        if track_uri:
            print(f"Track URI = [{track_uri}]")
        has_current_track_meta_data: bool = EventName.CURRENT_TRACK_META_DATA.value in sv_dict
        has_av_transport_uri_meta_data: bool = EventName.AV_TRANSPORT_URI_META_DATA.value in sv_dict
        # get metadata
        metadata_key: str = None
        if has_current_track_meta_data:
            metadata_key = EventName.CURRENT_TRACK_META_DATA.value
        elif has_av_transport_uri_meta_data:
            metadata_key = EventName.AV_TRANSPORT_URI_META_DATA.value
        print(f"Metadata available: [{metadata_key is not None}]")
        new_metadata: Song = None
        if metadata_key:
            g_items = get_items(metadata_key, sv_dict[metadata_key])
            new_metadata = metadata_to_new_current_song(g_items, track_uri) if g_items else None
            empty_g_current_song: bool = g_current_song is None
            metadata_is_new: bool = g_current_song is None or not same_song(g_current_song, new_metadata)
            print(f"new_metadata is new: [{metadata_is_new}] -> [{song_to_string(new_metadata)}]")
            if new_metadata:
                if empty_g_current_song or not same_song(g_current_song, new_metadata):
                    print(f"Setting g_current_song to [{new_metadata.title}] "
                          f"by [{new_metadata.artist}] "
                          f"from [{new_metadata.album}] ...")
                    g_previous_song = g_current_song if g_current_song else None
                    g_current_song = new_metadata
                    # notify now playing if configured
                    print("Updating Now Playing with song information because we have new metadata ...")
                    on_playing(new_metadata)
                    now_playing_updated = True
                    # did the song change?
                    if g_previous_song and not same_song(g_previous_song, g_current_song):
                        print("Scrobbling because we have a new song in incoming metadata (new_metadata)")
                        maybe_scrobble(current_song=g_current_song)
                        print("Resetting g_current_song after scrobbling because of new incoming metadata ...")
                        # we scrobbled so we reset g_current_song
                        g_current_song = None
                else:
                    print("Not updating g_current_song")
            else:
                print("new_metadata is None")
        if PlayerState.PLAYING.value == g_player_state.value:
            print(f"Player state is [{g_player_state.value}] previous [{previous_player_state.value}] "
                  f"metadata_key [{metadata_key}] new_metadata [{new_metadata is not None}] "
                  f"g_current_song [{g_current_song is not None}]")
            if metadata_key:
                # song changed
                song_changed: bool = g_previous_song is None or not same_song(new_metadata, g_previous_song)
                print(f"Song changed: [{song_changed}] "
                      f"g_previous_song: [{g_previous_song is not None}]")
                if g_previous_song:
                    print(f"Scrobbling previous_song while handling [{PlayerState.PLAYING.value}] ...")
                    maybe_scrobble(current_song=g_previous_song)
                    print(f"Resetting g_current_song while handling [{PlayerState.PLAYING.value}] ...")
                    g_current_song = None
            else:
                # we update the now playing
                if new_metadata:
                    if not now_playing_updated:
                        print("Updating Now Playing with song information from incoming metadata ...")
                        on_playing(new_metadata)
                    else:
                        print("Now Playing (case #1) has been updated already ...")
                else:
                    # just update if we have a g_current_song
                    if g_current_song:
                        if not now_playing_updated:
                            print("Updating Now Playing with song information from g_current_song ...")
                            on_playing(g_current_song)
                        else:
                            print("Now Playing (case #2) has been updated already ...")
                    else:
                        print("Empty g_current_song, cannot update Now Playing")
        elif PlayerState.PAUSED_PLAYBACK.value == g_player_state.value:
            print(f"Player state is [{g_player_state.value}] previous [{previous_player_state.value}] "
                  f"metadata_key [{metadata_key}] new_metadata [{new_metadata is not None}] "
                  f"g_current_song [{g_current_song is not None}] -> No Action")
        elif PlayerState.TRANSITIONING.value == g_player_state.value:
            print(f"Player state is [{g_player_state.value}] previous [{previous_player_state.value}] "
                  f"metadata_key [{metadata_key}] new_metadata [{new_metadata is not None}] "
                  f"g_current_song [{g_current_song is not None}] -> No Action")
        elif PlayerState.STOPPED.value == g_player_state.value:
            print(f"Player state is [{g_player_state.value}] previous [{previous_player_state.value}] "
                  f"g_previous_song [{g_previous_song is not None}]")
            # we need to scrobble!
            if g_current_song:
                print(f"Scrobbling because of the {PlayerState.STOPPED.value} state ...")
                maybe_scrobble(current_song=g_current_song)
            # reset g_current_song anyway
            print(f"Resetting g_current_song because of the {PlayerState.STOPPED.value} state ...")
            g_current_song = None


async def subscribe(description_url: str, service_names: any) -> None:
    """Subscribe to service(s) and output updates."""
    global g_event_handler  # pylint: disable=global-statement
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
    print(f"subscribe: source=[{source}]")
    server = AiohttpNotifyServer(device.requester, source=source)
    await server.async_start_server()
    # gather all wanted services
    if "*" in service_names:
        service_names = device.services.keys()
        print(f"subscribe: service_names:[{service_names}]")
    services = []
    for service_name in service_names:
        print(f"subscribe: Getting service [{service_name}] from device ...")
        service = service_from_device(device, service_name)
        if not service:
            print(f"Unknown service: {service_name}")
            sys.exit(1)
        print(f"subscribe: Got service [{service_name}] from device.")
        service.on_event = on_event
        services.append(service)
    # subscribe to services
    g_event_handler = server.event_handler
    for service in services:
        print(f"subscribe: Subscribing to service [{service}] ...")
        try:
            await g_event_handler.async_subscribe(service)
            print(f"subscribe: Subscribed to service [{service}].")
        except UpnpResponseError as ex:
            print(f"Unable to subscribe to {service}: {ex}")
    s = 0
    # keep the webservice running
    while True:
        await asyncio.sleep(10)
        s = s + 1
        if s >= 12:
            await g_event_handler.async_resubscribe_all()
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


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def main() -> None:
    host_ip: str = get_ip()
    print(f"Running on [{host_ip}]")
    print(f"Now Playing enabled: [{config.get_enable_now_playing()}]")
    print(f"Dump UPnP Data: [{config.get_dump_upnp_data()}]")
    """Set up async loop and run the main program."""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(async_main())
    except KeyboardInterrupt:
        if g_event_handler:
            loop.run_until_complete(g_event_handler.async_unsubscribe_all())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
