#!/usr/bin/python

import time
import math
import os
import subprocess
import inspect

def writeToLogFile(str):
    logFileName = '/home/pi/log/dfrobot_log.txt'
    if os.stat(logFileName).st_size > 1000000:
        open(logFileName, 'w').close()
    
    # Get filename of the module which called this function so it can be used in the prompt.
    frm = inspect.stack()[1]
    mod = inspect.getmodule(frm[0])
    prompt = '***** ' + time.strftime("%Y-%m-%d %H:%M") + ', ' + mod.__file__ + ': '
    logFile = open(logFileName, 'a')
    logFile.write(prompt + str)
    logFile.close()

def runShellCommandWait( cmd ):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0]

def runShellCommandNowait( cmd ):
    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

waitForNextMove = 0
def move(direction, speed, doMove):
    global waitForNextMove

    if doMove:
        if waitForNextMove == 0:
            if direction == 'forward':
                dir = 1
            elif direction == 'backward':
                dir = 2
            elif direction == 'left':
                dir = 3
            elif direction == 'right':
                dir = 4
            else:
                dir = 0
            stdOutAndErr = runShellCommandWait('i2c_cmd ' + str(dir) + ' ' + str(speed))
            waitForNextMove = 3
        else:
            waitForNextMove = waitForNextMove - 1