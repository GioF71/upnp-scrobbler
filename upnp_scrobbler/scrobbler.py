#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name

import asyncio
import json
import time
import xmltodict
import os
import datetime
import pylast
import socket
import webbrowser

from typing import Optional, Sequence, Callable

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable, UpnpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpResponseError, UpnpConnectionError
from async_upnp_client.profiles.dlna import dlna_handle_notify_last_change
from async_upnp_client.utils import get_local_ip
from async_upnp_client.const import DeviceInfo

from song import Song, copy_song, same_song
from player_state import PlayerState, get_player_state
from util import duration_str_to_sec
from event_name import EventName

import config
import constants
import scanner

key_title: str = "dc:title"
key_subtitle: str = "dc:subtitle"
key_artist: str = "upnp:artist"
key_album: str = "upnp:album"
key_duration: tuple[str, str] = ["res", "@duration"]

g_previous_song: Song = None
g_current_song: Song = None
g_last_scrobbled: Song = None

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


def song_to_short_string(song: Song) -> str:
    if song:
        return (f"Song [{song.title}] from [{song.album}] by [{song.artist}] "
                f"TrackUri set [{song.track_uri is not None}] "
                f"AvTransportUri set [{song.av_transport_uri is not None}] ")
    else:
        return "<NO_DATA>"


def song_to_string(song: Song) -> str:
    if song:
        return (f"Song [{song.title}] from [{song.album}] by [{song.artist}] "
                f"Duration [{song.duration}] "
                f"PlaybackStart [{song.playback_start}] "
                f"Subtitle [{song.subtitle}] "
                f"TrackUri [{song.track_uri}] "
                f"AvTransportUri [{song.av_transport_uri}]")
    else:
        return "<NO_DATA>"


def maybe_scrobble(current_song: Song) -> bool:
    global g_last_scrobbled
    if g_last_scrobbled and same_song(current_song, g_last_scrobbled):
        # too close in time?
        delta: float = current_song.playback_start - g_last_scrobbled.playback_start
        if delta < config.get_minimum_delta():
            print("Requesting a new scrobble for the same song again too early, not scrobbling")
            return False
    if execute_scrobble(current_song):
        g_last_scrobbled = copy_song(current_song)
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
        print(f"execute_scrobble we can scrobble [{song_to_short_string(current_song)}] "
              f"elapsed [{elapsed:.2f}] "
              f"duration [{song_duration:.2f}] "
              f"threshold [{config.get_duration_threshold()}] "
              f"over_threshold [{over_threshold}] "
              f"over_half [{over_half}]")
        last_fm_scrobble(current_song=current_song)
        print(f"Scrobble success for [{song_to_short_string(current_song)}]")
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
    last_fm_password: str = os.getenv("LAST_FM_PASSWORD")
    if last_fm_key and last_fm_secret and last_fm_username and (last_fm_password_hash or last_fm_password):
        return create_last_fm_network_legacy(
            last_fm_key=last_fm_key,
            last_fm_secret=last_fm_secret,
            last_fm_username=last_fm_username,
            last_fm_password_hash=last_fm_password_hash,
            last_fm_password=last_fm_password)
    elif last_fm_key and last_fm_secret:
        # create a new or use existing session key.
        return create_last_fm_network_session_key(
            last_fm_key=last_fm_key,
            last_fm_secret=last_fm_secret)
    else:
        # cannot enable last.fm
        # should be allowed only if last.fm is disabled
        return None


def get_last_fm_session_key_file_name() -> str:
    return os.path.join(
        config.get_app_config_dir(),
        constants.Constants.LAST_FM.value,
        constants.Constants.LAST_FM_SESSION_KEY.value)


def create_last_fm_network_session_key(
        last_fm_key: str,
        last_fm_secret: str) -> pylast.LastFMNetwork:
    session_key_dir = os.path.join(
        config.get_app_config_dir(),
        constants.Constants.LAST_FM.value)
    os.makedirs(name=session_key_dir, exist_ok=True)
    session_key_file_name = get_last_fm_session_key_file_name()
    network: pylast.LastFMNetwork = pylast.LastFMNetwork(last_fm_key, last_fm_secret)
    session_key_file_exists: bool = os.path.exists(session_key_file_name)
    print(f"LAST.fm session file exists [{session_key_file_exists}] at path [{session_key_file_name}]")
    # can we validate the LAST.fm connection?
    if not session_key_file_exists:
        skg: pylast.SessionKeyGenerator = pylast.SessionKeyGenerator(network)
        url = skg.get_web_auth_url()
        print(f"Please authorize this script to access your account: {url}\n")
        webbrowser.open(url)
        while True:
            try:
                session_key = skg.get_web_auth_session_key(url)
                with open(session_key_file_name, "w") as f:
                    print(f"Saving LAST.fm session file at path [{session_key_file_name}]")
                    f.write(session_key)
                break
            except pylast.WSError:
                time.sleep(1)
    else:
        session_key = open(session_key_file_name).read()
    network.session_key = session_key
    return network


