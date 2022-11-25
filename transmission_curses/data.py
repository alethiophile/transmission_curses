#!python3

from __future__ import annotations

import attr, datetime
from enum import Enum, Flag

from typing import Union, List, Dict, Any, Optional

class TorrentStatus(Enum):
    STOPPED = 0         # Torrent is stopped
    CHECK_WAIT = 1      # Queued to check files
    CHECK = 2           # Checking files
    DOWNLOAD_WAIT = 3   # Queued to download
    DOWNLOAD = 4        # Downloading
    SEED_WAIT = 5       # Queued to seed
    SEED = 6            # Seeding

class TorrentPriority(Enum):
    LOW = -1
    NORMAL = 0
    HIGH = 1

class TorrentSeedMode(Enum):
    # this means go with the global default setting
    GLOBAL = 0
    LIMITED = 1
    UNLIMITED = 2

@attr.s(auto_attribs=True)
class TorrentInfo:
    """Information about a torrent, sufficient to display its status in the listing
    page."""

    # A unique ID for this torrent. Must be unique within all torrents
    # currently added to the backend. In Transmission, this is the int id.
    id: Union[str, int]
    name: str
    download_dir: str
    status: TorrentStatus
    tracker_stats: List[TrackerStatus]
    desired_available: int
    rate_download: int
    rate_upload: int
    eta: int
    upload_ratio: float
    size_when_done: int
    have_valid: int
    have_unchecked: int
    added_date: datetime.datetime
    uploaded_ever: int
    error_string: str
    recheck_progress: float
    peers_connected: int
    upload_limit: Optional[int]
    download_limit: Optional[int]
    upload_limited: bool
    download_limited: bool
    bandwidth_priority: TorrentPriority
    peers_sending: int
    peers_receiving: int
    ratio_limit: float
    ratio_mode: TorrentSeedMode
    private: bool
    magnet_link: str
    queue_position: int
    hash_string: str
    percent_done: float

    @classmethod
    def from_transmission_dict(cls, dct: Dict[str, Any]) -> TorrentInfo:
        return cls(
            id=dct['id'],
            name=dct['name'],
            download_dir=dct['downloadDir'],
            status=TorrentStatus(dct['status']),
            tracker_stats=[TrackerStatus(i) for i in dct['trackerStats']],
            desired_available=dct['desiredAvailable'],
            rate_download=dct['rateDownload'],
            rate_upload=dct['rateUpload'],
            eta=dct['eta'],
            upload_ratio=dct['uploadRatio'],
            size_when_done=dct['sizeWhenDone'],
            have_valid=dct['haveValid'],
            have_unchecked=dct['haveUnchecked'],
            added_date=datetime.datetime.fromtimestamp(dct['addedDate']),
            uploaded_ever=dct['uploadedEver'],
            error_string=dct['errorString'],
            recheck_progress=dct['recheckProgress'],
            peers_connected=dct['peersConnected'],
            upload_limit=dct['uploadLimit'] if dct['uploadLimited'] else None,
            download_limit=(dct['downloadLimit'] if dct['downloadLimited']
                            else None),
            upload_limited=dct['uploadLimited'],
            download_limited=dct['downloadLimited'],
            bandwidth_priority=TorrentPriority(dct['bandwidthPriority']),
            peers_sending=dct['peersSendingToUs'],
            peers_receiving=dct['peersGettingFromUs'],
            ratio_limit=dct['seedRatioLimit'],
            ratio_mode=TorrentSeedMode(dct['seedRatioMode']),
            private=dct['isPrivate'],
            magnet_link=dct['magnetLink'],
            queue_position=dct['queuePosition'],
            hash_string=dct['hashString'],
            percent_done=dct['percentDone'],
        )

class TrackerConnectState(Enum):
    INACTIVE = 0      # not planning to announce/scrape
    WAITING = 1       # waiting to announce/scrape at scheduled time
    QUEUED = 2        # announce/scrape queued
    ACTIVE = 3        # announce/scrape ongoing

