#!python3

from __future__ import annotations

import trio, os, urwid
from .rpc import TransmissionConnection
from math import floor, inf
from .util import output, make_underline_layout, render_bytes
from .torrent_list import TorrentListWalker
from .torrent_detail import TorrentDetailWindow

from typing import Any, List, Dict, Tuple, Optional, Union, Callable, cast

class ConsoleHeader(urwid.WidgetWrap):
    def __init__(self):
        self.verinf = urwid.Text("Transmission ver. @ host:port", 'left',
                                 'clip')
        self.helpstr = urwid.Text("/:Search  f:Filter  s:Sort  ?:Help  "
                                  "o:Options  q:Quit", 'right', 'clip')
        w = urwid.AttrMap(
            urwid.Columns([self.verinf, ('pack', self.helpstr)]),
            'invert',
            'invert'
        )
        super().__init__(w)

    def selectable(self):
        return True

    def update(self, ses: Dict[str, Any], conn: Tuple[str, int]) -> None:
        self.verinf.set_text(f"Transmission {ses['version']} @ "
                             f"{conn[0]}:{conn[1]}")

class RatesWidget(urwid.WidgetWrap):
    def __init__(self):
        self.dl_rate = urwid.Text('', align='right')
        self.dl_limit = urwid.Text('')
        self.ul_rate = urwid.Text('', align='right')
        self.ul_limit = urwid.Text('')
        self.cols = urwid.Columns([
            (2, urwid.Text(' ↓')),
            (7, urwid.AttrMap(self.dl_rate, 'download_rate')),
            ('pack', self.dl_limit),
            (2, urwid.Text(' ↑')),
            (9, urwid.AttrMap(self.ul_rate, 'upload_rate')),
            ('pack', self.ul_limit),
        ])
        self.delay_msg = urwid.Text('', align='right')
        super().__init__(self.cols)

    def update_rates(self, stats, ses):
        self.dl_rate.set_text(render_bytes(stats['downloadSpeed']))
        self.dl_limit.set_text(f"/{ses['speed-limit-down']}K" if
                               ses['speed-limit-down-enabled'] else '')
        self.ul_rate.set_text(render_bytes(stats['uploadSpeed']))
        self.ul_limit.set_text(f"/{ses['speed-limit-up']}K" if
                               ses['speed-limit-up-enabled'] else '')

    def update_time(self, time):
        # self.delay_msg.set_text(str(time))
        self.time_since_update = time
        self.delay_msg.set_text(f"{floor(time):d}s ago")
        if self.time_since_update >= 5:
            self._w = self.delay_msg
        else:
            self._w = self.cols

    def col_count(self):
        rv = 0
        for w, o in self.cols.contents:
            t, v, _ = o
            if t == 'given':
                rv += v
            elif t == 'pack':
                mc, mr = w.pack((180,))
                rv += mc
        return rv

    def pack(self, size, focus=False):
        if self._w is self.cols:
            cv = self.col_count()
            return (cv, 1)
        else:
            return super().pack(size, focus)

class ConsoleFooter(urwid.WidgetWrap):
    def __init__(self):
        self.counts = urwid.Text("", 'left', 'clip')
        self.rates = RatesWidget()
        self.cols = urwid.Columns([
            self.counts,
            ('pack', self.rates),
        ])
        w = urwid.AttrMap(
            self.cols,
            {
                None: 'invert'
            }
        )
        self.time_since_update = 0.0
        super().__init__(w)

    def update(self, tl: List[Dict[str, Any]], stats: Dict[str, Any],
               ses: Dict[str, Any], dur: float) -> None:
        self.counts.set_text(f"Torrents:{len(tl)} (request took {dur:.4f}s)")
        self.rates.update_rates(stats, ses)

    def update_time(self, time: float) -> None:
        self.rates.update_time(time)

    def selectable(self):
        return False

