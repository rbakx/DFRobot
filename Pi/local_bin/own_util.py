#!/usr/bin/python
import time
import math
import os
import subprocess
import thread
import re
import inspect
import logging

def runShellCommandWait(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0]

def runShellCommandNowait(cmd):
    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

def getNofConnections():
    stdOutAndErr = runShellCommandWait('netstat | grep -E \'44444.*ESTABLISHED|44445.*ESTABLISHED\' | wc -l')
    return int(stdOutAndErr)

# Below a psutil equivalent of netstat.
# At the moment we do not use this because the output is difficult to parse and probably less stable than netstat.
# The number of connections reported with this function is not the same as with getNofConnections()
# due to different parsing, mostly it is one less.
def getNofConnectionsPsUtil():
    txt = str(psutil.net_connections(kind='tcp'))
    rexp = re.compile('(44444|44445)\)[^\)]*\)[^\)]*ESTABLISHED\'')
    match = rexp.findall(txt)
    return len(match)

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
        stdOutAndErr = runShellCommandWait('/usr/local/bin/i2c_cmd ' + str(dir) + ' ' + str(speed))
    # Still delay when doMove == False to have similar timing.
    time.sleep(delay)

def moveCamRel(degrees):
    if degrees >= -90 and degrees <= 90:
        if degrees > 0:
            stdOutAndErr = runShellCommandWait('/usr/local/bin/i2c_cmd 10 ' + str(128 + degrees))
        elif degrees < 0:
            stdOutAndErr = runShellCommandWait('/usr/local/bin/i2c_cmd 11 ' + str(128 - degrees))
        # Delay for i2c communication.
        time.sleep(0.1)

def moveCamAbs(degrees):
    if degrees >= 0 and degrees <= 90:
        stdOutAndErr = runShellCommandWait('/usr/local/bin/i2c_cmd 12 ' + str(128 + degrees))
        # Delay for i2c communication.
        time.sleep(0.1)

def getBatteryLevel():
    stdOutAndErr = runShellCommandWait('/usr/local/bin/i2c_cmd 0')
    # Delay for i2c communication.
    time.sleep(0.1)
    # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
    expr = re.compile('.*Received ([0-9]+).*', re.DOTALL)
    m = expr.match(stdOutAndErr)
    if m != None:
        return m.group(1)
    else:
        return 'unknown'

def getUptime():
    stdOutAndErr = runShellCommandWait('/usr/bin/uptime')
    # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
    expr = re.compile('.*up ([^,]+).*', re.DOTALL)
    m = expr.match(stdOutAndErr)
    if m != None:
        return m.group(1)
    else:
        return 'unknown'

def uploadAndPurge(filepath, nrOfFilesToKeep):
    # Going to upload the file to Google Drive using the 'drive' utility.
    # To upload into the 'DFRobotUploads' folder, the -p option is used with the id of this folder.
    # When the 'DFRobotUploads' folder is changed, a new id has to be provided.
    # This id can be obtained using 'drive list -t DFRobotUploads'.
    # The uploaded file has a distinctive name to enable finding and removing it again with the 'drive' utility.
    logging.getLogger("MyLog").info('going to call \'drive\' to upload ' + filepath)
    # Run 'drive' as www-data to prevent Google Drive authentication problems.
    stdOutAndErr = runShellCommandWait('sudo -u www-data /usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f ' + filepath)
    logging.getLogger("MyLog").info(stdOutAndErr)
    
    # Purge uploads to Google Drive to prevent filling up.
    logging.getLogger("MyLog").info('going to call \'purge_dfrobot_uploads.sh\'')
    # purge_dfrobot_uploads.sh is a bash script which writes to the logfile itself, so do not redirect output.
    # This means we cannot use runShellCommandWait() or runShellCommandNowait().
    p = subprocess.Popen('/usr/local/bin/purge_dfrobot_uploads.sh ' + os.path.basename(filepath) + ' ' + str(nrOfFilesToKeep), shell=True)
    p.wait()