@attr.s(auto_attribs=True)
class TrackerStatus:
    """Information about the current status of a torrent relative to a given
    tracker."""

    announce_url: str
    announce_state: TrackerConnectState
    download_count: int
    has_announced: bool
    has_scraped: bool
    host: str
    id: Union[int, str]
    is_backup: bool
    last_announce_peer_count: int
    last_announce_result: str
    # time last announce started
    last_announce_start_time: datetime.datetime
    last_announce_succeeded: bool
    # time last announce finished
    last_announce_time: datetime.datetime
    last_announce_timed_out: bool
    last_scrape_result: str
    last_scrape_start_time: datetime.datetime
    last_scrape_succeeded: bool
    last_scrape_time: datetime.datetime
    last_scrape_timed_out: bool
    leech_count: int
    next_announce_time: datetime.datetime
    next_scrape_time: datetime.datetime
    scrape_url: str
    scrape_state: TrackerConnectState
    seed_count: int
    tier: int

    @classmethod
    def from_transmission_dict(cls, dct: Dict[str, Any]) -> TrackerStatus:
        return cls(
            announce_url=dct['announce'],
            announce_state=TrackerConnectState(dct['announceState']),
            download_count=dct['downloadCount'],
            has_announced=dct['hasAnnounced'],
            has_scraped=dct['hasScraped'],
            host=dct['host'],
            id=dct['id'],
            is_backup=dct['isBackup'],
            last_announce_peer_count=dct['lastAnnouncePeerCount'],
            last_announce_result=dct['lastAnnounceResult'],
            last_announce_start_time=datetime.datetime.fromtimestamp(
                dct['lastAnnounceStartTime']),
            last_announce_succeeded=dct['lastAnnounceSucceeded'],
            last_announce_time=datetime.datetime.fromtimestamp(
                dct['lastAnnounceTime']),
            last_announce_timed_out=dct['lastAnnounceTimedOut'],
            last_scrape_result=dct['lastScrapeResult'],
            last_scrape_start_time=datetime.datetime.fromtimestamp(
                dct['lastScrapeStartTime']),
            last_scrape_succeeded=dct['lastScrapeSucceeded'],
            last_scrape_time=datetime.datetime.fromtimestamp(
                dct['lastScrapeTime']),
            last_scrape_timed_out=dct['lastScrapeTimedOut'],
            leech_count=dct['leecherCount'],
            next_announce_time=datetime.datetime.fromtimestamp(
                dct['nextAnnounceTime']),
            next_scrape_time=datetime.datetime.fromtimestamp(
                dct['nextScrapeTime']),
            scrape_url=dct['scrape'],
            scrape_state=TrackerConnectState(dct['scrapeState']),
            seed_count=dct['seederCount'],
            tier=dct['tier'],
        )

class ScheduledDay(Flag):
    SUNDAY = (1 << 0)
    MONDAY = (1 << 1)
    TUESDAY = (1 << 2)
    WEDNESDAY = (1 << 3)
    THURSDAY = (1 << 4)
    FRIDAY = (1 << 5)
    SATURDAY = (1 << 6)
    WEEKDAYS = (MONDAY | TUESDAY | WEDNESDAY | THURSDAY | FRIDAY)
    WEEKENDS = (SATURDAY | SUNDAY)
    ALL_DAYS = (WEEKDAYS | WEEKENDS)

@attr.s(auto_attribs=True)
class SessionSettings:
    """Information about the current global settings."""

    alt_speed_down: int
    alt_speed_enabled: bool
    alt_speed_time_begin: datetime.time
    alt_speed_time_enabled: bool
    alt_speed_time_end: datetime.time
    alt_speed_time_day: ScheduledDay
    alt_speed_up: int
    blocklist_url: str
    blocklist_enabled: bool
    blocklist_size: int
    cache_size: int
    config_dir: str
    download_dir: str
    download_queue_size: int
    download_queue_enabled: bool
    dht_enabled: bool
    
