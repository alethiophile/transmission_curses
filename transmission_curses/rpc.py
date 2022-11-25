#!python3

import asks

from typing import Dict, Any, Tuple, Optional, List, Union

class RPCError(Exception):
    def __init__(self, *args, rv=None):
        self.return_dict = rv
        super().__init__(self, *args)

def raise_for_result(rv: Dict[str, Any]) -> None:
    if rv['result'] == 'success':
        return
    raise RPCError("Error: " + rv['result'], rv=rv)

class TransmissionConnection:
    STATUS_STOPPED       = 0   # Torrent is stopped
    STATUS_CHECK_WAIT    = 1   # Queued to check files
    STATUS_CHECK         = 2   # Checking files
    STATUS_DOWNLOAD_WAIT = 3   # Queued to download
    STATUS_DOWNLOAD      = 4   # Downloading
    STATUS_SEED_WAIT     = 5   # Queued to seed
    STATUS_SEED          = 6   # Seeding

    def __init__(self, host: str, port: int = 9091,
                 auth: Optional[Tuple[str, str]] = None) -> None:
        self.session = asks.Session(connections=5)
        self.url = f'http://{host}:{port}/transmission/rpc'
        self.auth = auth
        self.sess_id = None

    async def send_request(self, method: str,
                           args: Dict[str, Any],
                           retry: bool = False) -> Dict[str, Any]:
        # tremc uses the tag field specified by Transmission, but I cannot for
        # the life of me fathom why (some kind of demented async handling?)

        # anyway, I won't bother, it's useless; if you want multiple requests
        # in flight at once, call send_request in different tasks
        hdr: Dict[str, str] = {}
        if self.sess_id:
            hdr['X-Transmission-Session-Id'] = self.sess_id

        req_args = { 'headers': hdr }
        if self.auth:
            req_args['auth'] = asks.BasicAuth(self.auth)

        data = { 'method': method, 'arguments': args }
        r = await self.session.post(self.url, json=data, **req_args)

        if r.status_code == 409 and not retry:
            # Transmission's anti-CSRF code
            self.sess_id = r.headers['X-Transmission-Session-Id']
            return await self.send_request(method, args, retry=True)
        r.raise_for_status()

        rv = r.json()
        raise_for_result(rv)
        return rv

    get_torrents_fields = [
        "id", "name", "downloadDir", "status", "trackerStats",
        "desiredAvailable", "rateDownload", "rateUpload", "eta",
        "uploadRatio", "sizeWhenDone", "haveValid", "haveUnchecked",
        "addedDate", "uploadedEver", "errorString", "recheckProgress",
        "peersConnected", "uploadLimit", "downloadLimit", "uploadLimited",
        "downloadLimited", "bandwidthPriority", "peersSendingToUs",
        "peersGettingFromUs", "seedRatioLimit", "seedRatioMode", "isPrivate",
        "magnetLink", "queuePosition", "hashString", "percentDone"
    ]

    async def get_torrents(self, torrents: Union[List[Union[int, str]],
                                                 int, str, None] = None,
                           fields: List[str] =
                           get_torrents_fields) -> List[Dict[str, Any]]:
        args: Dict[str, Any] = { 'fields': fields.copy() }
        if torrents is not None:
            args['ids'] = torrents
        rv = await self.send_request('torrent-get', args)
        return rv['arguments']['torrents']

    get_session_fields = [
        # number     | max global download speed (KBps)
        "alt-speed-down",
        # boolean    | true means use the alt speeds
        "alt-speed-enabled",
        # number | when to turn on alt speeds (units: minutes after midnight)
        "alt-speed-time-begin",
        # boolean    | true means the scheduled on/off times are used
        "alt-speed-time-enabled",
        # number     | when to turn off alt speeds (units: same)
        "alt-speed-time-end",
        # number     | what day(s) to turn on alt speeds (look at tr_sched_day)
        "alt-speed-time-day",
        # number     | max global upload speed (KBps)
        "alt-speed-up",
        # string     | location of the blocklist to use for "blocklist-update"
        "blocklist-url",
        # boolean    | true means enabled
        "blocklist-enabled",
        # number     | number of rules in the blocklist
        "blocklist-size",
        # number     | maximum size of the disk cache (MB)
        "cache-size-mb",
        # string     | location of transmission's configuration directory
        "config-dir",
        # string     | default path to download torrents
        "download-dir",
        # number | max number of torrents to download at once (see
        # download-queue-enabled)
        "download-queue-size",
        # boolean | if true, limit how many torrents can be downloaded at once
        "download-queue-enabled",
        # boolean    | true means allow dht in public torrents
        "dht-enabled",
        # string     | "required", "preferred", "tolerated"
        "encryption",
        # number | torrents we're seeding will be stopped if they're idle for
        # this long
        "idle-seeding-limit",
        # boolean | true if the seeding inactivity limit is honored by default
        "idle-seeding-limit-enabled",
        # string     | path for incomplete torrents, when enabled
        "incomplete-dir",
        # boolean    | true means keep torrents in incomplete-dir until done
        "incomplete-dir-enabled",
        # boolean    | true means allow Local Peer Discovery in public torrents
        "lpd-enabled",
        # number     | maximum global number of peers
        "peer-limit-global",
        # number     | maximum global number of peers
        "peer-limit-per-torrent",
        # boolean    | true means allow pex in public torrents
        "pex-enabled",
        # number     | port number
        "peer-port",
        # boolean    | true means pick a random peer port on launch
        "peer-port-random-on-start",
        # boolean    | true means enabled
        "port-forwarding-enabled",
        # boolean    | whether or not to consider idle torrents as stalled
        "queue-stalled-enabled",
        # number | torrents that are idle for N minuets aren't counted toward
        # seed-queue-size or download-queue-size
        "queue-stalled-minutes",
        # boolean    | true means append ".part" to incomplete files
        "rename-partial-files",
        # number     | the current RPC API version
        "rpc-version",
        # number     | the minimum RPC API version supported
        "rpc-version-minimum",
        # string     | filename of the script to run
        "script-torrent-done-filename",
        # boolean    | whether or not to call the "done" script
        "script-torrent-done-enabled",
        # double     | the default seed ratio for torrents to use
        "seedRatioLimit",
        # boolean    | true if seedRatioLimit is honored by default
        "seedRatioLimited",
        # number | max number of torrents to uploaded at once (see
        # seed-queue-enabled)
        "seed-queue-size",
        # boolean    | if true, limit how many torrents can be uploaded at once
        "seed-queue-enabled",
        # number     | max global download speed (KBps)
        "speed-limit-down",
        # boolean    | true means enabled
        "speed-limit-down-enabled",
        # number     | max global upload speed (KBps)
        "speed-limit-up",
        # boolean    | true means enabled
        "speed-limit-up-enabled",
        # boolean    | true means added torrents will be started right away
        "start-added-torrents",
        # boolean | true means the .torrent file of added torrents will be
        # deleted
        "trash-original-torrent-files",
        # object     | see below
        "units",
        # boolean    | true means allow utp
        "utp-enabled",
        # string     | long version string "$version ($revision)"
        "version",
    ]

    async def get_session(self, fields: List[str] =
                          get_session_fields) -> Dict[str, Any]:
        args: Dict[str, Any] = {}
        if fields:
            args['fields'] = fields.copy()
        rv = await self.send_request('session-get', args)
        return rv['arguments']

    async def get_session_stats(self) -> Dict[str, Any]:
        rv = await self.send_request('session-stats', {})
        return rv['arguments']
