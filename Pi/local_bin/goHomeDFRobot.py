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

def goHomeRobot( ):
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
            #cv2.rectangle(img,top_left, bottom_right, 255, 2)
            #cv2.imshow("Show",img)
            #cv2.waitKey(100)

# Main script
# Reset the log file to zero length if the size gets too large.
if os.stat(logfileName).st_size > 1000000:
    open(logfileName, 'w').close()

with open(logfileName, 'a') as logfile:
    logfile.write(prompt() + 'START LOG  *****\n')

    # Call goHomeRobot() function.
    logfile.write(prompt() + 'going to call goHomeRobot()\n')
    goHomeRobot()
