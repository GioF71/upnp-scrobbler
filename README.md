# UPnP Scrobbler

A simple LAST.fm scrobbler for WiiM devices.  
It can now also scrobble to a subsonic server.  

## References

I started taking the code published in [this post](https://forum.wiimhome.com/threads/last-fm.3144/post-44653) as the starting point.  
It seems that I cannot get a valid link to the user profile on that board, but anyway the nickname is `cc_rider`.  
A big thank you goes to him/her for the code he/she shared.  
I then used [pylast](https://github.com/pylast/pylast), as suggested in that thread, for the actual operations on [last.fm](https://www.last.fm/).  
I also use [subsonic-connector](https://github.com/GioF71/subsonic-connector) for subsonic scrobbling.  

## Links

REPOSITORY TYPE|LINK
:---|:---
Git Repository|[GitHub](https://github.com/GioF71/upnp-scrobbler)
Docker Images|[Docker Hub](https://hub.docker.com/repository/docker/giof71/upnp-scrobbler)

## Task List

- [x] Scrobbling from a WiiM device as a generic UPnP Renderer
- [x] Scrobbling from a WiiM device when using Tidal Connect
- [x] Scrobbling to gmrender-resurrect ([Source](https://github.com/hzeller/gmrender-resurrect) and [Docker image](https://github.com/gioF71/gmrender-resurrect-docker)) as a generic UPnP Renderer
- [x] Scrobbling to mpd + upmpdcli in UPnP-AV mode
- [x] Scrobbling to a subsonic server
- [x] Enable "now playing" for subsonic
- [x] Enable song matching for subsonic
- [x] Allow multiple subsonic servers
- [ ] Scrobbling to listenbrainz
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
DEVICE_URL|Device URL of your UPnP Device, alternative to DEVICE_UDN and DEVICE_NAME (example: `http://192.168.1.7:49152/description.xml`)
DEVICE_UDN|Device identifier, alternative to DEVICE_URL and DEVICE_NAME (must match only one device)
DEVICE_NAME|Device friendly name, alternative to DEVICE_URL and DEVICE_UDN (must match only one device)
DEVICE_TIMEOUT_SEC_INITIAL|Int value, defaults to `5` seconds
DEVICE_TIMEOUT_SEC_DELTA|Int value, defaults to `5` seconds
DEVICE_TIMEOUT_SEC_MAX|Int value, defaults to `60` seconds
LAST_FM_API_KEY|Your LAST.fm api key, mandatory
LAST_FM_SHARED_SECRET|Your LAST.fm api key, mandatory
LAST_FM_USERNAME|Your LAST.fm account username, optional
LAST_FM_PASSWORD_HASH|Your LAST.fm account password encoded using md5, optional
LAST_FM_PASSWORD|Your LAST.fm account password in clear text, optional, used when LAST_FM_PASSWORD_HASH is not provided
ENABLE_NOW_PLAYING|Update `now playing` information if set to `yes` (default)
DURATION_THRESHOLD|Minimum duration required from scrobbling (unless at least half of the duration has elapsed), defaults to `240`
DUMP_UPNP_DATA|Additional logging for UPnP data, defaults to `no`
DUMP_EVENT_KEYS|Dump keys from each event keys, defaults to `no`
DUMP_EVENT_KEY_VALUES|Dump data from each event keys, defaults to `no`

## Running

The preferred way of running this application is through Docker.  

### Configuration directory

When using docker, the base configuration directory is `/config`. When running outside of docker, the code looks for the default config directory using the [`platformdirs`](https://github.com/tox-dev/platformdirs) library.  

#### LAST.fm configuration file

LAST.FM related variables can be stored in a file inside the `<config-directory>` volume, exacly at `<config-directory>/upnp-scrobbler/last.fm/last_fm_config.env`. Example:  

```text
LAST_FM_API_KEY=xxxx
LAST_FM_SHARED_SECRET=xxxx
# optional
LAST_FM_USERNAME=xxxx
# optional
LAST_FM_PASSWORD=xxxx
# optional
LAST_FM_PASSWORD_HASH=xxxx
```

#### Subsonic Configuration files

Subsonic related variables should be saved in files inside the `<config-directory>` volume, with files names like `<config-directory>/upnp-scrobbler/subsonic/<subsonic_key>.server.env`, and optionally `<config-directory>/upnp-scrobbler/subsonic/<subsonic_key>.credentials.env` (if you want to separate credentials).  
Example file names:  

```text
lightweight-music-server.server.env
lightweight-music-server.credentials.env
```

Example of content for the mentioned files:  

```text
SUBSONIC_BASE_URL=https://your-subsonic-server.your-domain.com
# legacy auth
SUBSONIC_LEGACY_AUTH=true
# there is an alias available for variable name SUBSONIC_LEGACYAUTH (it's named this way in upmpdcli)
# SUBSONIC_LEGACYAUTH=true
# optional port, by default it will be `443` if the base url starts with `https`, otherwise `80`
SUBSONIC_PORT=443
# optional server path
# SUBSONIC_SERVER_PATH=server-path
# optional enable now playing, defaults to true
# SUBSONIC_ENABLE_NOW_PLAYING=false
# SUBSONIC_ENABLE_SONG_MATCH=true
```

and:

```text
SUBSONIC_USERNAME=your-username
# there is an alias available for variable name SUBSONIC_USER (it's named this way in upmpdcli)
# SUBSONIC_USER=your-username
SUBSONIC_PASSWORD=your-password
```

You can collapse all the variables in one file for each subsonic configuration, but its name must be `<subsonic_key>.server.env` for each value given to `subsonic_key`.  

The subsonic configuration variables are listed in the following table:

NAME|DESCRIPTION
:---|:---
SUBSONIC_BASE_URL|Server base URL, e.g. https://navidrome.mydomain.com
SUBSONIC_PORT|Server port, will default to 443 or 80 depending on SUBSONIC_BASE_URL
SUBSONIC_SERVER_PATH|Optional server path
SUBSONIC_USERNAME|Server username
SUBSONIC_PASSWORD|Server password or key
SUBSONIC_LEGACY_AUTH|Legay authentication (`true` or `false`), defaults to `false`
SUBSONIC_ENABLE_SONG_MATCH|Allow to find the song by title, artist(s) and album, defaults to `true`
SUBSONIC_ENABLE_NOW_PLAYING|Allow to scrobble in Now Playing mode when a song is matched (as opposed to found using the id in the track url), defaults to `true`

### LAST.fm authentication

If username and password (hash or plaintext) are not provided, the application will prompt you to authorize the app.  
You will need to watch the logs, al least for the first run.  
Please note that API key and secret are still required.  

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
2025-11-17|Search subsonic tracks using the exact title, compare removing non alphanumeric characters
2025-10-26|Add support for "Now Playing" on subsonic (see [#16](https://github.com/GioF71/upnp-scrobbler/issues/16))
2025-10-26|Add support for "Now Playing" on subsonic (see [#14](https://github.com/GioF71/upnp-scrobbler/issues/14))
2025-10-10|Don't assume LAST.fm is configured (see [#12](https://github.com/GioF71/upnp-scrobbler/issues/12))
2025-09-14|Improved logging during authentication
2025-09-12|Trigger "Now playing" only if player state is actually playing
2025-08-10|Code style improvements
2025-08-09|Initial support for [gmrender-resurrect](https://github.com/hzeller/gmrender-resurrect)
2025-08-09|Increasing timeouts
2025-08-09|Fixed device search, would fail if first hit is not the expected one
2025-08-08|Allow to specify last.fm credentials using an external file (`last_fm_config.env`)
2025-08-08|Allow to specify device by udn (DEVICE_UDN)
2025-08-08|Allow to specify device by friendly name (DEVICE_NAME)
2024-12-23|Get transport state from LAST_CHANGE if not in TRANSPORT_STATE
2024-12-22|Rewrite for better linearity, should avoid sparse management of variables
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
