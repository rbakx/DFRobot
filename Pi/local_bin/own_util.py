#!/usr/bin/python
import time
import math
import os
import subprocess
import thread
import re
import inspect
import fcntl

def writeToLogFile(str):
    if str != '':
        logFileName = '/home/pi/log/dfrobot_log.txt'
        if os.stat(logFileName).st_size > 1000000:
            open(logFileName, 'w').close()
        
        # Get filename of the module which called this function so it can be used in the prompt.
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        prompt = '***** ' + time.strftime("%Y-%m-%d %H:%M") + ', ' + mod.__file__ + ': '
        logFile = open(logFileName, 'a')
        logFile.write(prompt + str + '\n')
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

def uploadAndPurge(filename, nrOfFilesToKeep):
    # Going to upload the file to Google Drive using the 'drive' utility.
    # To upload into the 'DFRobotUploads' folder, the -p option is used with the id of this folder.
    # When the 'DFRobotUploads' folder is changed, a new id has to be provided.
    # This id can be obtained using 'drive list -t DFRobotUploads'.
    # The uploaded file has a distinctive name to enable finding and removing it again with the 'drive' utility.
    writeToLogFile('going to call \'drive\' to upload ' + filename)
    # Run 'drive' as www-data to prevent Google Drive authentication problems.
    stdOutAndErr = runShellCommandWait('sudo -u www-data /usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/DFRobotUploads/' + filename)
    writeToLogFile(stdOutAndErr)
    writeToLogFile('going to call \'drive\' to upload logfile')
    # Run 'drive' as www-data to prevent Google Drive authentication problems.
    stdOutAndErr = runShellCommandWait('sudo -u www-data /usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/log/dfrobot_log.txt')
    writeToLogFile(stdOutAndErr)
                    
    # Purge uploads to Google Drive to prevent filling up.
    writeToLogFile('going to call going to call \'purge_dfrobot_uploads.sh\'')
    # purge_dfrobot_uploads.sh is a bash script which writes to the logfile itself, so do not redirect output.
    # This means we cannot use runShellCommandWait() or runShellCommandNowait().
    p = subprocess.Popen('/usr/local/bin/purge_dfrobot_uploads.sh ' + filename + ' ' + str(nrOfFilesToKeep), shell=True)
    p.wait()
    p = subprocess.Popen('/usr/local/bin/purge_dfrobot_uploads.sh dfrobot_log.txt 1', shell=True)
    p.wait()

def whatsAppClient():
    global globContinueWhatsApp
    global globMsgIn, globMsgInAvailable, globMsgInAvailableLock
    global globMsgOut, globMsgOutType, globImgOut, globMsgOutAvailable, globMsgOutAvailableLock
    # Start Yowsup client. Through pipes it communicates with this thread. Default the pipes are buffering
    # which makes that the communication blocks. Therefore the -u option is which will put stdout in unbuffered mode.
    # For stdin we use stdin.flush() below.
    p = subprocess.Popen('python -u /home/pi/yowsup/yowsup-cli demos --yowsup --config /home/pi/yowsup/yowsup_config', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    # Use file control to make the stdout readline() used below non-blocking.
    # stdout is what comes back from yowsup-cli.
    # This means that if there is no input, readline() will generate an exception.
    # This is what we want otherwise we cannot handle stdout and stdin in the same thread.
    fcntl.fcntl(p.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
    p.stdin.write('/L\n')
    
    # Regulare expression to filter out message from yowsup-cli output
    expr = re.compile('.*\[.*whatsapp.net.*\]\\s*(.*)')
    while globContinueWhatsApp:
        # Sleep below to save CPU.
        time.sleep(1)
        
        # ***** Handle input *****
        # Below use readline() and not read() because read() will return only after EOF is read which will
        # not happen as the Yowsup client keeps running. readline() instead reads until the end of a line.
        # Using the fcntl above the readline() will not block, but generate an exception when there is no input.
        try:
            line = p.stdout.readline()
        except IOError:
            pass
        else: # got line
            m = expr.match(line)
            if m != None:
                writeToLogFile('whatsAppClient: WhatsApp message received: "' + m.group(1) + '"')
                globMsgInAvailableLock.acquire()
                globMsgIn = m.group(1)
                globMsgInAvailable = True
                globMsgInAvailableLock.release()
            
        # ***** Handle output *****
        globMsgOutAvailableLock.acquire()
        if globMsgOutAvailable:
            if globMsgOutType == 'Image':
                writeToLogFile('whatsAppClient: going to send WhatsApp image ' + globImgOut + ' with caption "' + globMsgOut + '"')
                p.stdin.write('/image send 31613484264' + ' "' + globImgOut + '"' + ' "' + globMsgOut + '"' + '\n')
            else:
                writeToLogFile('whatsAppClient: going to send WhatsApp message "' + globMsgOut + '"')
                p.stdin.write('/message send 31613484264 "' + globMsgOut + '"\n')
            # Flush the stdin pipe otherwise the command will not get through.
            p.stdin.flush()
            globMsgOutAvailable = False
        globMsgOutAvailableLock.release()
    # There seems to be no command for exiting yowsup-cli client, so kill process.
    stdOutAndErr = runShellCommandWait('pkill -f yowsup')

def startWhatsAppClient():
    global globContinueWhatsApp
    global globMsgIn, globMsgInAvailable, globMsgInAvailableLock
    global globMsgOut, globMsgOutAvailable, globMsgOutAvailableLock
    writeToLogFile('going to start whatsAppClient')
    globMsgInAvailableLock = thread.allocate_lock()
    globMsgOutAvailableLock = thread.allocate_lock()
    globContinueWhatsApp = True
    globMsgInAvailable = globMsgOutAvailable = False
    thread.start_new_thread(whatsAppClient, ())

def stopWhatsAppClient():
    global globContinueWhatsApp
    writeToLogFile('going to stop whatsAppClient')
    globContinueWhatsApp = False

def sendWhatsAppMsg(msg):
    global globMsgOut, globMsgOutType, globMsgOutAvailable, globMsgOutAvailableLock
    globMsgOutAvailableLock.acquire()
    globMsgOut = msg
    globMsgOutType = 'Text'
    globMsgOutAvailable = True
    globMsgOutAvailableLock.release()

def sendWhatsAppImg(img, caption):
    global globMsgOut, globMsgOutType, globImgOut, globMsgOutAvailable, globMsgOutAvailableLock
    globMsgOutAvailableLock.acquire()
    globImgOut = img
    globMsgOut = caption
    globMsgOutType = 'Image'
    globMsgOutAvailable = True
    globMsgOutAvailableLock.release()

def receiveWhatsAppMsg():
    global globMsgIn, globMsgInAvailable, globMsgInAvailableLock
    msg = ''
    globMsgInAvailableLock.acquire()
    if globMsgInAvailable:
        msg = globMsgIn
        globMsgInAvailable = False
    globMsgInAvailableLock.release()
    return msg
