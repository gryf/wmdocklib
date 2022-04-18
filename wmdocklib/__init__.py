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
            event = helpers.get_event()

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

        if self.font:
            # Read provided xpm file with font definition
            palette, fontdef = helpers.read_xpm(self.font)
            font_width = self.charset_width = len(fontdef[0])
            font_height = len(fontdef)

            if self.font_dimentions is None:
                (self.char_width,
                 self.char_height) = helpers.get_font_char_size(self.font)
            else:
                self.char_width, self.char_height = self.font_dimentions

            if self.char_width is None:
                # font filename doesn't provide hints regarding font size
                raise ValueError('Cannot infer font size either from font '
                                 'name (does not contain wxh), or from '
                                 'font_dimentions attribute')
        else:
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

        palette_values = {v: k for k, v in palette.items()}

        bevel = helpers.get_unique_key(palette)
        palette[bevel] = self.bevel_color

        # handle bg color
        bg = helpers.normalize_color(self.background_color)
        key = helpers.get_unique_key(palette)
        palette[key] = bg
        bg = key

        if patterns is None:
            patterns = [bg * self.width] * self.height

        if self.style == '3d':
            ex = bevel
        else:
            ex = bg

        if self.background is None:
            self.background = (
                [' ' * self.width for item in range(self.margin)] +
                [' ' * self.margin + bg * (self.width - 2 * self.margin - 1) +
                 ex + ' ' * (self.margin)
                 for item in range(self.margin,
                                   self.height - self.margin - 1)] +
                [' ' * self.margin + ex * (self.width - 2 * self.margin) +
                 ' ' * (self.margin)] +
                [' ' * self.width for item in range(self.margin)])

        elif isinstance(self.background,
                        list) and not isinstance(self.background[0], str):
            nbackground = [[' '] * self.width for i in range(self.height)]
            for ((left, top), (right, bottom)) in self.background:
                for x in range(left, right+1):
                    for y in range(top, bottom):
                        if x < right:
                            nbackground[y][x] = bg
                        else:
                            nbackground[y][x] = ex
                    nbackground[bottom][x] = ex
            self.background = [''.join(item) for item in nbackground]

        self.charset_start = self.height + len(patterns)

        xpmwidth = max(len(self.background[0]), len(patterns[0]), font_width)
        xpmheight = len(self.background) + len(patterns) + font_height

        xpm = ([f'{xpmwidth} {xpmheight} {len(palette)} 1'] +
               [f'{k}\tc {v}'
                for k, v in list(palette.items()) if v == 'None'] +
               [f'{k}\tc {v}'
                for k, v in list(palette.items()) if v != 'None'] +
               [item + ' ' * (xpmwidth - len(item))
                for item in self.background + patterns])
        if self.font:
            xpm += [line + ' ' * (xpmwidth - len(line)) for line in fontdef]

        with open('/tmp/foo.xpm', 'w') as fobj:
            fobj.write('/* XPM */\nstatic char *_x_[] = {\n')
            for item in xpm:
                fobj.write(f'"{item}"\n')
            fobj.write('};\n')

        pywmgeneral.include_pixmap(xpm)

    def redraw(self):
        pywmgeneral.redraw_window()
