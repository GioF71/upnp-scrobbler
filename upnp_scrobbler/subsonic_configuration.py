from subsonic_connector.configuration import ConfigurationInterface as SubsonicConnectorConfigurationInterface


class ScrobblerSubsonicConfiguration:

    def __init__(
            self,
            subsonic_key: str,
            base_url: str,
            port: int,
            username: str,
            password: str,
            server_path: str,
            legacy_auth: bool,
            enable_now_playing: bool,
            allow_match: bool):
        self.__subsonic_key: str = subsonic_key
        self.__base_url: str = base_url
        self.__port: int = port
        self.__username: str = username
        self.__password: str = password
        self.__server_path: str = server_path
        self.__legacy_auth: bool = legacy_auth
        self.__enable_now_playing: bool = enable_now_playing
        self.__allow_match: bool = allow_match

    @property
    def subsonic_key(self) -> str:
        return self.__subsonic_key

    @property
    def base_url(self) -> str:
        return self.__base_url

    @property
    def port(self) -> int:
        return self.__port

    @property
    def username(self) -> str:
        return self.__username

    @property
    def password(self) -> str:
        return self.__password

    @property
    def server_path(self) -> str:
        return self.__server_path

    @property
    def legacy_auth(self) -> bool:
        return self.__legacy_auth

    @property
    def enable_now_playing(self) -> bool:
        return self.__enable_now_playing

    @property
    def allow_match(self) -> bool:
        return self.__allow_match


class SubsonicConnectorConfiguration(SubsonicConnectorConfigurationInterface):

    def __init__(self, cfg: ScrobblerSubsonicConfiguration):
        self.__cfg: ScrobblerSubsonicConfiguration = cfg
        self.__port: int = cfg.port if cfg.port else (443 if self.__cfg.base_url.startswith("https") else 80)

    def getBaseUrl(self) -> str:
        return self.__cfg.base_url

    def getPort(self) -> str:
        return str(self.__port)

    def getServerPath(self) -> str:
        return self.__cfg.server_path

    def getUserName(self) -> str:
        return self.__cfg.username

    def getPassword(self) -> str:
        return self.__cfg.password

    def getLegacyAuth(self) -> bool:
        return self.__cfg.legacy_auth

    def getUserAgent(self) -> str:
        return "upnp-scrobbler"

    def getApiVersion(self) -> str:
        return "1.16.1"

    def getAppName(self) -> str:
        return "upnp-scrobbler"
