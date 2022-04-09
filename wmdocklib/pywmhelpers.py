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
import types
import configparser

charset_start = None
charset_width = None
pattern_start = None

from wmdocklib import pywmgeneral
defaultRGBFileList = [
    '/etc/X11/rgb.txt',
    '/usr/lib/X11/rgb.txt',
    '/usr/share/X11/rgb.txt',
    '/usr/X11R6/lib/X11/rgb.txt',
    '/usr/lib/X11/rgb.txt',
    ]

def readConfigFile(fileName, errOut):
    """Read the config file fileName.

    Return a dictionary with the options and values in the DEFAULT
    section. Ignore everything else. The configuration file should not
    get so complicated so that sections are needed. errOut is the
    file-like object to which error messages will be printed.
    """
    if not os.access(fileName, os.R_OK):
        if errOut:
            errOut.write(
                'Configuration file is not readable. Using defaults.\n')
        return {}
    cp = configparser.ConfigParser()
    try:
        cp.read(fileName)
    except configparser.Error as e:
        if errOut:
            errOut.write('Error in configuration file:\n')
            errOut.write(str(e) + '\nUsing defaults.')
        return {}
    defaults = cp.defaults()
    if defaults == {}:
        if errOut:
            errOut.write(
                'Missing or empty DEFAULT section in the config file.\n')
            errOut.write('Using defaults.\n')
    return defaults

def getCenterStartPos(s, areaWidth, offset):
    """Get the x starting position if we want to paint s centred."""
    w = len(s) * char_width
    textArea = areaWidth - offset * 2 - 1
    return (textArea - w) / 2

def addChar(ch, x, y, xOffset, yOffset, width, height, drawable=None):
    """Paint the character ch at position x, y in the window.

    Return the (width, height) of the character painted.  (will be useful if
    we implement proportional char sets)

    the library only supports lower ascii: 32-127.  any other will cause a
    ValueError exception.

    if the character being painted falls partly out of the boundary, it will
    be clipped without causing an exception.  this works even if the
    character starts out of the boundary.
    """

    if not (32 <= ord(ch) <= 127):
        #print ord(ch)
        #raise ValueError, "Unsupported Char: '%s'(%d)" % (ch, ord(ch))
        pass

    # linelength is the amount of bits the character set uses on each row.
    linelength = charset_width - (charset_width % char_width)
    # pos is the horizontal index of the box containing ch.
    pos = (ord(ch)-32) * char_width
    # translate pos into chX, chY, rolling back and down each linelength
    # bits.  character definition start at row 64, column 0.
    chY = int((pos / linelength) * char_height + charset_start)
    chX = int(pos % linelength)
    targX = int(x + xOffset)
    targY = int(y + yOffset)
    chW = char_width
    if ch in "',.:;":
        chW = char_twidth
    if drawable is None:
        pywmgeneral.copyXPMArea(chX, chY, chW, char_height, targX, targY)
    else:
        drawable.xCopyAreaFromWindow(chX, chY, chW, char_height, targX, targY)
    return (chW, char_height)

def addString(s, x, y, xOffset=0, yOffset=0, width=None, height=None, drawable=None):
    """Add a string at the given x and y positions.

    Call addChar repeatedely, so the same exception rules apply."""
    lastW = 0
    for letter in s:
        w, h = addChar(letter, x + lastW, y,
                       xOffset, yOffset, width, height,
                       drawable)
        lastW += w

def getVertSpacing(numLines, margin, height, yOffset):
    """Return the optimal spacing between a number of lines.

    margin is the space we want between the first line and the top."""
    h = height - (numLines * char_height + 1) - yOffset * 2 - margin
    return h / (numLines - 1)


def readXPM(fileName):
    """Read the xpm in filename.

    Return the pair (palette, pixels).

    palette is a dictionary char->color (no translation attempted).
    pixels is a list of strings.

    Raise IOError if we run into trouble when trying to read the file.  This
    function has not been tested extensively.  do not try to use more than
    """
    f = open(fileName, 'r')
    lines = [l.rstrip('\n') for l in f.readlines()]
    s = ''.join(lines)
    res = []
    while 1:
        nextStrStart = s.find('"')
        if nextStrStart != -1:
            nextStrEnd = s.find('"', nextStrStart + 1)
            if nextStrEnd != -1:
                res.append(s[nextStrStart+1:nextStrEnd])
                s = s[nextStrEnd+1:]
                continue
        break

    palette = {}
    colorCount = int(res[0].split(' ')[2])
    charsPerColor = int(res[0].split(' ')[3])
    assert(charsPerColor == 1)
    for i in range(colorCount):
        colorChar = res[i+1][0]
        colorName = res[i+1][1:].split()[1]
        palette[colorChar] = colorName
    res = res[1 + int(res[0].split(' ')[2]):]
    return palette, res

