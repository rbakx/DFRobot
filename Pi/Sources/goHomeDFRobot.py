#!/usr/bin/python
import cv2
import numpy as np
import urllib
import subprocess
import os
import time
import compass

logfileName = '/home/pi/log/dfrobot_log.txt'

def prompt( ):
    return '***** ' + time.strftime("%Y-%m-%d %H:%M") + ', ' + __file__ + ': '

def runShellCommandWait( cmd ):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0]

def runShellCommandNowait( cmd ):
    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

def goHomeRobot( ):
    stream=urllib.urlopen('http://@localhost:44445/?action=stream')
    bytes=''
    waitForNextMove = 0
    
    for i in range(0,10000):
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
            
            if waitForNextMove > 0:
                waitForNextMove = waitForNextMove - 1

            # Find the index of the largest contour
            areas = [cv2.contourArea(c) for c in contours]
            if areas:
                max_index = np.argmax(areas)
                cnt=contours[max_index]
                
                
                epsilon = 0.1*cv2.arcLength(cnt,True)
                approx = cv2.approxPolyDP(cnt,epsilon,True)
                
                
                x,y,w,h = cv2.boundingRect(cnt)

                pixel = img_hsv[y + h/2, x + w/2]
                xmid = x + w/2
                logfile.write(prompt() + 'area: ' + str(cv2.contourArea(cnt)) + '\n')
                logfile.write(prompt() + 'color: ' + str(pixel[0]) + ' ' + str(pixel[1]) + ' ' + str(pixel[2]) + '\n')
                logfile.write(prompt() + 'length: ' + str(len(cnt)) + ' ' + str(len(approx)) + '\n')
                logfile.write(prompt() + 'middle: ' + str(xmid) + '\n')
                logfile.write(prompt() + 'compass: ' + str(compass.readCompass()) + '\n')
                print 'area: ', cv2.contourArea(cnt)
                print 'color: ', pixel[0], pixel[1], pixel[2]
                print 'length: ', len(cnt), len(approx)
                print 'middle: ', xmid
                print 'compass: ', compass.readCompass()
                
                if len(approx) == 4:
                    if xmid < 266:
                        if waitForNextMove == 0:
                            stdOutAndErr = runShellCommandWait('i2c_cmd 3 128')
                            waitForNextMove = 3
                    elif xmid > 534:
                        if waitForNextMove == 0:
                            stdOutAndErr = runShellCommandWait('i2c_cmd 4 128')
                            waitForNextMove = 3
                else:
                    if waitForNextMove == 0:
                        stdOutAndErr = runShellCommandWait('i2c_cmd 3 128')
                        waitForNextMove = 3


#                cv2.rectangle(img,(x,y),(x+w,y+h),(0,255,0),2)
#                cv2.imshow("Show",img_thresh)
#                cv2.waitKey(100)
            else:
                print 'no areas detected'
                if waitForNextMove == 0:
                    stdOutAndErr = runShellCommandWait('i2c_cmd 3 128')
                    waitForNextMove = 3

# Main script
# Main script
# Reset the log file to zero length if the size gets too large.
if os.stat(logfileName).st_size > 1000000:
    open(logfileName, 'w').close()

with open(logfileName, 'a') as logfile:
    logfile.write(prompt() + 'START LOG  *****\n')
    
    # Call goHomeRobot()
    goHomeRobot()
