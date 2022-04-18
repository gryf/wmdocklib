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

    def prepare_pixmaps(self, background=None, patterns=None, style='3d',
                        margin=3):

        dockapp_size = (self.width, self.height)

        (self.char_width, self.char_height, self.charset_start,
         self.charset_width) = helpers.init_pixmap(background, patterns,
                                                   style, dockapp_size[0],
                                                   dockapp_size[1], margin,
                                                   self.font,
                                                   self.background_color,
                                                   self.palette)
