#!python3

from __future__ import annotations

import urwid
from .rpc import TransmissionConnection
from .util import ColSplitAttrMap, render_bytes, output, render_time

from typing import Optional, Dict, Tuple, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    # to satisfy mypy
    from .console import ConsoleMain

class TorrentEntry(urwid.WidgetWrap):
    status_text = {
        TransmissionConnection.STATUS_STOPPED: 'stopped',
        TransmissionConnection.STATUS_CHECK_WAIT: 'will verify',
        TransmissionConnection.STATUS_CHECK: 'verifying',
        TransmissionConnection.STATUS_DOWNLOAD_WAIT: 'will download',
        TransmissionConnection.STATUS_DOWNLOAD: 'downloading',
        TransmissionConnection.STATUS_SEED_WAIT: 'will seed',
        TransmissionConnection.STATUS_SEED: 'seeding',
    }

    @classmethod
    def get_status_text(cls, te):
        s = cls.status_text.get(te['status'], 'unknown state')
        if s == 'downloading':
            if te['rateDownload'] == 0:
                s = 'idle'
            s += f" ({round(te['percentDone'] * 100.0, 2)}%)"
        if s in ['will seed', 'will download']:
            s += f" ({te['queuePosition']})"
        return s

    def __init__(self, te, compact=False, parent=None):
        self.parent = parent
        status = self.get_status_text(te)
        done_color = ('idle_done' if status.startswith('idle') else
                      'downloading_done' if status.startswith('downloading')
                      else
                      'seeding_done' if status.startswith('seeding') else None)
        seed_count = (max(i['seederCount'] for i in te['trackerStats']) if
                      te['trackerStats'] else '?')
        if seed_count == -1: seed_count = '?'
        leech_count = (max(i['leecherCount'] for i in te['trackerStats']) if
                       te['trackerStats'] else '?')
        if leech_count == -1: leech_count = '?'
        w = urwid.Pile([
            ('pack', ColSplitAttrMap(
                urwid.Columns([
                    urwid.Text(te['name'], align='left', wrap='clip'),
                    (9,
                     urwid.Text(f"| {render_bytes(te['sizeWhenDone']): >7s}",
                                align='right', wrap='clip'))
                ]),
                te['percentDone'],
                (done_color, done_color),
                ('not_done', 'not_done_focus'))),
            ('pack', urwid.Columns([
                (2, urwid.Text('  ')),
                urwid.Text(status),
                urwid.Text(f"{render_bytes(te['uploadedEver'])} uploaded"),
                urwid.Text(f"{te['peersConnected']} peers connected"),
                urwid.Text(f"{seed_count} seeds    {leech_count} leeches",
                           align='right'),
            ]))
        ])
        nw = urwid.AttrMap(w,
                           'normal', 'selected')

        upload_rate_str = (render_bytes(te['rateUpload']) if
                           te['rateUpload'] > 0 else '')
        download_rate_str = (render_bytes(te['rateDownload']) if
                             te['rateDownload'] > 0 else '')
        eta_str = render_time(te['eta']) if te['eta'] > 0 else ''
        cw = urwid.Columns([
            nw,
            (9, urwid.Pile([
                urwid.Columns([
                    (2, urwid.Text(' ↓')),
                    (7, urwid.AttrMap(
                        urwid.Text(download_rate_str,
                                   align='right'),
                        'download_rate'))
                ]),
                urwid.Columns([
                    (2, urwid.Text(' ±')),
                    (7, urwid.AttrMap(
                        urwid.Text(eta_str, align='right'),
                        'eta'))
                ]),
            ])),
            (10, urwid.Pile([
                urwid.Columns([
                    (2, urwid.Text(' ↑')),
                    (8, urwid.AttrMap(
                        urwid.Text(upload_rate_str,
                                   align='right'),
                        'upload_rate'))
                ]),
                urwid.Columns([
                    (2, urwid.Text(' ·')),
                    (8, urwid.AttrMap(
                        urwid.Text(
                            f"{round(max(te['uploadRatio'], 0), 2):.2f}",
                            align='right'),
                        'eta'))
                ]),
            ])),
        ])
        self.torrent_info = te
        super().__init__(cw)

    def selectable(self):
        rv = self.parent is not None
        return rv

    def render(self, size, focus=False):
        # output(f"rendering {id(self)} at {size} focus={focus}")
        return super().render(size, focus)

    def keypress(self, size, key):
        if self.parent is None:
            return key
        if key == 'enter':
            self.parent.show_torrent_detail(self.torrent_info)
            return None
        return key

class TorrentListWalker(urwid.ListWalker):
    """A ListWalker subclass that tracks torrent entries according to their unique
    IDs assigned by Transmission.

    """
    def __init__(self, parent: Optional[ConsoleMain] = None) -> None:
        self.entries: Dict[int, Tuple[Dict[str, Any], urwid.Widget]] = {}
        self.order: List[int] = []

        self.parent = parent

        # This is a FIFO queue (max 2) of sort orders which are applied in
        # earliest-to-latest order. Thus, for sorts like 'status' where many
        # entries compare equal, you can set a secondary sort order (which
        # applies due to stable sort).
        self.sorts: List[Tuple[str, bool]] = [('name', False)]

        self.focus: Optional[int] = None

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def sort_key(self) -> str:
        return self.sorts[-1][0]

    @property
    def sort_reversed(self) -> bool:
        return self.sorts[-1][1]

    def set_entries(self, tl: List[Dict[str, Any]]) -> None:
        self.entries = { i['id']: (i, TorrentEntry(i, parent=self.parent))
                         for i in tl }
        self.order = list(self.entries.keys())
        self._do_sort()

        if len(self.order) == 0:
            self.focus = None
        elif self.focus not in self.order:
            self.focus = self.order[0]

        self._modified()

    def set_sort(self, key: Optional[str] = None,
                 rev: Optional[bool] = None) -> None:
        se = (self.sort_key if key is None else key,
              self.sort_reversed if rev is None else rev)
        self.sorts.append(se)
        while len(self.sorts) > 2:
            self.sorts.pop(0)
        self._do_sort()
        # if self.parent is not None:
        #     self.parent.jump_if_unfocused()
        self._modified()

    def _do_sort(self):
        for key, rev in self.sorts:
            self.order.sort(key=lambda x: self.entries[x][0][key],
                            reverse=rev)

    def __getitem__(self, item: int) -> urwid.Widget:
        return self.entries[item][1]

    def next_position(self, position: int) -> int:
        try:
            ind = self.order.index(position)
        except ValueError:
            raise IndexError()
        rv = self.order[ind + 1]
        return rv

    def prev_position(self, position: int) -> int:
        try:
            ind = self.order.index(position)
        except ValueError:
            raise IndexError()
        if ind == 0:
            raise IndexError()
        rv = self.order[ind - 1]
        return rv

    def set_focus(self, position: int) -> None:
        if position not in self.order:
            raise IndexError()
        self.focus = position
        self._modified()

    def positions(self, reverse: bool = False):
        if not reverse:
            return iter(self.order)
        return reversed(self.order)

    # def _modified(self) -> None:
    #     super()._modified()
