#!python3

import urwid
from math import floor
import datetime
from collections import abc

from typing import Optional, Tuple, Iterator

class ColSplitAttrMap(urwid.AttrMap):
    def __init__(self, w, frac, left_attrs, right_attrs):
        """This acts as an AttrMap, except it applies left_attrs to the leftmost
        portion of the rendered widget and right_attrs to the rightmost.
        left_attrs and right_attrs are both tuples of the form (attr_map,
        focus_map). frac is the floating-point fraction of the widget column
        width that has left_attrs applied.

        """
        super().__init__(w, *right_attrs)

        left_attr, left_focus = left_attrs
        self._left_attr_map = (left_attr if isinstance(left_attr, dict)
                               else { None: left_attr })
        self._left_focus_map = (left_focus if isinstance(left_focus, dict)
                                else { None: left_focus })

        self.frac = frac

    def render(self, size, focus=False):
        right_map = (self._focus_map if focus and self._focus_map is not None
                     else self._attr_map)
        left_map = (self._left_focus_map if focus and
                    self._left_focus_map is not None
                    else self._left_attr_map)

        base_canv = self._original_widget.render(size, focus=focus)
        right_canv = urwid.CompositeCanvas(base_canv)
        right_canv.fill_attr_apply(right_map)

        cols = base_canv.cols()
        apply_frac = round(self.frac, 3)
        right_cols = cols - floor(apply_frac * cols)
        # if requested amount is 0, don't overlay anything
        # (trying to trim a canvas down to 0 columns causes an error)
        if right_cols < cols:
            left_canv = urwid.CompositeCanvas(base_canv)
            left_canv.fill_attr_apply(left_map)

            left_canv.pad_trim_left_right(0, - right_cols)
            right_canv.overlay(left_canv, 0, 0)
        return right_canv

class ScrollableText(urwid.WidgetWrap):
    """A class that operates as a box widget, showing however much of the given
    text args can be displayed in the box. If treated like a flow widget, just
    passed on to the underlying Text.

    """
    def __init__(self, *args, **kwargs):
        self.scroll_pos = kwargs.pop('scroll', 0)
        wid = urwid.Text(*args, **kwargs)
        super().__init__(wid)

        self.text_rows = 0

    def selectable(self):
        return True

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        if len(size) == 1:
            return super().keypress(size, key)

        cols, rows = size
        if self.text_rows <= rows:
            return key
        max_scroll_pos = max(self.text_rows - rows, 0)
        if key == 'down' and self.scroll_pos < max_scroll_pos:
            self.scroll_pos += 1
        elif key == 'up' and self.scroll_pos > 0:
            self.scroll_pos -= 1
        elif key == 'page down' and self.scroll_pos < max_scroll_pos:
            self.scroll_pos = min(self.scroll_pos + rows, max_scroll_pos)
        elif key == 'page up' and self.scroll_pos > 0:
            self.scroll_pos = max(self.scroll_pos - rows, 0)
        elif key == 'home' and self.scroll_pos > 0:
            self.scroll_pos = 0
        elif key == 'end' and self.scroll_pos < max_scroll_pos:
            self.scroll_pos = max_scroll_pos
        else:
            return key

        self._invalidate()
        return None

    def render(self, size, focus=False):
        if len(size) == 1:
            # flow rendering: delegate to underlying Text
            return super().render(size, focus)

        cols, rows = size
        text_canv = super().render((cols,), focus)
        self.text_rows = text_canv.rows()
        if self.text_rows <= rows:
            self.scroll_pos = 0
        res = urwid.CompositeCanvas(text_canv)
        res.pad_trim_top_bottom(- self.scroll_pos,
                                rows - self.text_rows + self.scroll_pos)
        return res

def render_bytes(amt: int) -> str:
    suffixes = ['', 'K', 'M', 'G', 'T', 'P']
    for n, s in enumerate(suffixes):
        if amt < 1024 ** (n + 1):
            return f"{amt / (1024 ** n):.1f}{s}"
    return str(amt)

def render_time(secs: int) -> str:
    MINUTE = 60
    HOUR = MINUTE * 60
    DAY = HOUR * 24
    MONTH = DAY * 28
    YEAR = DAY * 365

    if secs < MINUTE:
        return f"{secs}s"
    elif secs < HOUR:
        mins = round(secs / MINUTE)
        return f"{mins}m"
    elif secs < DAY:
        hrs = round(secs / HOUR)
        return f"{hrs}h"
    elif secs < MONTH:
        days = round(secs / DAY)
        return f"{days}d"
    elif secs < YEAR:
        months = round(secs / MONTH)
        return f"{months}M"
    else:
        years = round(secs / YEAR)
        return f"{years}Y"

out = None
def output(s):
    global out
    if out is None:
        out = open('out', 'a')
    ts = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    out.write(f"{ts} -- {s}\n")
    out.flush()

def make_underline_layout(text: str, char_in: Optional[str],
                          base_style=None, underline_style='underline'):
    """Makes a Text layout list that displays the given text, with the first
    instance of the given character underlined."""
    if char_in is None:
        return [text]
    ind = text.index(char_in)
    return [(base_style, text[:ind]),
            (underline_style, text[ind:ind + 1]),
            (base_style, text[ind + 1:])]

def byte_to_bits(b: int) -> Iterator[bool]:
    for mul in [0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01]:
        yield (b & mul != 0)

class Bitset(abc.Sequence):
    def __init__(self, data):
        self._bytes = data

    def __iter__(self) -> Iterator[bool]:
        for i in self._bytes:
            yield from byte_to_bits(i)

    def __getitem__(self, ind: int) -> bool:
        bi = ind // 8
        bit = ind % 8

        val = self._bytes[bi]
        mask = 0x80 >> bit
        return (val & mask) != 0

    def __len__(self) -> int:
        return len(self._bytes) * 8

def bytes_to_bits(b: bytes) -> Iterator[bool]:
    for i in b:
        yield from byte_to_bits(i)
