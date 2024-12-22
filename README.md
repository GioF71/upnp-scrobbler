# UPnP Scrobbler

A simple LAST.fm scrobbler for WiiM devices.

## References

I started taking the code published in [this post](https://forum.wiimhome.com/threads/last-fm.3144/post-44653) as the starting point.  
It seems that I cannot get a valid link to the user profile on that board, but anyway the nickname is `cc_rider`.  
A big thank you goes to him/her for the code he/she shared.  
I then used [pylast](https://github.com/pylast/pylast), as suggested in that thread, for the actual operations on [last.fm](https://www.last.fm/).  

## Links

REPOSITORY TYPE|LINK
:---|:---
Git Repository|[GitHub](https://github.com/GioF71/upnp-scrobbler)
Docker Images|[Docker Hub](https://hub.docker.com/repository/docker/giof71/upnp-scrobbler)

## Task List

- [x] Scrobbling to last.fm from a WiiM device, using Tidal Connect
- [x] Scrobbling to last.fm from a WiiM device, using it as a generic UPnP Renderer
- [ ] Scrobbling to last.fm from gmrenderer-resurrect ([Source](https://github.com/hzeller/gmrender-resurrect) and [Docker image](https://github.com/gioF71/gmrender-resurrect-docker)), using it as a generic UPnP Renderer
- [ ] Scrobbling to libre.fm

## Build

You can build the docker image by typing:

```text
docker build . -t giof71/upnp-scrobbler
```

## Configuration

### Create your API key and secret

Open your browser at [this](https://www.last.fm/api/account/create), follow the instruction and accurately store the generated values.  
Those will be needed for the configuration.

### Environment Variables

NAME|DESCRIPTION
:---|:---
DEVICE_URL|Device URL of your UPnP Device (example: `http://192.168.1.7:49152/description.xml`)
LAST_FM_API_KEY|Your LAST.fm api key
LAST_FM_SHARED_SECRET|Your LAST.fm api key
LAST_FM_USERNAME|Your LAST.fm account username
LAST_FM_PASSWORD_HASH|Your LAST.fm account password encoded using md5
LAST_FM_PASSWORD|Your LAST.fm account password in clear text, used when LAST_FM_PASSWORD_HASH is not provided
ENABLE_NOW_PLAYING|Update `now playing` information if set to `yes` (default)
DURATION_THRESHOLD|Minimum duration required from scrobbling (unless at least half of the duration has elapsed), defaults to `240`

## Running

The preferred way of running this application is through Docker.  

### Sample compose file

Here is a simple compose file, valid for a WiiM device:

```text
---
version: "3"

services:
  scrobbler:
    image: giof71/upnp-scrobbler:latest
    container_name: wiim-scrobbler
    network_mode: host
    environment:
      - DEVICE_URL=http://192.168.1.7:49152/description.xml
      - LAST_FM_API_KEY=your-lastfm-api-key
      - LAST_FM_SHARED_SECRET=your-lastfm-api-secret
      - LAST_FM_USERNAME=your-lastfm-username
      - LAST_FM_PASSWORD_HASH=your-lastfm-md5-hashed-password
    restart: unless-stopped
```

It is advisable to put the variable values in a .env file in the same directory with this `docker-compose.yaml` file.  
Start the container with the following:

`docker-compose up -d`

## Change history

DATE|DESCRIPTION
:---|:---
2024-12-22|Avoid to require a g_previous_song in order to trigger a scrobble
2024-12-22|Remove handling of impossible situation
2024-12-22|Catch empty metadata
2024-12-22|Don't consider track_uri as a difference between tracks
2024-12-22|Add logs on maybe_scrobble in order to verify calculations
2024-12-22|Explicitly return None in get_items
2024-12-22|Add logs on maybe_scrobble in order to verify calculations
2024-12-22|Add timestamp to log lines, more logging
2024-12-21|Add log before scrobbling when metadata changes
2024-12-21|Scrobble when metadata changes
2024-12-20|More granular handling of events
2024-12-19|Algorithm reviewed, should be working now
2024-12-18|Now playing is executed when appropriate only
2024-12-18|Code refactored
2024-12-11|Log host ip
2024-12-10|Add debug logging, to be refined
2024-11-29|Improved general reliability and management of duration
2024-11-28|Fixed parsing of duration
2024-03-26|Initial release
