#!/usr/bin/python
import time
import math
import os
import subprocess
import thread
import re
import inspect
import logging
import numpy as np
import i2c


# Global variables.
slaveAddressArduino = 0x04


def runShellCommandWait(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0]


def runShellCommandNowait(cmd):
    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)


def getNofConnections():
    stdOutAndErr = runShellCommandWait('netstat | grep -E \'44444.*ESTABLISHED|44445.*ESTABLISHED\' | wc -l')
    return int(stdOutAndErr)


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
        # Create i2c lock if it does not exist yet.
        i2c.createI2cLock()
        # Lock i2c communication for this thread.
        i2c.globI2cLock.acquire()
        i2c.write_byte(slaveAddressArduino, 0, dir)
        i2c.write_byte(slaveAddressArduino, 0, int(speed))
        # Delay for i2c communication.
        time.sleep(i2c.globI2cDelay)
        # Release i2c communication for this thread.
        i2c.globI2cLock.release()
    # Still delay when doMove == False to have similar timing.
    time.sleep(delay)


def moveCamRel(degrees, delay):
    if degrees >= -90 and degrees <= 90:
        if degrees > 0:
            # Create i2c lock if it does not exist yet.
            i2c.createI2cLock()
            # Lock i2c communication for this thread.
            i2c.globI2cLock.acquire()
            i2c.write_byte(slaveAddressArduino, 0, 10)
            i2c.write_byte(slaveAddressArduino, 0, 128 + int(degrees))
            # Delay for i2c communication.
            time.sleep(i2c.globI2cDelay)
            # Release i2c communication for this thread.
            i2c.globI2cLock.release()
        elif degrees < 0:
            # Create i2c lock if it does not exist yet.
            i2c.createI2cLock()
            # Lock i2c communication for this thread.
            i2c.globI2cLock.acquire()
            i2c.write_byte(slaveAddressArduino, 0, 11)
            i2c.write_byte(slaveAddressArduino, 0, 128 - int(degrees))
            # Delay for i2c communication.
            time.sleep(i2c.globI2cDelay)
            # Release i2c communication for this thread.
            i2c.globI2cLock.release()
        # Delay to let camera image stabilize.
        time.sleep(delay)


def moveCamAbs(degrees, delay):
    if degrees >= 0 and degrees <= 90:
        # Create i2c lock if it does not exist yet.
        i2c.createI2cLock()
        # Lock i2c communication for this thread.
        i2c.globI2cLock.acquire()
        i2c.write_byte(slaveAddressArduino, 0, 12)
        i2c.write_byte(slaveAddressArduino, 0, 128 + int(degrees))
        # Delay for i2c communication.
        time.sleep(i2c.globI2cDelay)
        # Release i2c communication for this thread.
        i2c.globI2cLock.release()
        # Delay to let camera image stabilize.
        time.sleep(delay)


def switchLight(on):
    if on == True:
        # Create i2c lock if it does not exist yet.
        i2c.createI2cLock()
        # Lock i2c communication for this thread.
        i2c.globI2cLock.acquire()
        i2c.write_byte(slaveAddressArduino, 0, 20)
        # Delay for i2c communication.
        time.sleep(i2c.globI2cDelay)
        # Release i2c communication for this thread.
        i2c.globI2cLock.release()
    else:
        # Create i2c lock if it does not exist yet.
        i2c.createI2cLock()
        # Lock i2c communication for this thread.
        i2c.globI2cLock.acquire()
        i2c.write_byte(slaveAddressArduino, 0, 21)
        # Delay for i2c communication.
        time.sleep(i2c.globI2cDelay)
        # Release i2c communication for this thread.
        i2c.globI2cLock.release()


def getBatteryLevel():
    # Create i2c lock if it does not exist yet.
    i2c.createI2cLock()
    # Lock i2c communication for this thread.
    i2c.globI2cLock.acquire()
    i2c.write_byte(slaveAddressArduino, 0, 0)
    level = i2c.read_byte(slaveAddressArduino, 0)
    # Delay for i2c communication.
    time.sleep(i2c.globI2cDelay)
    # Release i2c communication for this thread.
    i2c.globI2cLock.release()
    return level