class ConsoleMain(urwid.WidgetWrap):
    def __init__(self, parent: ConsoleToplevel) -> None:
        self.data = TorrentListWalker(parent=self)
        self.view = urwid.ListBox(self.data)
        self.detail_shown = False
        self.parent = parent
        super().__init__(self.view)

    def render_torrents(self, tlist: List[Dict[str, Any]]) -> None:
        self.data.set_entries(tlist)
        self.jump_if_unfocused()
        if self.detail_shown:
            dwin = self._w

            # we use dwin here so that it gets separately closed over by cb,
            # since _w in self can get changed out from under us
            def cb(te):
                dwin.set_data(te)
            tid = self._w.torrent_info['id']
            self.parent.call_async_function(
                lambda: self.parent.get_torrent_details(tid),
                cb
            )

    # def selectable(self) -> bool:
    #     rv = super().selectable()
    #     return rv

    def set_sort(self, key: str, reverse: bool):
        self.data.set_sort(key, reverse)
        self.jump_if_unfocused()

    def jump_if_unfocused(self) -> None:
        if self.parent.fr.focus_position != 'body':
            self.jump_to_top()

    def jump_to_top(self) -> None:
        if len(self.data) > 0:
            self.view.focus_position = next(self.data.positions())

    def show_torrent_detail(self, te):
        """This invokes a network call to fetch details, and waits until the result is
        in."""
        def cb(te):
            self._w = TorrentDetailWindow(te)
            self.detail_shown = True

        self.parent.call_async_function(
            lambda: self.parent.get_torrent_details(te['id']),
            cb
        )

    def keypress(self, size, key):
        # output(f"ConsoleMain {key} from toplevel")
        key = super().keypress(size, key)
        # output(f"ConsoleMain {key} from super")

        if key in ['q', 'esc'] and self.detail_shown:
            # output("hiding detail")
            self._w = self.view
            self.detail_shown = False
        else:
            return key

class PopupItem(urwid.WidgetWrap):
    def __init__(self, text: str, trigger_char: Optional[str],
                 callback: Optional[Callable[[], bool]]) -> None:
        if trigger_char is not None:
            if len(trigger_char) != 1:
                raise ValueError("trigger_char must be one character")
            if trigger_char not in text:
                raise ValueError("trigger_char must be in value")
            if callback is None:
                raise ValueError("callback must be set if trigger_char set")

        self._selectable = (trigger_char is not None)

        self.trigger = trigger_char
        self.callback = callback

        w = urwid.Text(make_underline_layout(text, trigger_char), wrap='clip')
        am = urwid.AttrMap(w, {},
                           {None: 'selected',
                            'underline': 'selected_underline'})
        super().__init__(am)

    # @staticmethod
    # def make_layout(text: str, trigger_char: Optional[str]):

    def selectable(self) -> bool:
        return self._selectable

    def keypress(self, size, key):
        return key

class PopupWindow(urwid.WidgetWrap):
    def __init__(self, title: Union[str, Tuple[str, ...]],
                 lines: List[PopupItem], scroll_select: bool = False) -> None:
        self.all_triggers: Dict[str, PopupItem] = {}
        for l in lines:
            if l.trigger is None:
                continue
            lt = l.trigger.lower()
            if lt in self.all_triggers:
                raise ValueError("trigger char may not be repeated")
            self.all_triggers[lt] = l
        self.contents = urwid.Pile(lines)
        self.item_list = lines
        self.scroll_select = scroll_select
        w = urwid.LineBox(self.contents, title)
        super().__init__(w)

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        if key == 'esc':
            self.parent.close_popup()
        elif key in self.all_triggers:
            cb = self.all_triggers[key].callback
            assert cb is not None
            close = cb()
            if close:
                self.parent.close_popup()
        elif self.scroll_select:
            if key in ['up', 'down']:
                return super().keypress(size, key)
            elif key == 'enter':
                cb = self.contents.focus.callback
                assert cb is not None
                close = cb()
                if close:
                    self.parent.close_popup()
        return None

    def _selectable(self) -> bool:
        return True

    def get_min_cols(self) -> int:
        return max(i.pack()[0] for i in self.item_list)

