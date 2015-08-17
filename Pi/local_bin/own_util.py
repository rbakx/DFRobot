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

def move(direction, speed, delay, doMove):
    if doMove:
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
    # Still delay when doMove == False to have similar timing.
    time.sleep(delay)

def moveCamRel(degrees):
    if degrees >= -90 and degrees <= 90:
        if degrees > 0:
            stdOutAndErr = runShellCommandWait('i2c_cmd 10 ' + str(128 + degrees))
        elif degrees < 0:
            stdOutAndErr = runShellCommandWait('i2c_cmd 11 ' + str(128 - degrees))
        # Delay for i2c communication.
        time.sleep(0.1)

def moveCamAbs(degrees):
    if degrees >= 0 and degrees <= 90:
        stdOutAndErr = runShellCommandWait('i2c_cmd 12 ' + str(128 + degrees))
        # Delay for i2c communication.
        time.sleep(0.1)

def uploadAndPurge(filename, nrOfFilesToKeep):
    # Going to upload the file to Google Drive using the 'drive' utility.
    # To upload into the 'DFRobotUploads' folder, the -p option is used with the id of this folder.
    # When the 'DFRobotUploads' folder is changed, a new id has to be provided.
    # This id can be obtained using 'drive list -t DFRobotUploads'.
    # The uploaded file has a distinctive name to enable finding and removing it again with the 'drive' utility.
    writeToLogFile('going to call \'drive\' to upload ' + filename + '\n')
    # Run 'drive' as www-data to prevent Google Drive authentication problems.
    stdOutAndErr = runShellCommandWait('sudo -u www-data /usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/DFRobotUploads/' + filename)
    writeToLogFile(stdOutAndErr + '\n')
    writeToLogFile('going to call \'drive\' to upload logfile\n')
    # Run 'drive' as www-data to prevent Google Drive authentication problems.
    stdOutAndErr = runShellCommandWait('sudo -u www-data /usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/log/dfrobot_log.txt')
    writeToLogFile(stdOutAndErr + '\n')
                    
    # Purge uploads to Google Drive to prevent filling up.
    writeToLogFile('going to call going to call \'purge_dfrobot_uploads.sh\'\n')
    # purge_dfrobot_uploads.sh is a bash script which writes to the logfile itself, so do not redirect output.
    # This means we cannot use runShellCommandWait() or runShellCommandNowait().
    p = subprocess.Popen('/usr/local/bin/purge_dfrobot_uploads.sh ' + filename + ' ' + str(nrOfFilesToKeep), shell=True)
    p.wait()
    p = subprocess.Popen('/usr/local/bin/purge_dfrobot_uploads.sh dfrobot_log.txt 1', shell=True)
    p.wait()
