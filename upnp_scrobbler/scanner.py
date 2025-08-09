import asyncio
# import sys

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.client import UpnpDevice
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.utils import CaseInsensitiveDict


async def discover_dmr_devices(source, timeout) -> set[CaseInsensitiveDict]:
    """Discover DMR devices."""
    # Do the search, this blocks for timeout (4 seconds, default).
    discoveries = await DmrDevice.async_search(source=source, timeout=timeout)
    if not discoveries:
        # no device found
        return set()
    return discoveries


async def discover(timeout: int, source=("0.0.0.0", 0), dump_discovery: bool = False):
    discoveries: set[CaseInsensitiveDict] = await discover_dmr_devices(source=("0.0.0.0", 0), timeout=timeout)
    discovery: CaseInsensitiveDict
    for discovery in discoveries if discoveries else set():
        location: str = discovery["location"] if "location" in discovery else None
        print(f"Discovery found device at: [{location}] ...")
        if dump_discovery:
            await show_discovery(discovery)
    return discoveries


async def show_discoveries(discoveries: set[CaseInsensitiveDict]):
    print(discoveries)
    discovery: CaseInsensitiveDict
    for discovery in discoveries if discoveries else set():
        show_discovery(discovery)


async def show_discovery(d: CaseInsensitiveDict):
    location: str = d["location"] if "location" in d else None
    if location:
        requester = AiohttpRequester()
        factory = UpnpFactory(requester)
        # create a device
        device = await factory.async_create_device(location)
        if device:
            device_fn: str = device.friendly_name
            device_id: str = device.udn
            # print("Device: {}".format(device))
            print(f"Device name:[{device_fn}] udn:[{device_id}] url:[{location}]")
    else:
        print("Location is empty, nothing to do.")


async def get_device_url_by_name(device_name: str, timeout: int) -> list[str]:
    discoveries: set[CaseInsensitiveDict] = await discover(timeout=timeout)
    by_name: dict[str, list] = dict()
    current: CaseInsensitiveDict
    for current in discoveries if discoveries else set():
        # get location
        location: str = current["location"] if "location" in current else None
        if not location:
            continue
        # extract name
        requester = AiohttpRequester()
        factory = UpnpFactory(requester)
        # create a device
        device: UpnpDevice = await factory.async_create_device(location)
        if device:
            fn: str = device.friendly_name
            print(f"Found device with friendly name [{fn}]")
            if device_name == fn:
                print(f"Device [{device.udn}] matches friendly name [{fn}]")
                # does by_name already contain friendly name?
                device_list: list[str] = None
                if fn in by_name:
                    device_list: list[str] = by_name[fn]
                else:
                    device_list = []
                    by_name[fn] = device_list
                print(f"Adding location [{location}] for friendly_name [{fn}] -> ([{device.udn}])")
                device_list.append(location)
    return by_name[device_name] if device_name in by_name else []


async def get_device_url_by_udn(device_udn: str, timeout: int) -> list[str]:
    discoveries: set[CaseInsensitiveDict] = await discover(timeout=timeout)
    by_name: dict[str, list] = dict()
    current: CaseInsensitiveDict
    for current in discoveries if discoveries else set():
        # get location
        location: str = current["location"] if "location" in current else None
        if not location:
            continue
        # extract name
        requester = AiohttpRequester()
        factory = UpnpFactory(requester)
        # create a device
        device: UpnpDevice = await factory.async_create_device(location)
        if device:
            udn: str = device.udn
            print(f"Found device with udn [{udn}]")
            if device_udn.lower() == udn.lower():
                print(f"Device [{device.friendly_name}] matches udn [{device.udn}]")
                # does by_name already contain udn?
                device_list: list[str] = None
                if device_udn in by_name:
                    device_list: list[str] = by_name[device_udn]
                else:
                    device_list = []
                    by_name[device_udn] = device_list
                print(f"Adding location [{location}] for udn [{device_udn}] -> [{device.friendly_name}]")
                device_list.append(location)
    return by_name[device_udn] if device_udn in by_name else []


if __name__ == "__main__":
    asyncio.run(discover(timeout=5, dump_discovery=True))
