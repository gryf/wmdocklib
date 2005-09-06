#!/usr/bin/env python

'''pywmseti.py

WindowMaker dockapp to monitor the progress of your seti@home.

Copyright (C) 2003 Kristoffer Erlandsson

Licensed under the GNU General Public License.


Changes

2003-06-24 Kristoffer Erlandsson
Added event handling for graceful shutdown

2003-06-17 Kristoffer Erlandsson
First workingish version

'''
usage = '''pywmseti.py [options]
Available options are:
-h, --help                      print this help
-t, --textcolor <color>         set the text color
-p, --progressbarcolor <color>  set the color of the progress bar
-g, --barbgcolor <color>        set the background color of the progress bar
-i, --indicatorcolor <color>    set the color of the running indicator
-b, --background <color>        set the background color
-d, --setidir <directory>       set the directory where seti@home resides
-n, --nice <value>              set the nice value to run seti@home with
-r, --rgbfile <file>            set the rgb file to get color codes from
-c, --configfile <file>         set the config file to use
'''

import sys
import time
import getopt
import os

import pywmhelpers

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

graphStartX = 7
graphStartY = 53
graphLength = 50
graphHeight = 4

graphBgStartX = 72
graphBgStartY = 53

graphLineStartX = 66
graphLineStartY = 58

runningIndX = 71
runningIndY = 1
runningIndWidth = 3
runningIndHeight = 15
numRunningInds = 4

letters = 'abcdefghijklmnopqrstuvwxyz'
digits = '0123456789:/-% '

defaultConfigFile = '~/.pywmsetirc'
defaultRGBFiles = ['/usr/lib/X11/rgb.txt', '/usr/X11R6/lib/X11/rgb.txt']

stateFileName = 'state.sah'
uinfoFileName = 'user_info.sah'
pidFileName = 'pid.sah'
execFileName = 'setiathome'