def create_last_fm_network_legacy(
        last_fm_key: str,
        last_fm_secret: str,
        last_fm_username: str,
        last_fm_password_hash: str = None,
        last_fm_password: str = None) -> pylast.LastFMNetwork:
    if not last_fm_password_hash and not last_fm_password:
        raise Exception("One between last_fm_password_hash and last_fm_password must be provided")
    if not last_fm_password_hash:
        # try cleartext, not recommended
        last_fm_password_hash = pylast.md5(last_fm_password)
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


def metadata_to_new_current_song(items: dict[str, any], track_uri: str = None) -> Song:
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


def get_in_dict(from_dict: dict[str, any], path: list[str]) -> any:
    curr_obj: dict[str, any] = from_dict
    curr_path: str
    for curr_path in path:
        if isinstance(curr_obj, dict) and curr_path in curr_obj:
            curr_obj = curr_obj[curr_path]
        else:
            return None
    return curr_obj


def get_player_state_from_last_change(last_change_data: str) -> str:
    lcd_dict: dict = xmltodict.parse(last_change_data)
    transport_state: str = (lcd_dict["Event"]["InstanceID"]["TransportState"]["@val"]
                            if "Event" in lcd_dict
                            and "InstanceID" in lcd_dict["Event"]
                            and "TransportState" in lcd_dict["Event"]["InstanceID"]
                            and "@val" in lcd_dict["Event"]["InstanceID"]["TransportState"]
                            else None)
    return transport_state


def get_items(event_name: str, event_value: any) -> any:
    item_path: list[str] = ["DIDL-Lite", "item"]
    parsed: dict[str, any]
    try:
        parsed = xmltodict.parse(event_value)
    except Exception as ex:
        print(f"on_avtransport_event parse failed due to [{type(ex)}] [{ex}]")
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


def get_player_state_from_transport_state(sv_dict: dict[str, any]) -> PlayerState:
    if EventName.TRANSPORT_STATE.value in sv_dict:
        return get_player_state(sv_dict[EventName.TRANSPORT_STATE.value])
    else:
        return None


def service_variables_by_name(service_variables: Sequence[UpnpStateVariable]) -> dict[str, UpnpStateVariable]:
    result: dict[str, UpnpStateVariable] = dict()
    for sv in service_variables:
        result[sv.name] = sv.value
    return result


def get_new_metadata(sv_dict: dict[str, any]) -> Song:
    global g_current_song
    has_current_track_meta_data: bool = EventName.CURRENT_TRACK_META_DATA.value in sv_dict
    has_av_transport_uri_meta_data: bool = EventName.AV_TRANSPORT_URI_META_DATA.value in sv_dict
    # get metadata
    metadata_key: str = None
    if has_current_track_meta_data:
        metadata_key = EventName.CURRENT_TRACK_META_DATA.value
    elif has_av_transport_uri_meta_data:
        metadata_key = EventName.AV_TRANSPORT_URI_META_DATA.value
    print(f"Metadata available: [{metadata_key is not None}]")
    incoming_metadata: Song = None
    if metadata_key:
        g_items = get_items(metadata_key, sv_dict[metadata_key])
        incoming_metadata = metadata_to_new_current_song(g_items) if g_items else None
        if incoming_metadata is None or incoming_metadata.is_empty():
            print("Incoming incoming_metadata is missing or empty!")
            incoming_metadata = None
        return incoming_metadata if incoming_metadata else None


def display_player_state(state: PlayerState) -> str:
    return state.value if state else ''


class Subscription:

    def __init__(
            self,
            service_name: str,
            handler: Callable[[UpnpService, Sequence[UpnpStateVariable]], None],
            enabled: bool = False):
        self.__service_name: str = service_name
        self.__handler: Callable[[UpnpService, Sequence[UpnpStateVariable]], None] = handler
        self.__enabled: bool = enabled

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @property
    def service_name(self) -> str:
        return self.__service_name

    @property
    def handler(self) -> Callable[[UpnpService, Sequence[UpnpStateVariable]], None]:
        return self.__handler


