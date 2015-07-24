#!/usr/bin/python
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
    stream=urllib.urlopen('http://@localhost:44445/?action=stream')
    bytes=''

    for i in range(0,1000):
        bytes+=stream.read(1024)
        a = bytes.find('\xff\xd8')
        b = bytes.find('\xff\xd9')
        if a!=-1 and b!=-1:
            jpg = bytes[a:b+2]
            bytes= bytes[b+2:]
            img = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8),cv2.CV_LOAD_IMAGE_COLOR)
            
            img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            COLOR_MIN = np.array([92, 100, 50],np.uint8)
            COLOR_MAX = np.array([102, 255, 220],np.uint8)
            img_thresh = cv2.inRange(img_hsv, COLOR_MIN, COLOR_MAX)
            contours, hierarchy = cv2.findContours(img_thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
            
            # Find the index of the largest contour
            areas = [cv2.contourArea(c) for c in contours]
            if areas:
                max_index = np.argmax(areas)
                cnt=contours[max_index]
                
                epsilon = 0.1*cv2.arcLength(cnt,True)
                approx = cv2.approxPolyDP(cnt,epsilon,True)
                
                x,y,w,h = cv2.boundingRect(cnt)
                cv2.rectangle(img,(x,y),(x+w,y+h),(0,255,0),2)
            # Print images with name like 'tmp_img000042.jpg'.
            # Use leading zeros to make sure order is correct when using shell filename expansion.
            cv2.imwrite('/home/pi/DFRobotUploads/tmp_img' + str(i).zfill(6) + '.jpg', img)

    stdOutAndErr = runShellCommandWait('mencoder mf:///home/pi/DFRobotUploads/tmp_img*.jpg -mf w=800:h=600:fps=2:type=jpg -ovc lavc -lavcopts vcodec=mpeg4:mbd=2:trell -oac copy -o /home/pi/DFRobotUploads/dfrobot_pivid.avi')
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
    runShellCommandNowait('LD_LIBRARY_PATH=/opt/mjpg-streamer/mjpg-streamer-experimental/ /opt/mjpg-streamer/mjpg-streamer-experimental/mjpg_streamer -i "input_raspicam.so -vf -hf -fps 2 -q 10 -x 800 -y 600" -o "output_http.so -p 44445 -w /opt/mjpg-streamer/mjpg-streamer-experimental/www"')
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


