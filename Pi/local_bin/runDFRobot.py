#!/usr/bin/env python
import cv2
import numpy as np
import urllib
import subprocess
import os
import time

logfileName = '/home/pi/log/dfrobot_log.txt'

def prompt( ):
    return '***** ' + time.strftime("%Y-%m-%d %H:%M") + ', ' + __file__ + ': '

def runShellCommandWait( cmd ):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0]

def runShellCommandNowait( cmd ):
    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

def runRobot( ):
    # Get directory of this python script
    dirname = os.path.dirname(os.path.realpath(__file__))
    template = cv2.imread(os.path.join(dirname,"template.jpg"), 0)
    w, h = template.shape[::-1]
    stream=urllib.urlopen('http://@localhost:44445/?action=stream')
    bytes=''

    for i in range(0,100):
        bytes+=stream.read(1024)
        a = bytes.find('\xff\xd8')
        b = bytes.find('\xff\xd9')
        if a!=-1 and b!=-1:
            jpg = bytes[a:b+2]
            bytes= bytes[b+2:]
            img = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8),cv2.CV_LOAD_IMAGE_GRAYSCALE)
            
            # Apply template Matching
            res = cv2.matchTemplate(img,template, cv2.TM_SQDIFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            
            # If the method is TM_SQDIFF or TM_SQDIFF_NORMED, take minimum
            top_left = min_loc
            bottom_right = (top_left[0] + w, top_left[1] + h)
            
            logfile.write(prompt() + str(top_left) + ' ' + str(bottom_right) + '\n')
            cv2.rectangle(img,top_left, bottom_right, 255, 2)
            # Print images with name like 'tmp_img000042.jpg'.
            # Use leading zeros to make sure order is correct when using shell filename expansion.
            cv2.imwrite('/home/pi/DFRobotUploads/tmp_img' + str(i).zfill(6) + '.jpg', img)

    stdOutAndErr = runShellCommandWait('mencoder mf:///home/pi/DFRobotUploads/tmp_img*.jpg -mf w=320:h=240:fps=2:type=jpg -ovc lavc -lavcopts vcodec=mpeg4:mbd=2:trell -oac copy -o /home/pi/DFRobotUploads/dfrobot_pivid.avi')
    logfile.write(prompt() + stdOutAndErr + '\n')
    stdOutAndErr = runShellCommandWait('rm /home/pi/DFRobotUploads/tmp_img*')
    logfile.write(prompt() + stdOutAndErr + '\n')

# Main script
# Reset the log file to zero length if the size gets too large.
if os.stat(logfileName).st_size > 1000000:
    open(logfileName, 'w').close()

with open(logfileName, 'a') as logfile:
    logfile.write(prompt() + 'START LOG  *****\n')

    # First check if there are active connections. If so, do not continue this script.
    stdOutAndErr = runShellCommandWait('netstat | grep 44444 | wc -l')
    if int(stdOutAndErr) > 0:
        logfile.write(prompt() + 'not going to run because there are active connections\n')
        exit(0)
    # Start MJPEG stream needed by runDFRobot.py. Stop previous stream first if any.
    logfile.write(prompt() + 'going to start stream\n')
    stdOutAndErr = runShellCommandWait('killall mjpg_streamer')
    time.sleep(0.5)
    runShellCommandNowait('LD_LIBRARY_PATH=/opt/mjpg-streamer/mjpg-streamer-experimental/ /opt/mjpg-streamer/mjpg-streamer-experimental/mjpg_streamer -i "input_raspicam.so -vf -hf -fps 2 -q 10 -x 320 -y 240" -o "output_http.so -p 44445 -w /opt/mjpg-streamer/mjpg-streamer-experimental/www"')
    # Call runRobot() function.
    logfile.write(prompt() + 'going to call runRobot()\n')
    runRobot()
    # Stop MJPEG stream.
    stdOutAndErr = runShellCommandWait('killall mjpg_streamer')

    # Going to upload the file to Google Drive using the 'drive' utility.
    # To upload into the 'DFRobotUploads' folder, the -p option is used with the id of this folder.
    # When the 'DFRobotUploads' folder is changed, a new id has to be provided.
    # This id can be obtained using 'drive list -t DFRobotUploads'.
    # The uploaded file has a distinctive name to enable finding and removing it again with the 'drive' utility.
    logfile.write(prompt() + 'going to call \'drive\' to upload videofile\n')
    stdOutAndErr = runShellCommandWait('/usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/DFRobotUploads/dfrobot_pivid.avi')
    logfile.write(prompt() + stdOutAndErr + '\n')
    logfile.write(prompt() + 'going to call \'drive\' to upload logfile\n')
    stdOutAndErr = runShellCommandWait('/usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/log/dfrobot_log.txt')
    logfile.write(prompt() + stdOutAndErr + '\n')

    # Purge uploads to Google Drive to prevent filling up.
    logfile.write(prompt() + 'going to call going to call \'purgeDFRobotUploads\'\n')
# purgeDFRobotUploads.sh is a bash script which writes to the logfile itself, so do not redirect output.
# This means we cannot use runShellCommandWait() or runShellCommandNowait().
# Also do not exectue this in the 'with open(logfileName, 'a')' to close the logfile,
# otherwise the logging gets mixed up.
p = subprocess.Popen('/usr/local/bin/purgeDFRobotUploads.sh dfrobot_pivid.avi 3', shell=True)
p.wait()
p = subprocess.Popen('/usr/local/bin/purgeDFRobotUploads.sh dfrobot_log.txt 1', shell=True)
p.wait()