def on_valid_rendering_control_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    sv_dict: dict[str, any] = service_variables_by_name(service_variables)
    print(f"on_valid_rendering_control_event: Keys in event [{sv_dict.keys()}]")


def on_valid_qplay_control_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    sv_dict: dict[str, any] = service_variables_by_name(service_variables)
    print(f"on_valid_qplay_control_event: Keys in event [{sv_dict.keys()}]")


def on_valid_connection_manager_control_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    sv_dict: dict[str, any] = service_variables_by_name(service_variables)
    print(f"on_valid_connection_manager_control_event: Keys in event [{sv_dict.keys()}]")


def get_current_player_state(sv_dict: dict[str, any]) -> PlayerState:
    # first, we try TRANSPORT_STATE
    result: PlayerState = PlayerState.UNKNOWN
    if EventName.TRANSPORT_STATE.value in sv_dict:
        print(f"Trying to get PlayerState from [{EventName.TRANSPORT_STATE.value}] ...")
        result = get_player_state_from_transport_state(sv_dict)
    elif EventName.LAST_CHANGE.value in sv_dict:
        print(f"Trying to get PlayerState from [{EventName.LAST_CHANGE.value}] ...")
        transport_state: str = get_player_state_from_last_change(sv_dict[EventName.LAST_CHANGE.value])
        if transport_state:
            result = get_player_state(transport_state)
    return result


def on_valid_avtransport_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    global g_player_state
    global g_items
    global g_current_song
    global g_previous_song
    global g_last_scrobbled
    sv_dict: dict[str, any] = service_variables_by_name(service_variables)
    print(f"on_valid_avtransport_event keys [{sv_dict.keys()}]")
    # must have transport state
    previous_player_state: PlayerState = g_player_state
    # see if we have a new player state
    curr_player_state: PlayerState = get_current_player_state(sv_dict)
    g_player_state = (curr_player_state
                      if curr_player_state and curr_player_state != PlayerState.UNKNOWN
                      else g_player_state)
    print(f"Player state [{display_player_state(previous_player_state)}] -> "
          f"[{display_player_state(g_player_state)}]")
    # get current track uri
    track_uri: str = (sv_dict[EventName.CURRENT_TRACK_URI.value]
                      if EventName.CURRENT_TRACK_URI.value in sv_dict
                      else None)
    if track_uri:
        print(f"Track URI = [{track_uri}]")
    # get av transport uri
    av_transport_uri: str = (sv_dict[EventName.AV_TRANSPORT_URI.value]
                             if EventName.AV_TRANSPORT_URI.value in sv_dict
                             else None)
    if av_transport_uri:
        print(f"AV Transport URI = [{av_transport_uri}]")
    # get metadata
    incoming_metadata: Song = get_new_metadata(sv_dict)
    metadata_is_new: bool = False
    todo_update_now_playing: bool = False
    todo_scrobble: bool = False
    song_to_be_scrobbled: Song = None
    if incoming_metadata:
        if track_uri:
            incoming_metadata.track_uri = track_uri
        if av_transport_uri:
            incoming_metadata.av_transport_uri = av_transport_uri
        empty_g_current_song: bool = g_current_song is None
        metadata_is_new = ((incoming_metadata is not None) and
                           (g_current_song is None or not same_song(g_current_song, incoming_metadata)))
        print(f"incoming_metadata: "
              f"empty g_current_song: [{empty_g_current_song}] "
              f"metadata_is_new: [{metadata_is_new}] -> "
              f"[{song_to_string(incoming_metadata)}]")
        if metadata_is_new:
            print(f"Arming Now Playing because metadata_is_new [{song_to_string(incoming_metadata)}] ...")
            todo_update_now_playing = True
            # consider arming scrobbling
            if not empty_g_current_song:
                # we can scrobble the g_current_song
                print(f"Arming Scrobble because g_current_song not is empty [{song_to_string(g_current_song)}] ...")
                todo_scrobble = True
                song_to_be_scrobbled = copy_song(g_current_song)
            else:
                print("NOT arming scrobble because g_current_song is empty")
        else:
            print(f"Not arming Now Playing because metadata_is_new is [{metadata_is_new}]")
        # store g_current_song if not the same ...
        if empty_g_current_song or not same_song(g_current_song, incoming_metadata):
            print(f"Setting g_previous_song to [{song_to_short_string(incoming_metadata)}] ...")
            previous_song: Song = copy_song(g_current_song) if g_current_song else None
            g_current_song = copy_song(incoming_metadata)
            if previous_song:
                print(f"Setting g_previous_song to [{song_to_short_string(previous_song)}] ...")
                # update g_previous_song and g_current_song
                g_previous_song = copy_song(previous_song)
    else:
        print("Incoming incoming_metadata is None")
    # examing states
    if PlayerState.PLAYING.value == g_player_state.value:
        if (not todo_scrobble) and (metadata_is_new and incoming_metadata and g_previous_song):
            print(f"Arming scrobble of previous_song [{song_to_string(g_previous_song)}] "
                  f"while handling [{PlayerState.PLAYING.value}] ...")
            todo_scrobble = True
            song_to_be_scrobbled = copy_song(g_previous_song)
    elif PlayerState.STOPPED.value == g_player_state.value:
        if not todo_scrobble and g_current_song is not None:
            print(f"Arming scrobble of current song [{song_to_string(g_current_song)}] "
                  f"because of the {PlayerState.STOPPED.value} state ...")
            todo_scrobble = True
            song_to_be_scrobbled = copy_song(g_current_song)
    # Execute armed actions
    if todo_update_now_playing:
        on_playing(incoming_metadata)
    if todo_scrobble:
        maybe_scrobble(current_song=song_to_be_scrobbled)