class TestPopup(PopupWindow):
    def __init__(self):
        super().__init__(
            title='Testing',
            lines=[
                PopupItem('Close', 'C', lambda: True)
            ])

class SortControlWindow(PopupWindow):
    sort_orders = [
        ('Name', 'N', 'name'),
        ('Age', 'A', 'addedDate'),
        ('Progress', 'P', 'percentDone'),
        ('Seeds', 'S', 'seeders'),
        ('Leeches', 'c', 'leechers'),
        ('Size', 'z', 'sizeWhenDone'),
        ('Status', 't', 'status'),
        ('Uploaded', 'l', 'uploadedEver'),
        ('Upload Speed', 'U', 'rateUpload'),
        ('Download Speed', 'D', 'rateDownload'),
        ('Ratio', 'R', 'uploadRatio'),
        ('Peers', 'e', 'peersConnected'),
        ('Location', 'o', 'downloadDir'),
        # ('Tracker', 'k', 'mainTrackerDomain'),
    ]

    def __init__(self):
        items = []

        def getSortLambda(k):
            def f():
                self.parent.main.set_sort(k, None)
                return True
            return f

        for i, j, k in self.sort_orders:
            items.append(PopupItem(i, j, getSortLambda(k)))
        items.append(PopupItem(
            "Reverse", 'v',
            # a dumb trick to both call a function and return a value from the
            # same lambda
            lambda: (self.parent.main.set_sort(
                None, not self.parent.main.data.sort_reversed
            ), True)[-1]))
        super().__init__(
            title='Sort order',
            lines=items,
            scroll_select=True
        )

