import sys

from wmdocklib import helpers


class DockApp:
    width = 64
    height = 64
    x_offset = 4
    y_offset = 4
    palette = {"1": "black",
               "2": "white"}

    def __init__(self, args=None):
        self._args = args
        self._charset_start = None
        self._charset_width = None

    def check_for_events(self):
        event = helpers.get_event()
        while event is not None:
            if event['type'] == 'destroynotify':
                sys.exit(0)
            event = helpers.get_event()
