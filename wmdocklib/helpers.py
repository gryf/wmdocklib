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


def read_font(font_name):
    # read xpm, return cell_size, definition and palette.
    font_palette, fontdef = read_xpm(font_name)

    res = re.match(r'.*?(?P<w>[0-9]+)(?:\((?P<t>[0-9]+)\))?x(?P<h>[0-9]+).*',
                   font_name)
    if not res:
        raise ValueError("can't infer font size from name (does not "
                         "contain wxh)")
    width = res.groupdict().get('w')
    height = res.groupdict().get('h')

    return width, height, fontdef, font_palette


def get_center_start_pos(string, areaWidth, offset):
    """Get the x starting position if we want to paint string centred."""
    w = len(string) * char_width
    text_area = areaWidth - offset * 2 - 1
    return (text_area - w) / 2


def add_char(ch, x, y, x_offset, y_offset, width, height, drawable=None):
    """Paint the character ch at position x, y in the window.

    Return the (width, height) of the character painted.  (will be useful if
    we implement proportional char sets)

    the library only supports lower ascii: 32-127.  any other will cause a
    ValueError exception.

    if the character being painted falls partly out of the boundary, it will
    be clipped without causing an exception.  this works even if the
    character starts out of the boundary.
    """
    # linelength is the amount of bits the character set uses on each row.
    linelength = charset_width - (charset_width % char_width)
    # pos is the horizontal index of the box containing ch.
    pos = (ord(ch)-32) * char_width
    # translate pos into ch_x, ch_y, rolling back and down each linelength
    # bits.  character definition start at row 64, column 0.
    ch_y = int((pos / linelength)) * char_height + charset_start
    ch_x = pos % linelength
    target_x = x + x_offset
    target_y = y + y_offset
    char_width

    if drawable is None:
        pywmgeneral.copy_xpm_area(ch_x, ch_y, char_width, char_height,
                                  target_x, target_y)
    else:
        drawable.xCopyAreaFromWindow(ch_x, ch_y, char_width, char_height,
                                     target_x, target_y)
    return char_width


def add_string(string, x, y, x_offset=0, y_offset=0, width=None, height=None,
               drawable=None):
    """Add a string at the given x and y positions.

    Call add_char repeatedely, so the same exception rules apply."""
    last_width = 0
    for letter in string:
        width = add_char(letter, x + last_width, y, x_offset, y_offset,
                         width, height, drawable)
        last_width += width


def get_vertical_spacing(num_lines, margin, height, y_offset):
    """Return the optimal spacing between a number of lines.

    margin is the space we want between the first line and the top."""
    h = height - (num_lines * char_height + 1) - y_offset * 2 - margin
    return h / (num_lines - 1)


def read_xpm(filename):
    """Read the xpm in filename.

    Return the pair (palette, pixels).

    palette is a dictionary char->color (no translation attempted).
    pixels is a list of strings.

    Raise IOError if we run into trouble when trying to read the file.  This
    function has not been tested extensively.  do not try to use more than
    """
    with open(filename, 'r') as fobj:
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


def init_pixmap(background=None, patterns=None, style='3d', width=64,
                height=64, margin=3, font_name=None, bg="black", palette=None):
    """builds and sets the pixmap of the program.

    the (width)x(height) upper left area is the work area in which we put
    what we want to be displayed.

    the remaining upper right area contains patterns that can be used for
    blanking/resetting portions of the displayed area.

    the remaining lower area defines the character set.  this is initialized
    using the corresponding named character set.  a file with this name must
    be found somewhere in the path.

    palette is a dictionary
    1: of integers <- [0..15] to colors.
    2: of single chars to colors.

    a default palette is provided, and can be silently overwritten with the
    one passed as parameter.

    The XBM mask is created out of the XPM.
    """

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

    # Read provided xpm file with font definition
    global char_width, char_height

    char_width, char_height, fontdef, font_palette = read_font(font_name)
    palette_values = {v: k for k, v in font_palette.items()}

    if not palette:
        palette = font_palette
    else:
        # make sure we don't overwrite font colors
        for key, color in palette.items():
            color = normalize_color(color)
            if color in palette_values:
                continue
            if key not in font_palette:
                font_palette[key] = color
            else:
                new_key = get_unique_key(font_palette)
                font_palette[new_key] = color

    palette_values = {v: k for k, v in font_palette.items()}
    palette = font_palette

    bevel = get_unique_key('#bebebe')
    palette[bevel] = '#bebebe'

    # handle bg color
    bg = normalize_color(bg)
    key = get_unique_key(palette)
    palette[key] = bg
    bg = key

    if patterns is None:
        patterns = [bg * width] * height

    if style == '3d':
        ex = bevel
    else:
        ex = bg

    if background is None:
        background = [' ' * width for item in range(margin)] + \
                [' ' * margin +
                 bg * (width - 2 * margin - 1) +
                 ex + ' ' * (margin)
                 for item in range(margin, height-margin-1)] + \
                [' ' * margin + ex * (width - 2 * margin) + ' ' * (margin)] + \
                [' ' * width for item in range(margin)]

    elif isinstance(background, list) and not isinstance(background[0], str):
        nbackground = [[' ']*width for i in range(height)]
        for ((left, top), (right, bottom)) in background:
            for x in range(left, right+1):
                for y in range(top, bottom):
                    if x < right:
                        nbackground[y][x] = bg
                    else:
                        nbackground[y][x] = ex
                nbackground[bottom][x] = ex
        background = [''.join(item) for item in nbackground]

    global charset_start, charset_width
    charset_start = height + len(patterns)
    charset_width = len(fontdef[0])

    xpmwidth = max(len(background[0]), len(patterns[0]), len(fontdef[0]))
    xpmheight = len(background) + len(patterns) + len(fontdef)

    xpm = [
        '%s %s %d 1' % (xpmwidth, xpmheight, len(palette)),
        ] + [
        '%s\tc %s' % (k, v)
        for k,v in list(palette.items())
        if v == 'None'
        ] + [
        '%s\tc %s' % (k,v)
        for k,v in list(palette.items())
        if v != 'None'
        ] + [
        item+' '*(xpmwidth-len(item))
        for item in background + patterns
        ] + [
        line + ' '*(xpmwidth-len(line))
        for line in fontdef
        ]

    pywmgeneral.include_pixmap(xpm)
    return char_width, char_height


def open_xwindow(argv, w, h):
    """Open the X window of given width and height.

    The XBM mask is here created from the upper left rectangle of the
    XPM using the given width and height."""
    pywmgeneral.open_xwindow(len(argv), argv, w, h)


def redraw():
    """Redraw the window."""
    pywmgeneral.redraw_window()


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
