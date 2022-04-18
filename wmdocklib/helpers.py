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

import os
import re

from wmdocklib import pywmgeneral


charset_start = None
charset_width = None

RGB_FILE_LIST = ['/etc/X11/rgb.txt',
                 '/usr/lib/X11/rgb.txt',
                 '/usr/share/X11/rgb.txt',
                 '/usr/X11R6/lib/X11/rgb.txt',
                 '/usr/lib/X11/rgb.txt']


def get_center_start_pos(string, areaWidth, offset):
    """Get the x starting position if we want to paint string centred."""
    w = len(string) * char_width
    text_area = areaWidth - offset * 2 - 1
    return (text_area - w) / 2


def get_vertical_spacing(num_lines, margin, height, y_offset):
    """Return the optimal spacing between a number of lines.

    margin is the space we want between the first line and the top."""
    h = height - (num_lines * char_height + 1) - y_offset * 2 - margin
    return h / (num_lines - 1)


def read_xpm(obj):
    """Read the xpm in filename or treat object as a string with XPM data.

    Return the pair (palette, pixels).

    palette is a dictionary char->color (no translation attempted).
    pixels is a list of strings.

    Raise IOError if we run into trouble when trying to read the file.  This
    function has not been tested extensively.  do not try to use more than
    """
    if obj.startswith('/* XPM */'):
        lines = [line for line in obj.split('\n')]
    else:
        with open(obj, 'r') as fobj:
            lines = fobj.read().split('\n')

    string = ''.join(lines)
    data = []
    while True:
        next_str_start = string.find('"')
        if next_str_start != -1:
            next_str_end = string.find('"', next_str_start + 1)
            if next_str_end != -1:
                data.append(string[next_str_start + 1:next_str_end])
                string = string[next_str_end + 1:]
                continue
        break

    palette = {}
    colorCount = int(data[0].split(' ')[2])
    charsPerColor = int(data[0].split(' ')[3])
    assert(charsPerColor == 1)

    for i in range(colorCount):
        colorChar = data[i+1][0]
        color_name = data[i+1][1:].split()[1]
        palette[colorChar] = color_name
    data = data[1 + int(data[0].split(' ')[2]):]
    return palette, data


def redraw_xy(x, y):
    """Redraw a given region of the window."""
    pywmgeneral.redraw_window_xy(x, y)


def copy_xpm_area(sourceX, sourceY, width, height, targetX, targetY):
    """Copy an area of the global XPM."""
    (sourceX, sourceY, width, height, targetX,
     targetY) = (int(sourceX), int(sourceY), int(width), int(height),
                 int(targetX), int(targetY))
    if width > 0 or height > 0:
        pywmgeneral.copy_xpm_area(sourceX, sourceY, width, height,
                                  targetX, targetY)


def add_mouse_region(index, left, top, right=None, bottom=None, width=None, height=None):
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


def get_color_code(color_name, rgb_fname=None):
    """Convert a color to rgb code usable in an xpm.

    We use the file rgb_fname for looking up the colors. Return None
    if we find no match. The rgb_fname should be like the one found in
    /usr/lib/X11R6/rgb.txt on most sytems.
    """
    if color_name.startswith('#'):
        return color_name

    if rgb_fname is None:
        for fn in RGB_FILE_LIST:
            if os.access(fn, os.R_OK):
                rgb_fname = fn
                break

    if rgb_fname is None:
        raise ValueError('cannot find rgb file')

    with open(rgb_fname, 'r') as fobj:
        lines = fobj.readlines()

    for line in lines:
        if line[0] != '!':
            words = line.split()
            if len(words) > 3:
                name = ' '.join(words[3:])
                if color_name.lower() == name.lower():
                    # Found the right color, get it's code
                    try:
                        r = int(words[0])
                        g = int(words[1])
                        b = int(words[2])
                    except ValueError:
                        continue

                    return f'#{r:02x}{g:02x}{b:02x}'
    return None


def get_unique_key(dict_to_check):
    for char in range(40, 126):
        char = chr(char)
        if char not in dict_to_check:
            return char


def normalize_color(color):
    if color.startswith('#'):
        return color
    else:
        return get_color_code(color)
