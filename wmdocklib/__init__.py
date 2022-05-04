import os
import sys
import tempfile
import time

from wmdocklib import helpers
from wmdocklib import pywmgeneral


class DockApp:
    width = 64
    height = 64
    margin = 3
    palette = {"1": "black",
               "2": "white"}
    background_color = 'black'
    style = '3d'
    bevel_color = '#bebebe'

    def __init__(self, args=None):
        self.args = args
        self.fonts = []
        self.background = None
        self.patterns = None
        self._debug = False

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

        The (width)x(height) upper left area is the work area in which we put
        what we want to be displayed. Also, nothing prevents us from putting
        anything on the right of that image and do the copying from there.

        The remaining upper right area contains patterns that can be used for
        blanking/resetting portions of the displayed area.

        The remaining lower area defines the character sets. This is
        initialized using the corresponding named character set. Fonts
        definition are holded by corresponding instances of BitmapFonts class.

        Palette is a dictionary
        1: of integers <- [0..15] to colors.
        2: of single chars to colors.

        a default palette is provided, and can be silently overwritten with the
        one passed as parameter.

        The XBM mask is created out of the XPM.
        """
        palette = {}
        patterns = self.patterns

        if self.background:
            palette, background = helpers.read_xpm(self.background)

        if self.fonts:
            for font in self.fonts:
                if not palette:
                    palette = font.palette
                else:
                    # merge background and font_palette and remap characters
                    palette, fontdef = helpers.merge_palettes(palette,
                                                              font.palette,
                                                              font.bitmap)
                    font.bitmap = fontdef

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
            sp = ' '
            background = (
                [f'{sp:{self.width}}' for _ in range(self.margin)] +
                [f'{sp:{self.margin}}' +
                 bg_color * (self.width - 2 * self.margin - 1) + f'{ex}'
                 f'{sp:{self.margin}}'
                 for _ in range(self.margin, self.height - self.margin - 1)] +
                [f'{sp:{self.margin}}' + ex * (self.width - 2 * self.margin) +
                 f'{sp:{self.margin}}'] +
                [f'{sp:{self.width}}' for _ in range(self.margin)])

        charset_start = self.height + len(patterns)
        for font in self.fonts:
            font.update(charset_start)
            charset_start += font.charset_height

        xpmwidth = max(len(background[0]), len(patterns[0]),
                       max([f.charset_width for f in self.fonts]))
        xpmheight = (len(background) + len(patterns) +
                     sum([f.charset_height for f in self.fonts]))

        xpm = ([f'{xpmwidth} {xpmheight} {len(palette)} 1'] +
               [f'{k}\tc {v}'
                for k, v in list(palette.items()) if v == 'None'] +
               [f'{k}\tc {v}'
                for k, v in list(palette.items()) if v != 'None'] +
               [item + ' ' * (xpmwidth - len(item))
                for item in background + patterns])
        if self.fonts:
            xpm += [f"{line:{xpmwidth}}" for x in self.fonts
                    for line in x.bitmap]

        if self._debug:
            fd, fname = tempfile.mkstemp(suffix='.xpm')
            os.close(fd)
            with open(fname, 'w') as fobj:
                fobj.write('/* XPM */\nstatic char *_x_[] = {\n')
                for item in xpm:
                    fobj.write(f'"{item}"\n')
                fobj.write('};\n')
            print(f'Saved XPM file under {fname}.')

        pywmgeneral.include_pixmap(xpm)

    def redraw(self):
        pywmgeneral.redraw_window()


class BitmapFonts:
    """
    A class for representing a character set.
    """
    x_offset = 3
    y_offset = 3

    def __init__(self, font_data, dimensions=None):
        """
        Load and initialize font data. font_data might be either string.
        """
        self.palette = None
        self.bitmap = None
        self.charset_width = None
        self.charset_height = None
        self.charset_start = None
        self.width = 0
        self.height = 0
        self.font_dimentions = (0, 0)
        if dimensions:
            self.font_dimentions = dimensions
        self._load_font(font_data)
        self._set_font_size(font_data)

    def update(self, charset_start):
        """
        Update information on font position in merged pixmap, so that methods
        add_string/add_char can calculate char position correctly.
        """
        self.charset_start = charset_start

    def add_char(self, ch, x, y, drawable=None):
        """Paint the character ch at position x, y in the window.

        if the character being painted falls partly out of the boundary, it
        will be clipped without causing an exception.  this works even if the
        character starts out of the boundary.
        """
        # linelength is the amount of bits the character set uses on each row.
        linelength = self.charset_width - (self.charset_width %
                                           self.width)
        # pos is the horizontal index of the box containing ch.
        pos = (ord(ch)-32) * self.width
        # translate pos into ch_x, ch_y, rolling back and down each linelength
        # bits.  character definition start at row 64, column 0.
        ch_y = int((pos / linelength)) * self.height + self.charset_start
        ch_x = pos % linelength
        target_x = x + self.x_offset
        target_y = y + self.y_offset

        if drawable is None:
            pywmgeneral.copy_xpm_area(ch_x, ch_y, self.width,
                                      self.height, target_x, target_y)
        else:
            drawable.xCopyAreaFromWindow(ch_x, ch_y, self.width,
                                         self.height, target_x, target_y)

    def add_string(self, string, x, y, drawable=None):
        """Add a string at the given x and y positions.

        Call add_char repeatedely, so the same exception rules apply."""
        last_width = 0
        for letter in string:
            self.add_char(letter, x + last_width, y, drawable)
            last_width += self.width

    def _set_font_size(self, font_data):
        if self.font_dimentions[0]:
            self.width, self.height = self.font_dimentions
        else:
            self.width, self.height = helpers.get_font_char_size(font_data)

        if not self.width:
            # font filename doesn't provide hints regarding font size
            raise ValueError('Cannot infer font size either from font '
                             'name (does not contain wxh), or from '
                             'font_dimentions attribute')

    def _load_font(self, font_data):
        self.palette, self.bitmap = helpers.read_xpm(font_data)
        self.charset_width = len(self.bitmap[0])
        self.charset_height = len(self.bitmap)
