import sys

from wmdocklib import helpers


class DockApp:
    width = 64
    height = 64
    x_offset = 4
    y_offset = 3
    palette = {"1": "black",
               "2": "white"}
    background_color = 'black'

    def __init__(self, args=None):
        self.args = args
        self.charset_start = None
        self.charset_width = None
        self.char_width = None
        self.char_height = None
        self.font = ''

    def check_for_events(self):
        event = helpers.get_event()
        while event is not None:
            if event['type'] == 'destroynotify':
                sys.exit(0)
            event = helpers.get_event()

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
