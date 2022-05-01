import time
import sys

from wmdocklib import helpers
from wmdocklib import pywmgeneral


class DockApp:
    width = 64
    height = 64
    margin = 3
    x_offset = 3
    y_offset = 3
    palette = {"1": "black",
               "2": "white"}
    background_color = 'black'
    style = '3d'
    bevel_color = '#bebebe'
    font_dimentions = None

    def __init__(self, args=None):
        self.args = args
        self.charset_start = None
        self.charset_width = 0
        self.char_width = None
        self.char_height = None
        self.font = None
        self.background = None
        self.patterns = None

    def check_for_events(self):
        event = helpers.get_event()
        while event is not None:
            if event['type'] == 'destroynotify':
                sys.exit(0)
            return event

    def run(self):
        self.prepare_pixmaps()
        self.open_xwindow()

        try:
            self.main_loop()
        except KeyboardInterrupt:
            pass

    def main_loop(self):
        while True:
            self.check_for_events()
            self.redraw()
            time.sleep(0.3)

    def open_xwindow(self):
        """Open the X window of given width and height.

        The XBM mask is here created from the upper left rectangle of the
        XPM using the given width and height."""
        pywmgeneral.open_xwindow(len(sys.argv), sys.argv, self.width,
                                 self.height)

    def prepare_pixmaps(self):
        """builds and sets the pixmap of the program.

        the (width)x(height) upper left area is the work area in which we put
        what we want to be displayed.

        the remaining upper right area contains patterns that can be used for
        blanking/resetting portions of the displayed area.

        the remaining lower area defines the character set. this is initialized
        using the corresponding named character set. a file with this name must
        be found somewhere in the path.

        palette is a dictionary
        1: of integers <- [0..15] to colors.
        2: of single chars to colors.

        a default palette is provided, and can be silently overwritten with the
        one passed as parameter.

        The XBM mask is created out of the XPM.
        """
        palette = {}
        patterns = self.patterns
        font_width = 0
        font_height = 0

        if self.background:
            palette, background = helpers.read_xpm(self.background)

        if self.font:
            # Read provided xpm file with font definition
            font_palette, fontdef = helpers.read_xpm(self.font)
            font_width = self.charset_width = len(fontdef[0])
            font_height = len(fontdef)
            if not palette:
                palette = font_palette
            else:
                # merge background and font_palette and remap characters
                palette, fontdef = helpers.merge_palettes(palette,
                                                          font_palette,
                                                          fontdef)

            # user provided font dimension tuple have precedence
            if self.font_dimentions is not None:
                self.char_width, self.char_height = self.font_dimentions
            else:
                (self.char_width,
                 self.char_height) = helpers.get_font_char_size(self.font)

            if self.char_width is None:
                # font filename doesn't provide hints regarding font size
                raise ValueError('Cannot infer font size either from font '
                                 'name (does not contain wxh), or from '
                                 'font_dimentions attribute')

        if not palette:
            palette[' '] = 'None'

        palette_values = {v: k for k, v in palette.items()}

        # merge defined palette colors to existing one
        if self.palette:
            for key, color in self.palette.items():
                color = helpers.normalize_color(color)
                if color in palette_values:
                    continue
                if key not in palette:
                    palette[key] = color
                else:
                    new_key = helpers.get_unique_key(palette)
                    palette[new_key] = color

        bevel = helpers.get_unique_key(palette)
        palette[bevel] = self.bevel_color

        # handle bg color
        bg_color = helpers.normalize_color(self.background_color)
        key = helpers.get_unique_key(palette)
        palette[key] = bg_color
        bg_color = key

        if patterns is None:
            patterns = [bg_color * self.width] * self.height

        if self.style == '3d':
            ex = bevel
        else:
            ex = bg_color

        if self.background is None:
            background = (
                [' ' * self.width for item in range(self.margin)] +
                [' ' * self.margin +
                 bg_color * (self.width - 2 * self.margin - 1) +
                 ex + ' ' * (self.margin)
                 for item in range(self.margin,
                                   self.height - self.margin - 1)] +
                [' ' * self.margin + ex * (self.width - 2 * self.margin) +
                 ' ' * (self.margin)] +
                [' ' * self.width for item in range(self.margin)])

        self.charset_start = self.height + len(patterns)

        xpmwidth = max(len(background[0]), len(patterns[0]), font_width)
        xpmheight = len(background) + len(patterns) + font_height

        xpm = ([f'{xpmwidth} {xpmheight} {len(palette)} 1'] +
               [f'{k}\tc {v}'
                for k, v in list(palette.items()) if v == 'None'] +
               [f'{k}\tc {v}'
                for k, v in list(palette.items()) if v != 'None'] +
               [item + ' ' * (xpmwidth - len(item))
                for item in background + patterns])
        if self.font:
            xpm += [line + ' ' * (xpmwidth - len(line)) for line in fontdef]

        with open('/tmp/foo.xpm', 'w') as fobj:
            fobj.write('/* XPM */\nstatic char *_x_[] = {\n')
            for item in xpm:
                fobj.write(f'"{item}"\n')
            fobj.write('};\n')

        pywmgeneral.include_pixmap(xpm)

    def add_char(self, ch, x, y, drawable=None):
        """Paint the character ch at position x, y in the window.

        if the character being painted falls partly out of the boundary, it
        will be clipped without causing an exception.  this works even if the
        character starts out of the boundary.
        """
        # linelength is the amount of bits the character set uses on each row.
        linelength = self.charset_width - (self.charset_width %
                                           self.char_width)
        # pos is the horizontal index of the box containing ch.
        pos = (ord(ch)-32) * self.char_width
        # translate pos into ch_x, ch_y, rolling back and down each linelength
        # bits.  character definition start at row 64, column 0.
        ch_y = int((pos / linelength)) * self.char_height + self.charset_start
        ch_x = pos % linelength
        target_x = x + self.x_offset
        target_y = y + self.y_offset

        if drawable is None:
            pywmgeneral.copy_xpm_area(ch_x, ch_y, self.char_width,
                                      self.char_height, target_x, target_y)
        else:
            drawable.xCopyAreaFromWindow(ch_x, ch_y, self.char_width,
                                         self.char_height, target_x, target_y)

    def add_string(self, string, x, y, drawable=None):
        """Add a string at the given x and y positions.

        Call add_char repeatedely, so the same exception rules apply."""
        last_width = 0
        for letter in string:
            self.add_char(letter, x + last_width, y, drawable)
            last_width += self.char_width

    def redraw(self):
        pywmgeneral.redraw_window()
