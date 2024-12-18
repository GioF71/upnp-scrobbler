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

the_current_song: Song = None
last_scrobbled: Song = None

g_items: dict = {}

g_event_handler = None
g_playing = False
g_player_state: PlayerState = PlayerState.UNKNOWN


async def create_device(description_url: str) -> UpnpDevice:
    """Create UpnpDevice."""
    timeout: int = 60
    non_strict: bool = True
    requester: UpnpRequester = AiohttpRequester(timeout)
    factory: UpnpFactory = UpnpFactory(requester, non_strict=non_strict)
    return await factory.async_create_device(description_url)


# def get_timestamp() -> Union[str, float]:
#     """Timestamp depending on configuration."""
#     return time.time()


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


def maybe_scrobble(current_song: Song):
    global last_scrobbled
    global the_current_song
    if last_scrobbled and same_song(current_song, last_scrobbled):
        # too close in time?
        delta: float = current_song.playback_start - last_scrobbled.playback_start
        if delta < config.get_minimum_delta():
            print("Requesting a new scrobble for the same song again too early, not scrobbling")
            return
    if execute_scrobble(current_song):
        last_scrobbled = copy_song(current_song)
    # the_current_song = None


def execute_scrobble(current_song: Song) -> bool:
    now: float = time.time()
    # if we have no duration, we assume 4 m, so we scrobble at 2 minutes
    song_duration: float = current_song.duration if current_song.duration else float(120)
    duration_estimated: bool = current_song.duration is None
    elapsed: float = now - current_song.playback_start
    if elapsed >= config.get_duration_threshold() or elapsed >= (song_duration / 2.0):
        print(f"execute_scrobble we can scrobble [{current_song.title}] "
              f"from [{current_song.album}] "
              f"by [{current_song.artist}]")
        last_fm_scrobble(current_song=current_song)
        print(f"Scrobble success for [{current_song.title}] "
              f"from [{current_song.album}] "
              f"by [{current_song.artist}]")
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


def metadata_to_new_current_song(items: dict[str, any]) -> Song:
    current_song: Song = Song()
    current_song.title = items[key_title] if key_title in items else None
    current_song.subtitle = items[key_subtitle] if key_subtitle in items else None
    current_song.album = items[key_album] if key_album in items else None
    current_song.artist = items[key_artist] if key_artist in items else None
    duration_str: str = (items[key_duration[0]][key_duration[1]]
                         if key_duration[0] in items and key_duration[1] in items[key_duration[0]]
                         else None)
    if duration_str: current_song.duration = duration_str_to_sec(duration_str)
    return current_song


def on_playing(song: Song):
    update_now_playing: bool = config.get_enable_now_playing()
    if update_now_playing and song:
        print(f"Updating [now playing] [{'yes' if update_now_playing else 'no'}] for new song "
              f"[{song.title}] from [{song.album}] "
              f"by [{get_first_artist(song.artist)}]")
        do_update_now_playing(song)


def get_items(event_name: str, event_value: any) -> any:
    parsed: dict[str, any]
    try:
        parsed = xmltodict.parse(event_value)
    except Exception as ex:
        print(f"on_event parse failed due to [{type(ex)}] [{ex}]")
        return
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


def on_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    """Handle a UPnP event."""
    global g_playing
    global g_player_state
    global g_items
    global the_current_song
    # special handling for DLNA LastChange state variable
    if config.get_dump_upnp_data():
        print(f"on_event: service_variables=[{service_variables}]")
    if (len(service_variables) == 1 and
            service_variables[0].name == "LastChange"):
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)
    else:
        for sv in service_variables:
            print(f"on_event: sv.name=[{sv.name}]")
            if sv.name == EventName.TRANSPORT_STATE.value:
                print(f"Event [{sv.name}] = [{sv.value}]")
                new_player_state: PlayerState = get_player_state(sv.value)
                if sv.value == PlayerState.PLAYING.value:
                    g_playing = True
                    g_player_state = new_player_state
                    if the_current_song:
                        on_playing(the_current_song)
                else:
                    g_playing = False
                    was_playing: bool = g_player_state == PlayerState.PLAYING
                    g_player_state = new_player_state
                    if sv.value == PlayerState.STOPPED.value and was_playing and the_current_song:
                        print(f"Scrobbling because: [{sv.value}]")
                        maybe_scrobble(the_current_song)
                        # we can reset the_current_song!
                        the_current_song = None
            # elif (sv.name in ["CurrentPlayMode"]):
            #     print(f"sv.name=[{sv.name}] sv.value=[{sv.value}]")
            elif (sv.name in [EventName.CURRENT_TRACK_META_DATA.value, EventName.AV_TRANSPORT_URI_META_DATA.value]):
                metadata: bool = sv.name == EventName.CURRENT_TRACK_META_DATA.value
                # Grab and print the metadata
                g_items = get_items(sv.name, sv.value)
                if metadata:
                    if the_current_song:
                        # song changed -> scrobble!
                        maybe_new: Song = metadata_to_new_current_song(g_items)
                        song_changed: bool = not same_song(maybe_new, the_current_song)
                        print(f"Event [{sv.name}] Song changed = [{song_changed}]")
                        if song_changed:
                            print(f"Event [{sv.name}] -> We want to scrobble because the song changed: "
                                  f"was [{the_current_song.title}] "
                                  f"now [{maybe_new.title}]")
                            maybe_scrobble(the_current_song)
                            # we can reset the_current_song!
                            the_current_song = None
                # start creating a new Song instance
                current_song: Song = metadata_to_new_current_song(g_items)
                if (metadata and (not the_current_song or not same_song(current_song, the_current_song))):
                    print(f"[{sv.name}] => Setting current_song with "
                          f"[{current_song.title}] from [{current_song.album}] "
                          f"by [{current_song.artist}]")
                    the_current_song = current_song
                    # update now playing anyway (even if there is no duration)
                    if g_playing:
                        on_playing(current_song)


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
