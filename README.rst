=========
wmdocklib
=========

This is a library which was extracted from a pretty much dead `pywmdockapps`_
project, and is meant to help with writing Window Maker dockapps in Python.


Installation
============

The installation from source expect there is a C compiler around, as well as X
and Python headers/dev packages. It might be installed using virtualenv, or
system wide:

.. code::shell-session

   $ pip install .

Note, that you'll need C compiler and Xorg dev package to build the C
extension.


Usage
=====

There is a base class, a foundation for building custom dockapps. Simplest
possible usage would be:

.. code:: python

   import wmdocklib

   app = wmdocklib.DockApp()
   app.run()

this will run dockapp, which doesn't do anything, it just displays black
background with 3 pixel wide border.

To build something useful, there will be a need for adding implementation,
and optionally bitmaps in XPM format for additional graphical elements, like
fonts, buttons, app mask and so on.

To create an application, it simple as:

- create a class inherited from DockApp,
- implement ``run()`` and ``main_loop()`` methods,
- optionally, add graphics (like bitmap charset), command line options handling,
  and possibly configuration file.

So below is the example for displaying random number:

.. code:: python
   :number-lines:

   import random
   import time

   import wmdocklib


   FONTS = '''\
   /* XPM */
   static char *square_[] = {
   "156 8 2 1",
   "  c black",
   "% c gray100",
   "        %    % %   % %          % %                                                          %  %%%%%   %   %%%%% %%%%% %   % %%%%% %%%%% %%%%% %%%%% %%%%% ",
   "        %    % %   % %            %                                                          %  %   %  %%       %     % %   % %     %         % %   % %   % ",
   "        %    % %  %%%%%          %%                                                         %%  %   %   %       %     % %   % %     %         % %   % %   % ",
   "        %          % %           %                                            %%%%%         %   %   %   %   %%%%%  %%%% %%%%% %%%%% %%%%%     % %%%%% %%%%% ",
   "                  %%%%%         %%                                        %%               %%   %   %   %   %         %     %     % %   %     % %   %     % ",
   "                   % %          %                                         %%          %%   %    %   %   %   %         %     %     % %   %     % %   %     % ",
   "        %          % %          % %                                        %          %%   %    %%%%%  %%%  %%%%% %%%%%     % %%%%% %%%%%     % %%%%% %%%%% ",
   "                                                                          %                                                                                 ",
   };
   '''

   class MyDockApp(wmdocklib.DockApp):

       font_dimentions = (6, 8)

       def __init__(self):
           super().__init__()
           self.fonts = [wmdocklib.BitmapFonts(FONTS, self.dimensions)]

       def run(self):
           self.prepare_pixmaps()
           self.open_xwindow()
           self.main_loop()

       def main_loop(self):
           while True:
               self.fonts[0].add_string(f'{random.randint(0, 999):3}', 1, 1)
               self.redraw()
               time.sleep(0.1)


   app = MyDockApp()
   app.run()


In this simple application, there is (partial) charset defined (lines 7-22),
which is assigned to the ``self.font`` (this attribute can be either a string
with XPM data like above, or just a filename), by which it will be indicated
that font data will be used.

Than, class ``MyDockApp`` is defined, with overriden methods ``run()`` and
``main_loop()``.

As for method ``run()`` it is kind of initialization of the object and window.
By calling ``prepare_pixmaps`` there will be prepared combined bitmaps of
background, pattern and (optionally) fonts, coordinates for the charset, it's
width and heigh, and finally load prepared pixmap to memory.

Function ``open_xwindow`` will create and show the window. And than main loop
is called, which iterate endlessly calling ``add_string()`` method for display
string on the dockapp. Note, that ``add_string()`` method (and underlying
``add_char()``) assuming, that fonts in bitmap are ordered just like ``ord()``
will do.

Method ``redraw()`` will trigger entire window to be refreshed.


Lowlevel module
===============

There is a C module called ``pywmgeneral``, which exposes couple of functions,
which are useful building custom dockapps.

- ``open_xwindow`` - this function is responsible for creating an application
  window, with all the wm hints set to appropriate values, so that we can get
  docked app in Window Maker or borderless window in most of other window
  managers. This method should be run after ``include_pixmap`` is called, since
  (any) bitmap is expected to be a part of the app. It accepts four arguments
  - ``argcount`` - number of arguments in next argument list
  - ``argument list`` - there are two arguments which can be passed to this
    function ``-geometry`` and ``-disply``. All the rest will be ignored, so
    it's safe to pass ``len(sys.argv)`` and ``sys.argv`` as a *argcount* and
    *argument list* respectively.
  - ``width`` - application width, whatever value is accepted. By default
    ``64``.
  - ``height`` - application height, whatever value is accepted. By default
    ``64``.
- ``include_pixmap`` - function which loads and picture in XPM format as a
  string. The only argument here is a list of lines of the XPM image.
- ``redraw_window`` - repaint the window content.
- ``redraw_window_xy`` - repaint the window region counting from the provided
  coordinates (*x* and *y*) to the end of the application width and height.
- ``add_mouse_region`` - define a region for checking mouse events. This
  function may be repeated with definition for several regions using index.
  Arguments:
  - ``index`` - simple region integer identifier
  - ``left``, ``top``, ``right``, ``bottom`` - coordinates for the area
- ``check_mouse_region`` - function for check if certain defined mouse region
  has any event. It returns id of the mouse region, or -1 if there were no
  events within provided coordinates.
- ``copy_xpm_area`` - copy XPM area from provided coordinates to new location.
  Arguments:
  - ``source x``, ``source y`` - coordinate of the area to be copied from
  - ``source width``, ``source height`` - dimension of the block to be copied
  - ``target x``, ``targed y`` - destination coordinates.
- ``check_for_events`` - check for events. Return ``None`` if there is no
  events, or dictionary with information about type of the event. Currently
  supported events are as follows:
  - ``keypress``
  - ``buttonpress``
  - ``buttonrelease``
  - ``destroynotify``


License
=======

This work is licensed under (L)GPL license.

.. _pywmdockapps: http://pywmdockapps.sourceforge.net
