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
