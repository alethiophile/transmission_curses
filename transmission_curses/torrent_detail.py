#!python3

import urwid
from .util import output, make_underline_layout, ScrollableText, render_bytes
from .torrent_list import TorrentEntry
from . import data
import json
from operator import itemgetter

def format_size(n):
    def split_rear_three(s):
        yield s[-3:]
        if len(s) > 3:
            yield from split_rear_three(s[:-3])

    def format_comma(n):
        return ','.join(reversed(list(split_rear_three(str(n)))))

    return f"{format_comma(n)} [{render_bytes(n)}]" if n > 0 else 'nothing'

def percent(num, denom):
    try:
        return f"{num / denom * 100.0:.2f}"
    except ZeroDivisionError:
        return "0.00"

class DetailWindowInfo(urwid.WidgetWrap):
    def __init__(self, te):
        self.torrent_info = te
        self.display_overview()

    def display_overview(self, upd=False):
        # s = json.dumps(self.torrent_info, indent=2)
        te = self.torrent_info
        wanted_n = sum(f['length'] for n, f in enumerate(te['files']) if
                       te['wanted'][n])
        wanted_str = ('everything' if wanted_n == te['totalSize'] else
                      format_size(wanted_n))
        available_n = (te['desiredAvailable'] + te['haveValid'] +
                       te['haveUnchecked'])
        left_str = format_size(te['leftUntilDone'])
        files_complete = len([i for i in te['files'] if
                              i['bytesCompleted'] == i['length']])
        files_started = len([i for i in te['files'] if
                             i['bytesCompleted'] > 0])
        corrupt_str = ('nothing' if te['corruptEver'] == 0 else
                       format_size(te['corruptEver']))
        entries = [
            ('Hash', te['hashString']),
            ('ID', te['id']),
            ('Size', f"{format_size(te['totalSize'])};  "
             f"{wanted_str} wanted;  " +
             (f"{format_size(available_n)} available;  " if
              available_n < te['totalSize'] else '') + f"{left_str} left"),
            ('Files', f"{len(te['files'])};  " +
             ('all complete' if files_complete == len(te['files']) else
              f"{files_complete} complete;  {files_started} commenced")),
            ('Chunks', f"{te['pieceCount']};  "
             f"{format_size(te['pieceSize'])} each"),
            ('Download', f"{format_size(te['downloadedEver'])} "
             f"({percent(te['downloadedEver'], te['sizeWhenDone'])}%) "
             f"received;  {format_size(te['haveValid'])} "
             f"({percent(te['haveValid'], te['sizeWhenDone'])}%) verified;  "
             f"{corrupt_str} corrupt" +
             (f" (throttled to {te['downloadLimit']}K)" if
              te['downloadLimited'] else '')),
            ('Upload', f"{format_size(te['uploadedEver'])} "
             f"({percent(te['uploadedEver'], te['sizeWhenDone'])}%) "
             "transmitted" + (f";  sending {format_size(te['rateUpload'])} "
                              "per second" if te['rateUpload'] > 0 else '') +
             (f" (throttled to {te['uploadLimit']}K)" if te['uploadLimited']
              else '')),
            ('Ratio', f"{max(te['uploadRatio'], 0):.2f} copies distributed"),
            # TODO: add info about current session default setting here
            ('Seed limit',
             'default' if te['seedRatioMode'] == data.TorrentSeedMode.GLOBAL
             else f"seed until ratio {te['seedRatioLimit']}" if
             te['seedRatioMode'] == data.TorrentSeedMode.LIMITED
             else 'unlimited')
            # TODO: add rest of this
        ]
        s = ""
        mtl = max(len(i[0]) for i in entries)
        for t, v in entries:
            if v is None:
                s += "\n"
                continue
            s += f" {t: >{mtl}}: {v}\n"
        old_scroll = self._w.scroll_pos if upd else 0
        wid = ScrollableText(s, scroll=old_scroll)
        self._w = wid

    def display_raw(self, upd=False):
        s = json.dumps(self.torrent_info, indent=2)
        old_scroll = self._w.scroll_pos if upd else 0
        wid = ScrollableText(f"JSON size: {len(s)}\n" + s, scroll=old_scroll)
        self._w = wid

    def display_files(self, upd=False):
        files_sorted = sorted(self.torrent_info['files'],
                              key=itemgetter('name'))
        text = ''.join(f"{(n+1): >4}"
                       f"{percent(i['bytesCompleted'], i['length']): >9}%"
                       f"{render_bytes(i['length']): >9}  "
                       f"{i['name']}\n"
                       for n, i in enumerate(files_sorted))
        old_scroll = self._w.scroll_pos if upd else 0
        wid = ScrollableText(text, scroll=old_scroll)
        self._w = wid

    def display_peers(self, upd=False):
        pass

    def display_trackers(self, upd=False):
        pass

    def display_chunks(self, upd=False):
        pass

    def selectable(self):
        return True

class TorrentDetailWindow(urwid.WidgetWrap):
    window_keys = {
        'O': ('Overview', DetailWindowInfo.display_overview),
        'F': ('Files', DetailWindowInfo.display_files),
        'e': ('Peers', DetailWindowInfo.display_peers),
        'T': ('Trackers', DetailWindowInfo.display_trackers),
        'C': ('Chunks', DetailWindowInfo.display_chunks),
        'R': ('Raw', DetailWindowInfo.display_raw),
    }

    def __init__(self, te):
        top = TorrentEntry(te, compact=False)
        self.mode_win = 'O'
        triggers = self.make_trigger_widget()
        self.info_win = DetailWindowInfo(te)
        disp = urwid.Pile([
            ('pack', top), ('pack', urwid.Text('')),
            ('pack', triggers), ('pack', urwid.Text('')),
            self.info_win
        ])
        self.torrent_info = te
        super().__init__(disp)

    def make_trigger_widget(self):
        def get_widget(k, v):
            wid = urwid.Text(make_underline_layout(v[0], k))
            if k == self.mode_win:
                wid = urwid.AttrMap(wid, {None: 'selected',
                                          'underline': 'selected_underline'})
            return wid

        triggers = urwid.Columns(
            [ urwid.BoxAdapter(urwid.SolidFill(' '), 1) ] +
            [ ('pack', get_widget(k, v)) for k, v in
              self.window_keys.items() ] +
            [ urwid.BoxAdapter(urwid.SolidFill(' '), 1) ],
            dividechars=2,
        )
        return triggers

    def set_mode(self, mode):
        upd = self.mode_win == mode
        self.mode_win = mode
        self.window_keys[mode][1](self.info_win, upd)
        self._w.contents[2] = (self.make_trigger_widget(), ('pack', None))

    def set_data(self, te):
        self.torrent_info = te
        self._w.contents[0] = (TorrentEntry(te), ('pack', None))
        self.info_win.torrent_info = te
        self.set_mode(self.mode_win)

    # def selectable(self):
    #     rv = super().selectable()
    #     return rv

    def keypress(self, size, key):
        key = super().keypress(size, key)

        for t in self.window_keys:
            if key == t.lower():
                self.set_mode(t)
                return None

        return key

    # def render(self, size, focus=False):
    #     # output(f"DetailWindow {id(self)} rendering at {size} focus={focus}")
    #     return super().render(size, focus)
