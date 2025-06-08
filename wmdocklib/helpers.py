"""pywmhelpers.py

Various helper functions when writing wm dockapps in Python. This module
is way better commented than the pywmgeneral one. This is the one
intented for use in applications. Many functions are just wrappers
around the ones in pywmgeneral but with nicer interfaces and better
documentation.

Copyright (C) 2003 Kristoffer Erlandsson

Licensed under the GNU General Public License


Changes:

2006-10-10 Mario Frasca
redesigned xpm initialization

2003-06-25 Kristoffer Erlandsson
Updated documentation

2003-06-24 Kristoffer Erlandsson
Some changes to handle the additional event handling in pywmgeneral

2003-06-16 Kristoffer Erlandsson
First workingish version
"""

import re

from wmdocklib import pywmgeneral


charset_start = None
charset_width = None

MARKER = 'xxxxxxxxxxx'


def get_font_char_size(font_name):
    """Return char size infered from font name.

    It is expected, that font should have char size included in the file name,
    i.e.

      charset_8x12_big_black.xpm
      6x8-small.xpm

    so the pattern searched here would be WxH, where W and H are char width
    and height (including interval between chars and lines) and x is literally
    x.
    """
    res = re.match(r'.*?(?P<w>[0-9]+)(?:\((?P<t>[0-9]+)\))?x(?P<h>[0-9]+).*',
                   font_name)
    if not res:
        return None, None

    return int(res.groupdict().get('w')), int(res.groupdict().get('h'))


def get_center_start_pos(string, area_width, char_width, offset):
    """Get the x starting position if we want to paint string centred."""
    string_width = len(string) * char_width
    text_area = area_width - offset * 2 - 1
    return (text_area - string_width) / 2


def get_vertical_spacing(num_lines, margin, char_height, height, y_offset):
    """Return the optimal spacing between a number of lines.

    margin is the space we want between the first line and the top."""
    height = height - (num_lines * char_height + 1) - y_offset * 2 - margin
    return height / (num_lines - 1)


def read_xpm(obj):
    """Read the xpm in filename or treat object as a string with XPM data.

    Return the pair (palette, bitmap_list).

    Palette is a dictionary char->color without color translation.
    Data is a list of strings of the XPM image lines.
    """
    if obj.startswith('/* XPM */'):
        lines = obj.split('\n')
    else:
        with open(obj, 'r') as fobj:
            lines = fobj.read().split('\n')

    string = ''.join(lines)
    bitmap_list = []
    while True:
        next_str_start = string.find('"')
        if next_str_start != -1:
            next_str_end = string.find('"', next_str_start + 1)
            if next_str_end != -1:
                bitmap_list.append(string[next_str_start + 1:next_str_end])
                string = string[next_str_end + 1:]
                continue
        break

    palette = {}
    color_count = int(bitmap_list[0].split(' ')[2])
    chars_per_color = int(bitmap_list[0].split(' ')[3])
    assert chars_per_color == 1

    for i in range(color_count):
        color_char = bitmap_list[i+1][0]
        color_name = bitmap_list[i+1][1:].split()[1]
        palette[color_char] = color_name
    bitmap_list = bitmap_list[1 + int(bitmap_list[0].split(' ')[2]):]
    return palette, bitmap_list


def redraw_xy(x, y):
    """Redraw a given region of the window."""
    pywmgeneral.redraw_window_xy(x, y)


def copy_xpm_area(source_x, source_y, width, height, target_x, target_y):
    """Copy an area of the global XPM."""
    (source_x, source_y, width, height, target_x,
     target_y) = (int(source_x), int(source_y), int(width), int(height),
                 int(target_x), int(target_y))
    if width > 0 or height > 0:
        pywmgeneral.copy_xpm_area(source_x, source_y, width, height,
                                  target_x, target_y)


def add_mouse_region(index, left, top, right=None, bottom=None, width=None,
                     height=None):
    """Add a mouse region in the window."""
    if right is bottom is None:
        right = left + width
        bottom = top + height
    pywmgeneral.add_mouse_region(index, left, top, right, bottom)


def check_mouse_region(x, y):
    """Check if x,y is in any mouse region. Return that region, otherwise -1.
    """
    return pywmgeneral.check_mouse_region(x, y)


def get_event():
    """Check for XEvents and return one if found.

    Return None if we find no events. There may be events pending still
    after this function is called. If an event which we handle is found,
    return a dictionary with information about it. All dictionaries
    contain a 'type' field identifying the event. Now existing events
    with dictionary keys are:
    'buttonrelease':
        x, y, button
    'destroynotify':
    """
    return pywmgeneral.check_for_events()


def get_color_code(color_name):
    """Convert a color to rgb code usable in an xpm."""
    color = pywmgeneral.get_color(color_name)
    if color < 0:
        return None
    return f"#{color:06x}"


def get_unique_key(dict_to_check):
    for char in range(40, 126):
        _char = chr(char)
        if _char not in dict_to_check:
            return _char
    return None


def normalize_color(color):
    if color.startswith('#'):
        return color

    return get_color_code(color)


def merge_palettes(pal1, pal2, bitmap_list):
    """
    Merge two palettes, with preference of the first one, make appropriate
    char changes in the bitmap_list. Returns new palette and corrected bitmap.
    """
    rerun = False
    for char in pal2.copy():
        # get the color from possibly updated palette, not from the copy
        color = pal2[char]
        if color == MARKER:
            # ignore replaced chars
            continue

        if pal1.get(char) == color:
            # perfect match no need to do anything
            continue

        if char not in pal1:
            # there is no color defined for the char, simply add
            # it to the palette
            pal1[char] = color
            continue

        # There is mismatch color for a char

        # find out, if color exists under different key
        new_char = {v: k for k, v in pal1.items()}.get(color)
        if pal2.get(new_char) == MARKER:
            continue

        if new_char:
            if new_char in pal2:
                # we have a clash - char contain different color, change it to
                # temporary marker.
                all_chars = pal1.copy()
                all_chars.update(pal2)
                sub = get_unique_key(all_chars)
                # remap clashing character to the new one
                bitmap_list = [r.replace(new_char, sub) for r in bitmap_list]
                # and now remap character with the one found in first palette
                bitmap_list = [r.replace(char, new_char) for r in bitmap_list]
                pal2[sub] = pal2[new_char]
                pal2[new_char] = MARKER
                pal2[char] = MARKER
                rerun = True
            else:
                # color not found, add new replacement
                bitmap_list = [x.replace(char, new_char) for x in bitmap_list]
        elif char in pal1:
            # color not found, check if the char already exists in first
            # palette
            all_chars = pal1.copy()
            all_chars.update(pal2)
            sub = get_unique_key(all_chars)
            bitmap_list = [r.replace(char, sub) for r in bitmap_list]
            pal2[sub] = color
            pal2[char] = MARKER
            rerun = True

    if rerun:
        pal1, bitmap_list = merge_palettes(pal1, pal2, bitmap_list)

    return pal1, bitmap_list