def initPixmap(background=None,
               patterns=None,
               style='3d',
               width=64, height=64,
               margin=3,
               font_name='6x8',
               bg=0, fg=7,
               palette=None, debug = 0):
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

    # initially all characters 32-126 are available...
    available = dict([(chr(ch), True) for ch in range(32,127)])

    # a palette is a dictionary from one single letter to an hexadecimal
    # color.  per default we offer a 16 colors palette including what I
    # consider the basic colors:
    basic_colors = ['black', 'blue3', 'green3', 'cyan3',
                    'red3', 'magenta3', 'yellow3', 'gray',
                    'gray41', 'blue1', 'green1', 'cyan1',
                    'red1', 'magenta1', 'yellow1', 'white']

    if isinstance(patterns, str):
        palette, patterns = readXPM(patterns)
    if isinstance(background, str):
        palette, background = readXPM(background)

    alter_palette, palette = palette, {}
    for name, index in zip(basic_colors, list(range(16))):
        palette['%x'%index] = getColorCode(name)
        available['%x'%index] = False
    palette[' '] = 'None'
    available[' '] = False

    # palette = {' ': None, '0':..., '1':..., ..., 'f':...}

    if alter_palette is not None:
        # alter_palette contains 0..15/chr -> 'name'/'#hex'
        # interpret that as chr -> '#hex'
        for k,v in list(alter_palette.items()):
            if isinstance(k, int):
                k = '%x' % k
            k = k[0]
            if not v.startswith('#'):
                v = getColorCode(v)
            palette[k] = v
            available[k] = False

    if isinstance(bg, int):
        bg = '%x' % bg
    if isinstance(fg, int):
        fg = '%x' % fg

    if patterns is None:
        patterns = [bg*width]*height

    if style == '3d': ex = '7'
    else: ex = bg

    if background is None:
        background = [
            ' '*width
            for item in range(margin)
            ] + [
            ' '*margin + bg*(width-2*margin-1) + ex + ' '*(margin)
            for item in range(margin,height-margin-1)
            ] + [
            ' '*margin + ex*(width-2*margin) + ' '*(margin)
            ] + [
            ' '*width for item in range(margin)
            ]
    elif isinstance(background, list) and not isinstance(background[0], (str,)):
        nbackground = [[' ']*width for i in range(height)]
        for ((left, top),(right, bottom)) in background:
            for x in range(left, right+1):
                for y in range(top, bottom):
                    if x < right:
                        nbackground[y][x] = bg
                    else:
                        nbackground[y][x] = ex
                nbackground[bottom][x] = ex
        background = [ ''.join(item) for item in nbackground ]

    global tile_width, tile_height
    tile_width = width
    tile_height = height

    global pattern_start
    pattern_start = height

    def readFont(font_name):
        # read xpm, return cell_size, definition and palette.
        font_palette, fontdef = readXPM(__file__[:__file__.rfind(os.sep) + 1] + font_name + '.xpm')

        import re
        m = re.match(r'.*?(?P<w>[0-9]+)(?:\((?P<t>[0-9]+)\))?x(?P<h>[0-9]+).*', font_name)
        if not m:
            raise ValueError("can't infer font size from name (does not contain wxh)")
        width = int(m.groupdict().get('w'))
        height = int(m.groupdict().get('h'))
        thinwidth = int(m.groupdict().get('t') or width)

        replace = []
        for code, value in list(font_palette.items()):
            if available[code]:
                continue
            if palette[code] != font_palette[code]:
                newcode = [k for k in available if available[k] and not k in font_palette][0]
                available[newcode] = False
                replace.append((code, newcode))
        for code, newcode in replace:
            for row, i in zip(fontdef,list(range(len(fontdef)))):
                fontdef[i] = row.replace(code, newcode)
            font_palette[newcode] = font_palette[code]
            del font_palette[code]
        return width, height, thinwidth, fontdef, font_palette

    def calibrateFontPalette(font_palette, fg, bg):
        """computes modified font_palette

        takes into account only intensity of original value.

        fg, bg must be of the form #xxxxxx

        the corresponding calibrated color lies at a specific percentage of
        the vector going from background to foreground."""

        bg_point = [int(bg[i*2+1:i*2+3],16) for i in range(3)]
        fg_point = [int(fg[i*2+1:i*2+3],16) for i in range(3)]

        fg_vec = [f-b for (f,b) in zip(fg_point,bg_point)]

        new_font_palette = {}
        for k, colorName in list(font_palette.items()):
            if colorName == 'None':
                continue
            origColor = getColorCode(colorName)[1:]
            origRgb = [int(origColor[i*2:i*2+2],16)/256. for i in range(3)]
            intensity = sum(origRgb) / 3
            newRgb = [i * intensity + base for i,base in zip(fg_vec, bg_point)]
            new_font_palette[k] = '#'+''.join(["%02x"% int(i) for i in newRgb])

        return new_font_palette

    global char_width, char_height, char_twidth
    char_width, char_height, char_twidth, fontdef, font_palette = readFont(font_name)
    font_palette = calibrateFontPalette(font_palette, palette[fg], palette[bg])

    palette.update(font_palette)

    global charset_start, charset_width
    charset_start = height + len(patterns)
    charset_width = len(fontdef[0])

    xpmwidth = max(len(background[0]), len(patterns[0]), len(fontdef[0]))
    xpmheight = len(background)+len(patterns)+len(fontdef)

    xpm = [
        '%s %s %d 1' % (xpmwidth, xpmheight, len(palette)),
        ] + [
        '%s\tc %s' % (k,v)
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
    if debug:
        print('/* XPM */\nstatic char *_x_[] = {')
        for item in xpm:
            print(('"%s",' % item))
        print('};')
    pywmgeneral.includePixmap(xpm)
    return char_width, char_height

def openXwindow(argv, w, h):
    """Open the X window of given width and height.

    The XBM mask is here created from the upper left rectangle of the
    XPM using the given width and height."""
    pywmgeneral.openXwindow(len(argv), argv, w, h)

def redraw():
    """Redraw the window."""
    pywmgeneral.redrawWindow()

def redrawXY(x, y):
    """Redraw a given region of the window."""
    pywmgeneral.redrawWindowXY(x, y)

def copyXPMArea(sourceX, sourceY, width, height, targetX, targetY):
    """Copy an area of the global XPM."""
    (sourceX, sourceY, width, height, targetX,
     targetY) = (int(sourceX), int(sourceY), int(width), int(height),
                 int(targetX), int(targetY))
    if width > 0 or height > 0:
        pywmgeneral.copyXPMArea(sourceX, sourceY, width, height,
                                targetX, targetY)

def addMouseRegion(index, left, top, right=None, bottom=None, width=None, height=None):
    """Add a mouse region in the window."""
    if right is bottom is None:
        right = left + width
        bottom = top + height
    pywmgeneral.addMouseRegion(index, left, top, right, bottom)

def checkMouseRegion(x, y):
    """Check if x,y is in any mouse region. Return that region, otherwise -1.
    """
    return pywmgeneral.checkMouseRegion(x, y)

def getEvent():
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
    return pywmgeneral.checkForEvents()

def getColorCode(colorName, rgbFileName=None):
    """Convert a color to rgb code usable in an xpm.

    We use the file rgbFileName for looking up the colors. Return None
    if we find no match. The rgbFileName should be like the one found in
    /usr/lib/X11R6/rgb.txt on most sytems.
    """
    if colorName.startswith('#'):
        return colorName

    if rgbFileName is None:
        for fn in defaultRGBFileList:
            if os.access(fn, os.R_OK):
                rgbFileName = fn
                break
    if rgbFileName is None:
        raise ValueError('cannot find rgb file')

    f = open(rgbFileName, 'r')
    lines = f.readlines()
    f.close()
    for l in lines:
        if l[0] != '!':
            words = l.split()
            if len(words) > 3:
                name = ' '.join(words[3:])
                if colorName.lower() == name.lower():
                    # Found the right color, get it's code
                    try:
                        r = int(words[0])
                        g = int(words[1])
                        b = int(words[2])
                    except ValueError:
                        continue
                    rgbstr = '#%02x%02x%02x' % (r,g,b)
                    return rgbstr
    return None