def on_rendering_control_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    """Handle a UPnP RenderingControl event."""
    print(f"on_rendering_control_event [{service.service_type}]")
    sv_dict: dict[str, any] = service_variables_by_name(service_variables)
    print(f"on_rendering_control_event: Keys in event [{sv_dict.keys()}]")
    if config.get_dump_upnp_data():
        print(f"on_rendering_control_event: service_variables=[{service_variables}]")
    if (len(service_variables) == 1 and
            service_variables[0].name == EventName.LAST_CHANGE.value):
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)
    on_valid_rendering_control_event(service, service_variables)


def on_qplay_control_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    """Handle a UPnP QPlay event."""
    print(f"on_qplay_control_event [{service.service_type}]")
    sv_dict: dict[str, any] = service_variables_by_name(service_variables)
    print(f"on_qplay_control_event: Keys in event [{sv_dict.keys()}]")
    if config.get_dump_upnp_data():
        print(f"on_qplay_control_event: service_variables=[{service_variables}]")
    if (len(service_variables) == 1 and
            service_variables[0].name == EventName.LAST_CHANGE.value):
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)
    on_valid_qplay_control_event(service, service_variables)


def on_connection_manager_control_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    """Handle a UPnP QPlay event."""
    print(f"on_connection_manager_control_event [{service.service_type}]")
    sv_dict: dict[str, any] = service_variables_by_name(service_variables)
    print(f"on_connection_manager_control_event: Keys in event [{sv_dict.keys()}]")
    if config.get_dump_upnp_data():
        print(f"on_connection_manager_control_event: service_variables=[{service_variables}]")
    if (len(service_variables) == 1 and
            service_variables[0].name == EventName.LAST_CHANGE.value):
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)
    on_valid_connection_manager_control_event(service, service_variables)


def on_avtransport_event(
        service: UpnpService,
        service_variables: Sequence[UpnpStateVariable]) -> None:
    """Handle a UPnP AVTransport event."""
    # special handling for DLNA LastChange state variable
    print(f"on_avtransport_event [{service.service_type}]")
    sv_dict: dict[str, any] = service_variables_by_name(service_variables)
    if config.get_dump_event_keys():
        print(f"on_avtransport_event Keys in event [{sv_dict.keys()}]")
    if config.get_dump_event_key_values():
        event_key: str
        for event_key in sv_dict.keys():
            print(f"Event Key [{event_key}] -> [{sv_dict[event_key]}]")
    if config.get_dump_upnp_data():
        print(f"on_avtransport_event service_variables [{service_variables}]")
    if (len(service_variables) == 1 and
            service_variables[0].name == EventName.LAST_CHANGE.value):
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)
    on_valid_avtransport_event(service, service_variables)


subscription_list: list[Subscription] = [
    Subscription("AVTransport", on_avtransport_event, True),
    Subscription("RenderingControl", on_rendering_control_event),
    Subscription("QPlay", on_qplay_control_event),
    Subscription("ConnectionManager", on_connection_manager_control_event)]