def getWifiStatus():
    stdOutAndErr = runShellCommandWait('/sbin/iwconfig')
    # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
    expr = re.compile('.*ESSID:"(.*)".*?Signal level=(.*dBm)', re.DOTALL)
    m = expr.match(stdOutAndErr)
    if m is not None:  # m will be not None only when both capture groups are valid.
        return m.group(1) + ': ' + m.group(2)
    else:
        return 'wifi unknown'


# Global variables for getBatteryLevel(), used as static variables.
# globBatteryLevels is a circular buffer of 30 battery values, initialized on battery level 200.
globBatteryLevels = np.ones(30) * 200
globBatteryLevelsIndex = 0  # index in the circular buffer.
# The function below determines whether the batteries are being charged or not.
# When the batteries are charged, the battery voltage is irregular.
# To measure this we store the battery voltage in a numpy array and determine the standard deviation.
# Assumption is that this function is called about once in a second or less often.
def checkCharging():
    global globBatteryLevels, globBatteryLevelsIndex
    charging = False
    level = getBatteryLevel()
    globBatteryLevels[globBatteryLevelsIndex] = level
    globBatteryLevelsIndex = globBatteryLevelsIndex + 1
    if globBatteryLevelsIndex >= 30:
        globBatteryLevelsIndex = 0
    # If standard deviation of numpy array with battery levels > 2.0 then the batteries are being charged.
    if np.std(globBatteryLevels) > 2.0:
        charging = True
    return charging


def testCheckCharging():
    while True:
        print checkCharging()
        time.sleep(1.0)


def getUptime():
    stdOutAndErr = runShellCommandWait('/usr/bin/uptime')
    # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
    expr = re.compile('.*up ([^,]+).*', re.DOTALL)
    m = expr.match(stdOutAndErr)
    if m is not None:
        return m.group(1)
    else:
        return 'unknown'


def uploadAndPurge(filepath, nrOfFilesToKeep):
    # Check if filename starts with 'dfrobot_' and number of files to keep >= 1 else do not purge anything and exit.
    filename = os.path.basename(filepath)
    if filename[:8] != 'dfrobot_' or nrOfFilesToKeep < 1:
        logging.getLogger("MyLog").info('uploadAndPurge: illegal filepath:nrOfFilesToKeep to upload and purge: ' + filepath + ':' + str(nrOfFilesToKeep))
        return
    
    # Going to upload the file to Google Drive using the 'drive' utility.
    # To upload into the 'DFRobotUploads' folder, the -p option is used with the id of this folder.
    # When the 'DFRobotUploads' folder is changed, a new id has to be provided.
    # This id can be obtained using 'drive list -t DFRobotUploads'.
    # The uploaded file has a distinctive name to enable finding and removing it again with the 'drive' utility.
    logging.getLogger("MyLog").info('going to call \'drive\' to upload ' + filepath)
    # Run 'drive' as www-data to prevent Google Drive authentication problems.
    stdOutAndErr = runShellCommandWait('sudo -u www-data /usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f ' + filepath)
    logging.getLogger("MyLog").info(stdOutAndErr)

    # Purge filename on Google Drive to prevent filling up.
    logging.getLogger("MyLog").info('going to purge ' + filename)
    # Find all Id's of filename versions on drive.
    stdOutAndErr = runShellCommandWait('sudo -u www-data /usr/local/bin/drive list -t ' + filename)
    # Now stdOutAndErr is a multiline string containing on each line a file version.
    # The last line is the oldest.
    # The first line is the title line so does not contain a valid file version.

    # Use a regular expression to get the file Id's of the oldest files to be purged in a list.
    # Use MULTILINE (so '^' will match the start of a new line) because stdOutAndErr can be multiline.
    expr = re.compile('(^.*?) ', re.MULTILINE)
    idList = expr.findall(stdOutAndErr)
    # Now idList is a list containing the Id's of all file versions.
    # The last Id in the list is the oldest.
    if idList is not None:
        logging.getLogger("MyLog").info('uploadAndPurge: ' + str(len(idList) - 1) + ' versions of ' + filename + ' found on Google Drive')
        # Iterate backwards through the list, starting with the oldest file
        # until there are nrOfFilesToKeep files left.
        for i in range(len(idList)-1, nrOfFilesToKeep, -1):
            # Delete this file version.
            stdOutAndErr = runShellCommandWait('sudo -u www-data /usr/local/bin/drive delete -i ' + idList[i])
            logging.getLogger("MyLog").info(stdOutAndErr)
