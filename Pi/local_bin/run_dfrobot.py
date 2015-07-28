#!/usr/bin/python
import cv2
import numpy as np
import urllib
import subprocess
import sys
import os
import time
import compass
import own_util

doPrint = False

def runRobot( ):
    stream=urllib.urlopen('http://@localhost:44445/?action=stream')
    bytes=''
    isHome = False
    
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
            
            # Find the largest contours
            areas = [cv2.contourArea(c) for c in contours]
            if areas:
                sortedContours = sorted(zip(areas, contours), key=lambda x: x[0], reverse=True)
                cnt1 = sortedContours[0][1] # largest contour
                x1,y1,w1,h1 = cv2.boundingRect(cnt1)
                if len(areas) > 1:
                    cnt2 = sortedContours[1][1] # second largest contour
                    if len(areas) > 2:
                        cnt3 = sortedContours[2][1] # third largest contour
                    
                    epsilon = 0.1*cv2.arcLength(cnt1,True)
                    approx1 = cv2.approxPolyDP(cnt1,epsilon,True)
                    epsilon = 0.1*cv2.arcLength(cnt2,True)
                    approx2 = cv2.approxPolyDP(cnt2,epsilon,True)
                    if len(areas) > 2:
                        epsilon = 0.1*cv2.arcLength(cnt3,True)
                        approx3 = cv2.approxPolyDP(cnt3,epsilon,True)
                    
                    x2,y2,w2,h2 = cv2.boundingRect(cnt2)
                    if len(areas) > 2:
                        x3,y3,w3,h3 = cv2.boundingRect(cnt3)
                    x1f = float(x1)
                    y1f = float(y1)
                    w1f = float(w1)
                    h1f = float(h1)
                    x2f = float(x2)
                    y2f = float(y2)
                    w2f = float(w2)
                    h2f = float(h2)
                    if len(areas) > 2:
                        x3f = float(x3)
                        y3f = float(y3)
                        w3f = float(w3)
                        h3f = float(h3)
                    
                    pixel1 = img_hsv[y1 + h1/2, x1 + w1/2]
                    pixel2 = img_hsv[y2 + h2/2, x2 + w2/2]
                    if len(areas) > 2:
                        pixel3 = img_hsv[y3 + h3/2, x3 + w3/2]
                    xmid = (x1f + w1f/2 + x2f + w2f/2) / 2
                    if doPrint:
                        print 'number of areas:', len(areas)
                        if len(areas) > 2:
                            print 'area1, area2, area3:', cv2.contourArea(cnt1), '***', cv2.contourArea(cnt2), '***', cv2.contourArea(cnt3)
                            print 'color:', pixel1[0], pixel1[1], pixel1[2], '***', pixel2[0], pixel2[1], pixel2[2], '***', pixel3[0], pixel3[1], pixel3[2]
                            print 'length:', len(cnt1), len(approx1), '***', len(cnt2), len(approx2), '***', len(cnt3), len(approx3)
                        else:
                            print 'area1, area2:', cv2.contourArea(cnt1), '***', cv2.contourArea(cnt2)
                            print 'color:', pixel1[0], pixel1[1], pixel1[2], '***', pixel2[0], pixel2[1], pixel2[2]
                            print 'length:', len(cnt1), len(approx1), '***', len(cnt2), len(approx2)
                        print 'middle:', xmid
                        print 'compass:', compass.readCompass()
                else:
                    if doPrint:
                        print 'only one area detected'
            else:
                if doPrint:
                    print 'no areas detected'
                
            #Show the image with the recognized contours
            if areas:
                cv2.rectangle(img,(x1,y1),(x1+w1,y1+h1),(0,255,0),2)
                if len(areas) > 1:
                    cv2.rectangle(img,(x2,y2),(x2+w2,y2+h2),(0,255,0),2)
                if len(areas) > 2:
                    cv2.rectangle(img,(x3,y3),(x3+w3,y3+h3),(0,255,0),2)

            # Write images with name like 'tmp_img000042.jpg'.
            # Use leading zeros to make sure order is correct when using shell filename expansion.
            cv2.imwrite('/home/pi/DFRobotUploads/tmp_img' + str(i).zfill(6) + '.jpg', img)

    stdOutAndErr = own_util.runShellCommandWait('mencoder mf:///home/pi/DFRobotUploads/tmp_img*.jpg -mf w=800:h=600:fps=2:type=jpg -ovc lavc -lavcopts vcodec=mpeg4:mbd=2:trell -oac copy -o /home/pi/DFRobotUploads/dfrobot_pivid.avi')
    own_util.writeToLogFile(stdOutAndErr + '\n')
    stdOutAndErr = own_util.runShellCommandWait('rm /home/pi/DFRobotUploads/tmp_img*')
    own_util.writeToLogFile(stdOutAndErr + '\n')