async def subscribe(description_url: str, subscription_list: list[Subscription]) -> None:
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
    print(f"Device url [{device.device_url}]")
    print(f"Device type [{device.device_type}]")
    device_info: DeviceInfo = device.device_info
    print(f"Device info [{device.device_info}]")
    print(f"Device Type: {device_info.device_type}")
    print(f"Device Friendly name: {device_info.friendly_name}")
    print(f"Device Model Name: {device_info.model_name}")
    print(f"Device Model Description: {device_info.model_description}")
    print(f"Available services for device: [{device.services.keys()}]")
    source = (get_local_ip(device.device_url), 0)
    print(f"subscribe: source=[{source}]")
    server = AiohttpNotifyServer(device.requester, source=source)
    await server.async_start_server()
    # gather all wanted services
    services = []
    # for service_name in service_names:
    subscription: Subscription
    for subscription in subscription_list:
        if not subscription.enabled:
            print(f"Skipping disabled subscription [{subscription.service_name}]")
            continue
        print(f"Processing enabled subscription [{subscription.service_name}]")
        print(f"subscribe: Getting service [{subscription.service_name}] from device ...")
        service = service_from_device(device, subscription.service_name)
        if not service:
            print(f"Unknown service: {subscription.service_name}, this might be fatal.")
            # sys.exit(1)
            continue
        print(f"subscribe: Got service [{subscription.service_name}] from device.")
        service.on_event = subscription.handler
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
    device_timeout_sec_initial: int = int(os.getenv("DEVICE_TIMEOUT_SEC_INITIAL", "5"))
    device_timeout_sec_delta: int = int(os.getenv("DEVICE_TIMEOUT_SEC_DELTA", "5"))
    device_timeout_sec_max: int = int(os.getenv("DEVICE_TIMEOUT_SEC_DELTA", "120"))
    device_timeout_sec: int = device_timeout_sec_initial
    cfg_device_url: str = os.getenv("DEVICE_URL")
    cfg_device_udn: str = os.getenv("DEVICE_UDN")
    cfg_device_name: str = os.getenv("DEVICE_NAME")
    if not (cfg_device_url or cfg_device_udn or cfg_device_name):
        # misconfiguration
        print("Please specify one among DEVICE_URL, DEVICE_UDN or DEVICE_NAME!")
        return None
    while True:
        print(f"Current timeout is [{device_timeout_sec}] second(s)")
        device_url: str = None
        if cfg_device_url:
            print(f"Using specified device url [{cfg_device_url}]")
            device_url = cfg_device_url
        if not device_url and cfg_device_udn:
            print(f"Trying to find device by udn [{cfg_device_udn}]")
            device_url_list: list[str] = await scanner.get_device_url_by_udn(
                device_udn=cfg_device_udn,
                timeout=device_timeout_sec)
            print(f"Devices for [{cfg_device_udn}] -> [{device_url_list}]")
            url_list_len: str = len(device_url_list if device_url_list else [])
            if url_list_len == 1:
                # one match
                device_url = device_url_list[0]
            else:
                # missing, or more than one
                print(f"There are [{url_list_len}] devices matching udn [{cfg_device_udn}], expecting 1")
        elif not device_url and cfg_device_name:
            print(f"Trying to find device by friendly name [{cfg_device_name}]")
            device_url_list: list[str] = await scanner.get_device_url_by_name(
                device_name=cfg_device_name,
                timeout=device_timeout_sec)
            print(f"Devices for [{cfg_device_name}] -> [{device_url_list}]")
            url_list_len: str = len(device_url_list if device_url_list else [])
            if url_list_len == 1:
                # one match
                device_url = device_url_list[0]
            else:
                # missing, or more than one
                print(f"There are [{url_list_len}] devices matching [{cfg_device_name}], expecting 1")
        # did we get the device_url?
        if not device_url:
            # raise Exception("We need a DEVICE_URL!")
            if device_timeout_sec < device_timeout_sec_max:
                device_timeout_sec += device_timeout_sec_delta
            print("Device not found, retrying ...")
        if device_url:
            device_timeout_sec = device_timeout_sec_initial
            print(f"Selected device with URL [{device_url}] ...")
            try:
                await subscribe(
                    description_url=device_url,
                    subscription_list=subscription_list)
            except Exception as ex:
                print(f"An error occurred [{type(ex)}] [{ex}], retrying ...")


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
    last_fm_config_dir: str = config.get_lastfm_config_dir()
    if os.path.exists(os.path.join(last_fm_config_dir, constants.Constants.LAST_FM_CONFIG.value)):
        config.load_env_file(os.path.join(last_fm_config_dir, constants.Constants.LAST_FM_CONFIG.value))
    # early initializtion of last.fm network
    create_last_fm_network()
    host_ip: str = get_ip()
    print(f"Running on [{host_ip}]")
    print(f"Now Playing enabled: [{config.get_enable_now_playing()}]")
    print(f"Dump UPnP Data: [{config.get_dump_upnp_data()}]")
    print(f"Dump UPnP Event Key/Values: [{config.get_dump_event_key_values()}]")
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