class PywmSeti:
    def __init__(self, statePath, uinfoPath, pidPath, execCmd):
        self._statePath = statePath
        self._uinfoPath = uinfoPath
        self._pidPath = pidPath
        self._execCmd = execCmd
        self._currentRunningInd = 0
        self._lastTime = time.time()
        self._lastNumResults = -1
        self._progress = 0
        
    def addString(self, s, x, y):
        try:
            pywmhelpers.addString(s, x, y, letterWidth, letterHeight,
                        lettersStartX, lettersStartY, letters, digitWidth,
                        digitHeight, digitsStartX, digitsStartY, digits,
                        xOffset, yOffset, width, height)
        except ValueError, e:
            sys.stderr.write('Error when painting string:\n' + str(e) + '\n')
            sys.exit(3)

    def getCenterStartPos(self, s):
        return pywmhelpers.getCenterStartPos(s, letterWidth, width, xOffset)

    def getVertSpacing(self, numLines, margin):
        return pywmhelpers.getVertSpacing(numLines, margin, height,
                                        letterHeight, yOffset)

    def getProgress(self, lines):
        '''Return the progess of the current workunit.
         
        Supply the lines of the statefile as argument.
        '''
        for line in lines:
            if line.startswith('prog='):
                try:
                    progress = float(line.split('=')[-1])
                except ValueError:
                    progress = 0
                return progress
        return 0

    def getNumResults(self, lines):
        '''Return the number of results produced.
         
        Supply the lines in the user info file as argument.
        '''
        for line in lines:
            if line.startswith('nresults='):
                try:
                    results = int(line.split('=')[-1])
                except ValueError:
                    pass
                else:
                    return results
        sys.stderr.write(
            "Error when reading uinfo file! Can't get number of results.\n")
        return -1

    def pidIsRunning(self, pid):
        '''Determine if the process with PID pid is running.
    
        Return 1 if it is running.
        Return 0 if it is not running.
        Return -1 if we do not have permission to signal the process
        This could be slightly non-portal, but I can not find any better
        way to do it.
        '''
        try:
            os.kill(pid, 0)
        except OSError, e:
            if e.errno == 1:
                return -1
            return 0
        return 1
        
    def openFileRead(self, fileName):
        try:
            f = file(fileName, 'r')
        except IOError, e:
            sys.stderr.write('Error when opening %s: %s\n' % (fileName, str(e)))
            return None
        return f


    def paintCurrentRunningIndicator(self):
        '''Paint the running indicator.
        '''
        indX = runningIndX + self._currentRunningInd * \
                             (runningIndWidth + 2)
        indY = runningIndY
        w = runningIndWidth
        h = runningIndHeight
        targX = width - xOffset - w - 5
        targY = yOffset + 5
        pywmhelpers.copyXPMArea(indX, indY, w, h, targX, targY)

    def updateRunning(self):
        '''Update the information regarding if we got seti@home running or not.

        Return a tuple with (running, startStopenabled).
        startStopEnabled is 1 if we own the process and got the permissions
        to start and stop it, or if there is no process running.
        '''
        pidFile = self.openFileRead(self._pidPath)
        if pidFile is None:
            sys.stderr.write("Can't read pid file")
            self._running = 0
            self._startStopEnabled = 0
            return
        try:
            self._pid = int(pidFile.read().strip())
        except ValueError:
            sys.stderr.write("Can't get pid from %s.\n" % self._pidPath)
            self._running = 0
            self._startStopEnabled = 0
            return
        pidFile.close()
        self._running = self.pidIsRunning(self._pid)
        if self._running == -1 and self._startStopEnabled:
            sys.stderr.write(
            "An other seti@home process which you don't own is running.\n")
            sys.stderr.write(
            "Starting and stopping of the process is disabled.\n")
            self._startStopenabled = 0
        if self._running == -1:
            self._running = 1
        else:
            # If no process is running (we could have stopped the one
            # running from an other process), enable starting and stopping.
            self._startStopEnabled = 1
        if self._running:
            self._currentRunningInd = (self._currentRunningInd - 1) \
                                      % numRunningInds
        else:
            self._currentRunningInd = 0
        self.paintCurrentRunningIndicator()

    def updateProgress(self):
        '''Update the progress on the current workunit.'''
        stateFile = self.openFileRead(self._statePath)
        if stateFile is None:
            # Can't open file, probably in progress of gettin a new workunit.
            progress = 0
        else:
            progress = self.getProgress(stateFile.readlines())
            stateFile.close()
        self._progress = progress
        percent = int(progress * 100.0)
        graphSize = int(round(progress * graphLength))
        pywmhelpers.copyXPMArea(
            graphLineStartX, graphLineStartY, graphSize, graphHeight, 
            graphStartX, graphStartY)
        pywmhelpers.copyXPMArea(
            graphBgStartX, graphBgStartY, graphLength - graphSize, graphHeight,
            graphStartX + graphSize, graphStartY)
        self.addString((str(percent) + '%').ljust(4), 4, 32)

    def updateNumResults(self):
        '''Update the number of workunits done.'''
        uinfoFile = self.openFileRead(self._uinfoPath)
        numResults = self.getNumResults(uinfoFile.readlines())
        if self._lastNumResults == -1:
            self._lastNumResults = numResults
        if numResults != self._lastNumResults and self._progress < 0.03:
            # If we just got a new number of results and the progress of the
            # current workunit is under 3%, assume we started working on a new
            # workunit. The times this could be missleading is if we have an
            # other seti@home process running on an other computer, but this is
            # accurate enough I think.
            self.nextWorkUnitStarted()
            self._lastNumResults = numResults
        uinfoFile.close()
        self.addString(str(numResults)[:7], 4, 4) 

    def updateTime(self):
        '''Update the time line.

        We display the time that we have been on the current work unit, since
        either the last one was done or since we started the program.
        '''
        timeSpent = time.time() - self._lastTime
        hours = int(timeSpent / 3600)
        mins = int((timeSpent - hours * 3600) / 60)
        hours = str(hours)[:3]
        mins = str(mins).zfill(2)
        s = (hours + ':' + mins).ljust(6)
        self.addString(s, 4, 18)

    def nextWorkUnitStarted(self):
        self._lastTime = time.time()

    def handleMouseClick(self, region):
        if region == 0:
            if self._startStopEnabled:
                if self._running:
                    try:
                        os.kill(self._pid, 15)
                    except OSError, e:
                        sys.stderr.write(
                            "Error when ending process: "+str(e)+'\n')
                else:
                    os.system(self._execCmd)  # Use fork instead?

    def _checkForEvents(self):
        '''Check for, and handle, X events.'''
        event = pywmhelpers.getEvent()
        while not event is None:
            if event['type'] == 'buttonrelease':
                region = pywmhelpers.checkMouseRegion(event['x'],
                                                      event['y'])
                self.handleMouseClick(region)
            elif event['type'] == 'destroynotify':
                sys.exit(0)
            event = pywmhelpers.getEvent()

    def mainLoop(self):
        counter = -1
        self._startStopEnabled = 1
        while 1:
            counter += 1
            self._checkForEvents()
            if counter % 10 == 0:
                self.updateRunning()
            if counter % 100 == 0:
                self.updateProgress()
                self.updateNumResults()
                self.updateTime()
            if counter == 999999:
                counter = -1
            pywmhelpers.redraw()
            time.sleep(0.1)
        