# Main script.
own_util.writeToLogFile('START LOG  *****\n')

# Handle arguments.
for arg in sys.argv[1:]:  # The [1:] is to skip argv[0] which is the script name.
    if arg == '-print':
        doPrint = True
    else:
        print 'illegal arguments, going to exit'
        own_util.writeToLogFile('illegal arguments, going to exit\n')
        exit(1)
    
# First check if there are active connections. If so, do not continue this script.
stdOutAndErr = own_util.runShellCommandWait('netstat | grep 44444 | wc -l')
if int(stdOutAndErr) > 0:
    own_util.writeToLogFile('not going to run because there are active connections\n')
    exit(0)
# Start MJPEG stream needed by runDFRobot.py. Stop previous stream first if any.
own_util.writeToLogFile('going to start stream\n')
stdOutAndErr = own_util.runShellCommandWait('killall mjpg_streamer')
time.sleep(0.5)
own_util.runShellCommandNowait('LD_LIBRARY_PATH=/opt/mjpg-streamer/mjpg-streamer-experimental/ /opt/mjpg-streamer/mjpg-streamer-experimental/mjpg_streamer -i "input_raspicam.so -vf -hf -fps 2 -q 10 -x 800 -y 600" -o "output_http.so -p 44445 -w /opt/mjpg-streamer/mjpg-streamer-experimental/www"')
# Call runRobot() function.
own_util.writeToLogFile('going to call runRobot()\n')
runRobot()
# Stop MJPEG stream.
stdOutAndErr = own_util.runShellCommandWait('killall mjpg_streamer')

# Going to upload the file to Google Drive using the 'drive' utility.
# To upload into the 'DFRobotUploads' folder, the -p option is used with the id of this folder.
# When the 'DFRobotUploads' folder is changed, a new id has to be provided.
# This id can be obtained using 'drive list -t DFRobotUploads'.
# The uploaded file has a distinctive name to enable finding and removing it again with the 'drive' utility.
own_util.writeToLogFile('going to call \'drive\' to upload videofile\n')
stdOutAndErr = own_util.runShellCommandWait('/usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/DFRobotUploads/dfrobot_pivid.avi')
own_util.writeToLogFile(stdOutAndErr + '\n')
own_util.writeToLogFile('going to call \'drive\' to upload logfile\n')
stdOutAndErr = own_util.runShellCommandWait('/usr/local/bin/drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/log/dfrobot_log.txt')
own_util.writeToLogFile(stdOutAndErr + '\n')

# Purge uploads to Google Drive to prevent filling up.
own_util.writeToLogFile('going to call going to call \'purge_dfrobot_uploads.sh\'\n')
# purge_dfrobot_uploads.sh is a bash script which writes to the logfile itself, so do not redirect output.
# This means we cannot use runShellCommandWait() or runShellCommandNowait().
p = subprocess.Popen('/usr/local/bin/purge_dfrobot_uploads.sh dfrobot_pivid.avi 3', shell=True)
p.wait()
p = subprocess.Popen('/usr/local/bin/purge_dfrobot_uploads.sh dfrobot_log.txt 1', shell=True)
p.wait()