class ConsoleToplevel(urwid.WidgetWrap):
    _w: urwid.Widget

    def __init__(self, nursery: trio.Nursery) -> None:
        self.main = ConsoleMain(self)
        self.hdr = ConsoleHeader()
        self.ftr = ConsoleFooter()
        self.fr = urwid.Frame(self.main, header=self.hdr, footer=self.ftr)
        self._nursery = nursery
        self._nursery.start_soon(self.update_data)
        self._nursery.start_soon(self.track_update_time)
        self.last_update = trio.current_time()
        self.popup_open = False
        super().__init__(self.fr)
        self.fr.focus_position = 'header'

        self.q_time = None
        self.q_count = 0

        self.callback_send, self.callback_recv = trio.open_memory_channel(inf)
        self._nursery.start_soon(self.handle_callbacks)

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        # pressing q five times in five seconds will quit, regardless of what
        # subwidgets are doing
        now = trio.current_time()
        if self.q_time is not None and now - self.q_time > 5.0:
            self.q_time = None
            self.q_count = 0

        if key == 'q':
            if self.q_time is None:
                self.q_time = now
            self.q_count += 1
            if self.q_count >= 5:
                raise urwid.ExitMainLoop()

        # output(f"{key} came to toplevel")
        key = super().keypress(size, key)
        # output(f"{key} came from super")
        if key is None:
            return

        if key == 'q':
            raise urwid.ExitMainLoop()
        elif key == 's':
            self.show_popup(SortControlWindow())
        elif key == 'esc' and self.fr.focus_position == 'body':
            self.fr.focus_position = 'header'
            self.main.jump_if_unfocused()
        elif key == 'up' and self.fr.focus_position == 'body':
            i = self.main.view.focus_position
            try:
                self.main.data.prev_position(i)
            except IndexError:
                self.fr.focus_position = 'header'
            else:
                return super().keypress(size, key)
        elif key == 'down' and self.fr.focus_position == 'header':
            self.fr.focus_position = 'body'
            self.main.view.focus_position = next(self.main.data.positions())
        else:
            return key

    def show_popup(self, win: PopupWindow) -> None:
        win.parent = self
        self.popup_open = True
        width = win.get_min_cols()
        self._w = urwid.Overlay(
            win, self._w,
            'center', ('relative', width), 'middle', 'pack'
        )

    def close_popup(self) -> None:
        # extract the lower window from the overlay and restore it
        self._w = self._w.contents[0][0]
        self.popup_open = False

    def selectable(self) -> bool:
        return True

    TORRENT_DETAIL_FIELDS = [
        'files', 'priorities', 'wanted', 'peers', 'trackers',
        'activityDate', 'dateCreated', 'startDate', 'doneDate',
        'totalSize', 'leftUntilDone', 'comment', 'creator',
        'hashString', 'pieceCount', 'pieceSize', 'pieces',
        'downloadedEver', 'corruptEver', 'peersFrom'
    ]

    # this is a cringeworthy hack of callback-based code into Trio's nice
    # coroutine system, but such are the wages of using a sync console
    # framework
    def call_async_function(self, func, callback):
        self.callback_send.send_nowait((func, callback))

    async def handle_callbacks(self) -> None:
        async for func, cb in self.callback_recv:
            # async funcs called inside a lambda, to avoid stray coroutines
            # floating around
            co = func()
            rv = await co
            cb(rv)

    async def get_torrent_details(self, tid: int) -> Dict[str, Any]:
        tfields = (self.tr_server.get_torrents_fields +
                   self.TORRENT_DETAIL_FIELDS)
        rv = await self.tr_server.get_torrents(torrents=tid, fields=tfields)
        # rv is a list of torrents; we know it has only one entry, so return it
        # on its own
        return rv[0]

    async def update_data(self) -> None:
        auth: Optional[Tuple[str, str]]
        if 'TR_AUTH' in os.environ:
            auth = cast(Tuple[str, str],
                        tuple(os.environ['TR_AUTH'].split(':')))
        else:
            auth = None
        tr_host = 'localhost'
        tr_port = 9091
        t = TransmissionConnection(tr_host, tr_port, auth)
        self.tr_server = t
        while True:
            it = trio.current_time()
            try:
                r = await t.get_torrents()
                ses = await t.get_session()
                stats = await t.get_session_stats()
            except Exception:
                continue
            ft = trio.current_time()
            self.last_update = ft
            dur = ft - it
            self.main.render_torrents(r)
            self.ftr.update(r, stats, ses, dur)
            self.hdr.update(ses, (tr_host, tr_port))
            await trio.sleep_until(it + 3.0)

    async def track_update_time(self) -> None:
        while True:
            ct = trio.current_time()
            self.ftr.update_time(ct - self.last_update)
            await trio.sleep(0.5)

async def main() -> None:
    palette = [('normal', 'black', 'default'),
               ('underline', 'black,underline', 'default',
                'underline'),
               ('invert', 'light gray', 'black'),
               ('selected', 'white', 'black', 'standout'),
               ('selected_underline', 'white,underline', 'black',
                'standout,underline'),
               ('seeding_done', 'black', 'dark green'),
               ('idle_done', 'black', 'dark cyan'),
               ('downloading_done', 'black', 'dark blue'),
               ('not_done', 'light gray', 'black'),
               ('not_done_focus', 'white', 'black', 'standout'),
               ('download_rate', 'light blue', 'black'),
               ('upload_rate', 'light red', 'black'),
               ('eta', 'white', 'black'),
               ('test', 'light red', 'default')]
    async with trio.open_nursery() as nursery:
        loop = urwid.TrioEventLoop()
        toplevel = ConsoleToplevel(nursery)
        ml = urwid.MainLoop(toplevel, palette, event_loop=loop)
        with ml.start():
            await loop.run_async()
        # this ends the update jobs started inside ConsoleToplevel
        nursery.cancel_scope.cancel()

def sync_main() -> None:
    trio.run(main)