def parseCommandLine(argv):
    '''Parse the commandline. Return a dictionary with options and values.'''
    shorts = 'ht:b:n:d:r:c:p:g:i:'
    longs = ['help', 'textcolor=', 'background=', 'setidir=', 'nice=',
             'rgbfile=', 'configfile=', 'progressbarcolor=', 'barbgcolor=',
             'indicatorcolor=']
    try:
        opts, nonOptArgs = getopt.getopt(argv[1:], shorts, longs)
    except getopt.GetoptError, e:
        sys.stderr.write('Error when parsing commandline: ' + str(e) + '\n')
        sys.stderr.write(usage)
        sys.exit(2)
    d = {}                
    for o, a in opts:     
        if o in ('-h', '--help'):
            sys.stdout.write(usage)
            sys.exit(0)
        if o in ('-t', '--textcolor'):
            d['textcolor'] = a
        if o in ('-b', '--background'):
            d['background'] = a
        if o in ('-d', '--setidir'):
            d['setidir'] = a
        if o in ('-n', '--nice'):
            d['nice'] = a
        if o in ('-r', '--rgbfile'):
            d['rgbfile'] = a
        if o in ('-c', '--configfile'):
            d['configfile'] = a
        if o in ('-p', '--progressbarcolor'):
            d['progressbarcolor'] = a
        if o in ('-g', '--barbgcolor'):
            d['barbgcolor'] = a
        if o in ('-i', '--indicatorcolor'):
            d['indicatorcolor'] = a
    return d

def parseColors(defaultRGBFileNames, config, xpm):
    rgbFileName = ''
    for fn in defaultRGBFileNames:
        if os.access(fn, os.R_OK):
            rgbFileName = fn
            break
    rgbFileName = config.get('rgbfile', rgbFileName)
    useColors = 1
    if not os.access(rgbFileName, os.R_OK):
        sys.stderr.write(
            "Can't read the RGB file, try setting it differently using -r,\n")
        sys.stderr.write(
            "Ignoring your color settings, using the defaults.\n")
        useColors = 0
    if useColors:
        # Colors is a list with (<config_key>, <xpm-key>) pairs.
        colors = (('indicatorcolor', 'indicator'),
                  ('progressbarcolor', 'graph'),
                  ('barbgcolor', 'graphbg'),
                  ('textcolor', 'text'),
                  ('background', 'background'))
        for key, value in colors:
            col = config.get(key)
            if not col is None:
                code = pywmhelpers.getColorCode(col, rgbFileName)
                if code is None:
                    sys.stderr.write('Bad colorcode for %s, ignoring.\n' % key)
                else:
                    pywmhelpers.setColor(xpm, value, code)

def main():
    clConfig = parseCommandLine(sys.argv)
    configFile = clConfig.get('configfile', defaultConfigFile)
    configFile = os.path.expanduser(configFile)
    fileConfig = pywmhelpers.readConfigFile(configFile, sys.stderr)
    # Merge the two configs, let the commandline options overwrite those in the
    # configuration file.
    config = fileConfig
    for i in clConfig.iteritems():
        config[i[0]] = i[1]
    # Get the configurations
    parseColors(defaultRGBFiles, config, xpm)
    setiDir = config.get('setidir')
    if setiDir is None:
        sys.stderr.write(
        'You have to supply a directory where seti@home resides. Either in\n')
        sys.stderr.write(
        'the configuration file or with -d/--setidir.\n')
        sys.exit(3)
    setiDir = os.path.expanduser(setiDir)
    try:
        os.chdir(setiDir)
    except OSError, e:
        sys.stderr.write('Error when accessing seti directory: %s\n' % str(e))
        sys.exit(4)
    statePath = os.path.join(setiDir, stateFileName)
    uinfoPath = os.path.join(setiDir, uinfoFileName)
    pidPath = os.path.join(setiDir, pidFileName)
    execPath = os.path.join(setiDir, execFileName)
    niceVal = config.get('nice')
    if niceVal is None:
        execCmd = execPath
    else:
        execCmd = execPath + ' -nice %s' % niceVal + '&'
    try:
        programName = sys.argv[0].split(os.sep)[-1]
    except IndexError:
        programName = ''
    sys.argv[0] = programName
    pywmhelpers.setDefaultPixmap(xpm)
    pywmhelpers.openXwindow(sys.argv, width, height)
    pywmhelpers.addMouseRegion(0, xOffset, yOffset, width - 2 * xOffset,
                               height - 2 * yOffset)
    pwms = PywmSeti(statePath, uinfoPath, pidPath, execCmd)
    pwms.mainLoop()

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
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..ooo..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..ooo..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..ooo..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..XXX.......................................................................',
 '    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     .///..XXX..XXX..XXX..XXX.......................................................................',
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
 'X%XXX%XXX%XXX%XXXXXXXXX%XXXXX%XXXXX%X%XXX%XXXXX%X%XXX%XXXXX%XX%%XXXX%XXXXXXXXXXXX%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
 'X%%%%%XX%%%XX%%%%%X%%%%%XXXXX%X%%%%%X%%%%%XXXXX%X%%%%%X%%%%%XX%%XXXX%XXXXXXXXXXXX%X%XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX............................',
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
