#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''pywmgeneric.py

WindowMaker dockapp to display the output from an external program, or the
string returned from a python function. Mouse actions can be associated with
the displayed text.

Copyright (C) 2003 Kristoffer Erlandsson

Licensed under the GNU General Public License.


Changes
2003-07-02 Kristoffer Erlandsson
Added support for up to 10 mouse buttons.
The char translation now handles both upper and lower case.

2003-06-29 Kristoffer Erlandsson
Additional error checking around string interpolations from cfg file.

2003-06-27 Kristoffer Erlandsson
First working version
'''

usage = '''pywmgeneric.py [options]
Available options are:
    -h, --help                  print this help
    -t, --text <color>          set the text color
    -b, --background <color>    set the background color
    -r, --rgbfile <file>        set the rgb file to get color codes from
    -c, --configfile <file>     set the config file to use
'''

import sys
import os
import time
import string
import ConfigParser
import getopt
import popen2

from pywmgeneral import pywmhelpers

class UserMethods:
    """Put methods that should be called when the action is method=... here.

    The action methods should return a function, which in turn returns
    the string to be displayed (if no 'display =' exists) and stored
    for later retreival.

    The mouse action methods gets the entry instance as an argument. Return
    value doesn't matter.

    An instance of this class is created at initialization and passed to all
    entries, so keep in mind that they share the same object.

    THE METHODS ALLREADY HERE ARE JUST SAMPLES AND WILL PROBABLY NOT WORK
    WITH YOUR SYSTEM.
    """

    userTicks = sysTicks = niceTicks = idleTicks = 0
    
    def getCpuTemp(self):
        def result():
            try:
                f = file('/proc/stat', 'r')
            except IOError:
                return lambda: 'error'

            import re
            cpuinfo = re.compile(r'^cpu.* (?P<user>[0-9]+) +(?P<nice>[0-9]+)'
                                 r'+(?P<sys>[0-9]+) +(?P<idle>[0-9]+)')
            match = dict([(k, int(v))
                           for (k,v) in cpuinfo.match(f.readline()).groupdict().items()])
            totalTicks = ((match['user'] - self.userTicks) +
                          (match['sys'] - self.sysTicks) +
                          (match['nice'] - self.niceTicks) +
                          (match['idle'] - self.idleTicks));

            if (totalTicks > 0):
                user = (100. * (match['user'] - self.userTicks)) / totalTicks;
                sys = (100. * (match['sys'] - self.sysTicks)) / totalTicks;
                nice = (100. * (match['nice'] - self.niceTicks)) / totalTicks;
                idle = (100. - (user + sys + nice));
            else:
                user = sys = nice = idle = 0;

            self.userTicks = match['user']
            self.sysTicks = match['sys']
            self.niceTicks = match['nice']
            self.idleTicks = match['idle']

            f.close()
            return '%02.f/%02.f/%02.f' % (user, nice, sys)
        return result

    def getSysTemp(self):
        try:
            f = file('/proc/sys/dev/sensors/w83697hf-isa-0290/temp1', 'r')
        except IOError:
            return lambda: 'error'
        temp = f.readline().split()[2]
        f.close()
        return lambda: 'sys: %s' % temp

    def showDnWithoutDescs(self, entry):
        '''Strip descriptions from some text where the descs are indented.

        Display it in an xmessage.
        '''
        text = entry.getAllText()
        s = '\n'.join([x for x in text.split('\n') if not x.startswith('   ')])
        os.system('xmessage "' + s.replace('"', r'\"') + '" &')
        
    def showTvWithoutDescs(self, entry):
        '''Strip descriptions from some text where the descs are indented.

        Display it in an xmessage.
        '''
        text = entry.getAllText()
        s='\n'.join([x for x in
            text.split('\n')[1:] if not x.startswith('   ')])
        s = s.replace('\n\n', '\n')
        os.system('xmessage "' + s.replace('"', r'\"') + '" &')

width = 64
height = 64

xOffset = 4
yOffset = 4

lettersStartX = 0
lettersStartY = 74
letterWidth = 6
letterHeight = 8

digitsStartX = 0
digitsStartY = 64
digitWidth = 6
digitHeight = 8

letters = 'abcdefghijklmnopqrstuvwxyz'
digits = '0123456789:/-%. '

maxChars = 9

defaultConfigFile = '~/.pywmgenericrc'
defaultRGBFiles = ('/usr/share/X11/rgb.txt', '/usr/X11R6/lib/X11/rgb.txt')

err = sys.stderr.write

def addString(s, x, y):
    '''Convenience function around pwymhelpers.addString.'''
    try:
        pywmhelpers.addString(s, x, y, letterWidth, letterHeight, lettersStartX,
                          lettersStartY, letters, digitWidth, digitHeight,
                          digitsStartX, digitsStartY, digits, xOffset, yOffset,
                          width, height)
    except ValueError, e:
        sys.stderr.write('Error when painting string:\n' + str(e) + '\n')
        sys.exit(3)

def clearLine(y):
    '''Clear a line of text at position y.'''
    pywmhelpers.copyXPMArea(72, yOffset, width - 2 * xOffset, letterHeight,
                            xOffset, y + yOffset)

def getXY(line):
    '''Return the x and y positions to be used at line line.'''
    return 0, line * (letterHeight + 3) + 1

def isTrue(s):
    """Return true if the string s can be interpreted as a true value.

    Raises ValueError if we get a string we don't like.
    """
    trueThings = ['on', 'yes', '1', 'true']
    falseThings = ['off', 'no', '0', 'false']
    if s in trueThings:
        return 1
    elif s in falseThings:
        return 0
    raise ValueError


class Entry:
    def __init__(self, line, updateDelay, action, mouseActions,
                 userMethods, display=None, scrollText=1):
        self._updateDelay = updateDelay
        self._line = line
        self._action = self._parseAction(action)
        self._mouseActions = [self._parseAction(a) for a in mouseActions]
        self._userMethods = userMethods
        self._display = display
        self._scrollText = scrollText

        self._scrollPos = 0
        self._tickCount = 0L

        self._runningProcs = []
        self._actionProc = None
        self._getTextMethod = None
        self._allText = ''
        self._displayLine = ''
        # Do one action when we start, so we are sure that one gets done even
        # if we do not want any other updates.
        self._doAction()
        self._lastActionAt = time.time()

    def _parseAction(self, action):
        '''Parse an action string, return (<action>, <argument string>).
        
        Or none if we get an empty action.'''
        if action:
            whatToDo = action.split()[0]
            argStr = action[len(whatToDo):].lstrip()
            return (whatToDo, argStr)
        return None

    def _execExternal(self, command):
        '''Exec an external command in the background.
        
        Return the running process as created by Popen3().'''
        proc = popen2.Popen3(command)
        self._runningProcs.append(proc)
        return proc

    def _doMouseAction(self, button):
        '''Perform the mouse action associated with a button.'''
        if len(self._mouseActions) < button:
            return  # Just for safety, shouldn't happen.
        item = self._mouseActions[button - 1]
        if item:
            # We have an action associated with the button.
            action, arg = item
        else:
            # No action associated with the button.
            return
        if action == 'exec':
            self._execExternal(self._expandStr(arg))
        elif action == 'method':
            try:
                method = getattr(self._userMethods, arg)
            except AttributeError:
                method = None
            if method:
                method(self)
            else:
                err("Warning: Method %s does not exist." % arg)
        elif action == 'update':
            self._doAction()
        else:
            err("Warning: Unknown mouse action: %s, ignoring.\n" % action)

    def _doAction(self):
        '''Perform the action associated with this entry.'''
        if self._action is None:
            return
        action, arg = self._action
        if action == 'exec':
            if self._actionProc is None :
                self._actionProc = self._execExternal(arg)
            else:
                if not self._actionProc in self._runningProcs:
                    # The action process since the last time is finished, we
                    # can start another one without risking that we get
                    # flooded by processes.
                    self._actionProc = self._execExternal(arg)
            self._getTextMethod = self._readFromActionProc
        elif action == 'method':
            try:
                method = getattr(self._userMethods, arg)
            except AttributeError:
                method = None
            if method:
                self._getTextMethod = method()
            else:
                err('Warning: method %s does not exist. Ignoring.\n' % arg)
        else:
            err("Warning: Unknown action: %s, ignoring.\n" % action)
            
    def _readFromActionProc(self):
        '''If our action process is ready, return the output. Otherwise None.
        '''
        if self._actionProc.poll() == -1:
            # Wait until the process is ready before we really read the text.
            return None
        # fromchild.read() will return '' if we allready have read the output
        # so there will be no harm in calling this method more times.
        return self._actionProc.fromchild.read()

    def _reapZombies(self):
        '''Poll all running childs. This will reap all zombies.'''
        i = 0
        for p in self._runningProcs:
            val = p.poll()
            if val != -1:
                self._runningProcs.pop(i)
            i += 1

    def _updateText(self):
        '''Get the text, update the display if it has changed.
        '''
        text = ''
        if self._getTextMethod:
            text = self._getTextMethod()
            # Only change the text if we get anything from the getTextMethod()
            if text:
                self._allText = text
        if self._display is None:
            # We have no display = in the config file, we want to
            # display the first line of the output of the action.
            if text:
                displayLine = text.split(os.linesep)[0]
            else:
                displayLine = self._displayLine
        else:
            displayLine = self._display
        if displayLine != self._displayLine:
            # Line to display has changed, display the new one.
            self._displayLine = displayLine
            self._scrollPos = 0
            self.displayText(displayLine)
        elif len(self._displayLine) > maxChars and self._scrollText:
            # Line is the same and is longer than the display and we
            # want to scroll it.
            if self._tickCount % 2 == 0:
                # Only scroll every third tick.
                self._scrollAndDisplay()

    def _scrollAndDisplay(self):
        '''Scroll the text one step to the left and redisplay it.

        When reaching the end, paint number of spaces before scrolling in the
        same line again from the right.
        '''
        if self._scrollPos >= \
                len(self._displayLine) + (maxChars - 4):
            self._scrollPos = 0
            self.displayText(self._displayLine)
        elif self._scrollPos >= len(self._displayLine) - 3:
            self._scrollPos += 1
            disp = self._displayLine[self._scrollPos:] + \
                ' ' * (maxChars - 3)
            diff = self._scrollPos - len(self._displayLine)
            if diff > 0:
                disp = disp[diff:]
            disp += self._displayLine
            self.displayText(disp)
        else:
            self._scrollPos += 1
            self.displayText(
                self._displayLine[self._scrollPos:])

    def tick1(self):
        '''Do things that should be done often.
        '''
        self._tickCount += 1
        self._reapZombies()
        self._updateText()
        currTime = time.time()
        if not self._updateDelay is None and \
                currTime - self._lastActionAt > self._updateDelay:
            # We want to do this last in the tick so the command gets the time
            # to finish before the next tick (if it's a fast one).
            self._lastActionAt = currTime
            self._doAction()

    def tick2(self):
        '''Do things that should be done a bit less often.
        '''
        pass

    def translateText(self, text):
        """Translate chars that can't be painted in the app to something nicer.
        
        Or nothing if we can't come up with something good. Could be nice to
        extend this function with chars more fitting for your language.
        """
        fromChars = 'áéíóúàèìòùâêîôûäëïöü'
        toChars = 'aeiouaeiouaeiouaeiou'
        deleteChars = []
        for c in text.lower():
            if not (c in letters or c in digits or c in fromChars):
                deleteChars.append(c)
        deleteChars = ''.join(deleteChars)
        trans = string.maketrans(fromChars, toChars)
        text = string.translate(text.lower(), trans, deleteChars)
        return text

    def getAllText(self):
        return self._allText

    def getDisplayedLine(self):
        return self._displayLine

    def _expandStr(self, s):
        '''Expand s, which now should be a line from an on_mouseX field.
        '''
        try:
            res = s % {'allText' : self._allText,
                        'displayedLine' : self._displayLine,
                        'allTextEscaped' : self._allText.replace('"', r'\"'),
                        'allTextButFirstLine' :
                            '\n'.join(self._allText.split('\n')[1:]),
                        'allTextButFirstLineEscaped' :
                            '\n'.join(self._allText.replace('"', '\"').
                                    split('\n')[1:])}
        except (KeyError, TypeError, ValueError):
            err(
              "Warning: %s doesn't expand correctly. Ignoring interpolations.\n"
              % s)
            res = s
        return res

    def displayText(self, text):
        '''Display text on the entry's line.
        
        Remove or translate characters that aren't supported. Truncate the text
        to fit in the app.
        '''
        x, y = getXY(self._line)
        clearLine(y)
        addString(self.translateText(text)[:maxChars], x, y)

    def mouseClicked(self, button):
        '''A mouse button has been clicked, do things.'''
        if 0 < button < 11:
            self._doMouseAction(button)

class PywmGeneric:
    def __init__(self, config):
        self._entrys = []
        line = 0
        um = UserMethods()
        for c in config:
            # Create our 5 entrys.
            if not c:
                self._entrys.append(None)
                line += 1
                continue
            delay = c.get('update_delay')
            if not delay is None:
                try:
                    delay = self.parseTimeStr(delay)
                except ValueError:
                    err("Malformed update_delay in section %s. "
                        % str(i))
                    err("Ignoring this section.\n")
                    self._entrys.append(None)
                    line += 1
                    continue
            action = c.get('action')
            display = c.get('display')
            if action is None and display is None:
                err(
                  "Warning: No action or display in section %d, ignoring it.\n"
                   % i)
                self._entrys.append(None)
            else:
                scroll = isTrue(c.get('scroll', '1'))
                # Get the mouse actions.
                mouseActions = []
                for i in range(10):
                    but = str(i + 1)
                    opt = 'on_mouse' + but
                    mouseActions.append(c.get(opt))
                self._entrys.append(Entry(line, delay, action,
                        mouseActions, um, display, scroll))
            line += 1
        self._setupMouseRegions()

    def _setupMouseRegions(self):
        for i in range(5):
            x, y = getXY(i)
            if not self._entrys[i] is None:
                pywmhelpers.addMouseRegion(i, x + xOffset, y + yOffset,
                    width - 2 * xOffset, y + yOffset + letterHeight)

    def parseTimeStr(self, timeStr):
        '''Take a string on a form like 10h and return the number of seconds.

        Raise ValueError if timeStr is on a bad format.
        '''
        multipliers = {'s' : 1, 'm' : 60, 'h' : 3600}
        timeStr = timeStr.strip()
        if timeStr:
            timeLetter = timeStr[-1]
            multiplier = multipliers.get(timeLetter)
            if not multiplier is None:
                timeNum = float(timeStr[:-1].strip())
                numSecs = timeNum * multiplier
                return numSecs
        raise ValueError, 'Invalid literal'

    def _checkForEvents(self):
        event = pywmhelpers.getEvent()
        while not event is None:
            if event['type'] == 'destroynotify':
                sys.exit(0)
            elif event['type'] == 'buttonrelease':
                region = pywmhelpers.checkMouseRegion(event['x'], event['y'])
                button = event['button']
                if region != -1:
                    if not self._entrys[region] is None:
                        self._entrys[region].mouseClicked(button)
            event = pywmhelpers.getEvent()

    def mainLoop(self):
        counter = -1
        while 1:
            counter += 1
            self._checkForEvents()
            if counter % 2 == 0:
                [e.tick1() for e in self._entrys if not e is None]
            if counter % 20 == 0:
                [e.tick2() for e in self._entrys if not e is None]

            if counter == 999999:
                counter = -1
            pywmhelpers.redraw()
            time.sleep(0.5)

def parseCommandLine(argv):
    '''Parse the commandline. Return a dictionary with options and values.'''
    shorts = 'ht:b:r:c:'
    longs = ['help', 'text=', 'background=', 'rgbfile=', 'configfile=']
    try:
        opts, nonOptArgs = getopt.getopt(argv[1:], shorts, longs)
    except getopt.GetoptError, e:
        err('Error when parsing commandline: ' + str(e) + '\n')
        err(usage)
        sys.exit(2)
    d = {} 
    for o, a in opts:
        if o in ('-h', '--help'):
            sys.stdout.write(usage)
            sys.exit(0)
        if o in ('-t', '--text'):
            d['textcolor'] = a
        if o in ('-b', '--background'):
            d['background'] = a
        if o in ('-r', '--rgbfile'):
            d['rgbfile'] = a
        if o in ('-c', '--configfile'):
            d['configfile'] = a
    return d

def parseColors(defaultRGBFileList, config, xpm):
    rgbFileName = ''
    for fn in defaultRGBFileList:
        if os.access(fn, os.R_OK):
            rgbFileName = fn
            break 
    rgbFileName = config.get('rgbfile', rgbFileName)
    useColors = 1
    if not os.access(rgbFileName, os.R_OK):
        err(
            "Can't read the RGB file, try setting it differently using -r,\n")
        err(
            "Ignoring your color settings, using the defaults.\n")
        useColors = 0
    if useColors:
        # Colors is a list with (<config_key>, <xpm-key>) pairs.
        colors =  (('barfgcolor', 'graph'),
                  ('barbgcolor', 'graphbg'),
                  ('textcolor', 'text'),
                  ('background', 'background'))
        for key, value in colors:
            col = config.get(key)
            if not col is None:
                code = pywmhelpers.getColorCode(col, rgbFileName)
                if code is None:
                    err('Bad colorcode for %s, ignoring.\n' % key)
                else:
                    pywmhelpers.setColor(xpm, value, code)

def readConfigFile(fileName):
    '''Read the config file.
    
    Return a list with dictionaries with the options and values in sections
    [0]-[4].
    '''
    fileName = os.path.expanduser(fileName)
    if not os.access(fileName, os.R_OK):
        err("Can't read the configuration file %s.\n" % fileName)
        # We can't do much without a configuration file
        sys.exit(3)
    cp = ConfigParser.ConfigParser()
    try:
        cp.read(fileName)
    except ConfigParser.Error, e:
        err("Error when reading configuration file:\n%s\n" % str(e))
        sys.exit(3)
    l = [{}, {}, {}, {}, {}]
    for i in range(5):
        strI = str(i)
        if cp.has_section(strI):
            for o in cp.options(strI):
                l[i][o] = cp.get(strI, o, raw=1)
    return l


def main():
    clConfig = parseCommandLine(sys.argv)
    configFile = clConfig.get('configfile', defaultConfigFile)
    configFile = os.path.expanduser(configFile)
    config = readConfigFile(configFile)
    parseColors(defaultRGBFiles, clConfig, xpm)
    try:
        programName = sys.argv[0].split(os.sep)[-1]
    except IndexError:
        programName = ''
    sys.argv[0] = programName
    pywmhelpers.setDefaultPixmap(xpm)
    pywmhelpers.openXwindow(sys.argv, width, height)
    pywmgeneric = PywmGeneric(config)
    pywmgeneric.mainLoop()

xpm = \
['160 100 13 1',
 ' \tc #208120812081',
 '.\tc #00000000FFFF',
 'o\tc #C71BC30BC71B',
 'O\tc #861782078E38',
 '+\tc #EFBEF3CEEFBE',
 '@\tc #618561856185',
 '#\tc #9E79A2899E79',
 '$\tc #410341034103',
 'o\tc #2020b2b2aaaa s indicator',
 '/\tc #2020b2b2aaaa s graph',
 '-\tc #707070707070 s graphbg',
 'X\tc #000000000000 s background',
 '%\tc #2081B2CAAEBA s text',
 '                                                                 ...............................................................................................',
 '                                                                 .///..XXX..ooo..XXX..XXX.......................................................................',
 '                                                                 .///..XXX..ooo..XXX..XXX.......................................................................',
 '                                                                 .///..XXX..ooo..XXX..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..ooo.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..ooo.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..ooo.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...-------------------------------------------------------------------------------------...',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...-------------------------------------------------------------------------------------...',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...-------------------------------------------------------------------------------------...',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...-------------------------------------------------------------------------------------...',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///...........................................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///////////////////////////////////////////////////////////////////////////////////////////...',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///////////////////////////////////////////////////////////////////////////////////////////...',
 '                                                                 .///////////////////////////////////////////////////////////////////////////////////////////...',
 '                                                                 .///////////////////////////////////////////////////////////////////////////////////////////...',
 '                                                                 ...............................................................................................',
 '                                                                 ...............................................................................................',
 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'X%%%%%XXX%XXX%%%%%X%%%%%X%XXX%X%%%%%X%%%%%X%%%%%X%%%%%X%%%%%XXXXXXXXXX%XXXXXXXXXX%X%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'X%XXX%XX%%XXXXXXX%XXXXX%X%XXX%X%XXXXX%XXXXXXXXX%X%XXX%X%XXX%XX%%XXXXXX%XXXXXXXXXXXX%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'X%XXX%XXX%XXXXXXX%XXXXX%X%XXX%X%XXXXX%XXXXXXXXX%X%XXX%X%XXX%XX%%XXXXX%%XXXXXXXXXXX%%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'X%XXX%XXX%XXX%%%%%XX%%%%X%%%%%X%%%%%X%%%%%XXXXX%X%%%%%X%%%%%XXXXXXXXX%XXX%%%%%XXXX%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'X%XXX%XXX%XXX%XXXXXXXXX%XXXXX%XXXXX%X%XXX%XXXXX%X%XXX%XXXXX%XXXXXXXX%%XXXXXXXXXXX%%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'X%XXX%XXX%XXX%XXXXXXXXX%XXXXX%XXXXX%X%XXX%XXXXX%X%XXX%XXXXX%XX%%XXXX%XXXXXXXXXXXX%XXXXX%%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'X%%%%%XX%%%XX%%%%%X%%%%%XXXXX%X%%%%%X%%%%%XXXXX%X%%%%%X%%%%%XX%%XXXX%XXXXXXXXXXXX%X%XXX%%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 '................................................................................................................................................................',
 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
 'XX%%%XX%%%%XXX%%%%X%%%%XX%%%%XX%%%%%X%%%%%X%XXX%XXX%XXXXXXX%X%XXX%X%XXXXX%XXX%X%%%%XX%%%%%X%%%%%X%%%%%X%%%%%X%%%%%X%%%%%X%XXX%X%XXX%X%XXX%X%XXX%X%XXX%X%%%%%XXXX',
 'X%XXX%X%XXX%X%XXXXX%XXX%X%XXXXX%XXXXX%XXXXX%XXX%XXX%XXXXXXX%X%XXX%X%XXXXX%%X%%X%XXX%X%XXX%X%XXX%X%XXX%X%XXX%X%XXXXXXX%XXX%XXX%X%XXX%X%XXX%X%XXX%X%XXX%XXXXX%XXXX',
 'X%XXX%X%XXX%X%XXXXX%XXX%X%XXXXX%XXXXX%XXXXX%XXX%XXX%XXXXXXX%X%XX%XX%XXXXX%X%X%X%XXX%X%XXX%X%XXX%X%XXX%X%XXX%X%XXXXXXX%XXX%XXX%X%XXX%X%XXX%XX%X%XX%XXX%XXXX%XXXXX',
 'X%%%%%X%%%%XX%XXXXX%XXX%X%%%%XX%%%%XX%X%%%X%%%%%XXX%XXXXXXX%X%%%XXX%XXXXX%XXX%X%XXX%X%XXX%X%%%%%X%%XX%X%%%%XX%%%%%XXX%XXX%XXX%X%XXX%X%XXX%XXX%XXX%%%%%XXX%XXXXXX',
 'X%XXX%X%XXX%X%XXXXX%XXX%X%XXXXX%XXXXX%XXX%X%XXX%XXX%XXXXXXX%X%XX%XX%XXXXX%XXX%X%XXX%X%XXX%X%XXXXX%X%X%X%XXX%XXXXX%XXX%XXX%XXX%X%XXX%X%X%X%XX%X%XXXXXX%XX%XXXXXXX',
 'X%XXX%X%XXX%X%XXXXX%XXX%X%XXXXX%XXXXX%XXX%X%XXX%XXX%XXX%XXX%X%XXX%X%XXXXX%XXX%X%XXX%X%XXX%X%XXXXX%XX%%X%XXX%XXXXX%XXX%XXX%XXX%X%XXX%X%%X%%X%XXX%XXXXX%X%XXXXXXXX',
 'X%XXX%X%%%%XXX%%%%X%%%%XX%%%%XX%XXXXX%%%%%X%XXX%XXX%XXXX%%%XX%XXX%X%%%%XX%XXX%X%XXX%X%%%%%X%XXXXX%%%%%X%XXX%X%%%%%XXX%XXXX%%%%XX%%%XX%XXX%X%XXX%X%%%%%X%%%%%XXXX',
 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................',
 '................................................................................................................................................................']

if __name__ == '__main__':
    main()
