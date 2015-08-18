#!/usr/bin/python
import cv2
import numpy as np
import urllib
import subprocess
import sys
import os
import time
import thread
import compass
import own_util

doFullRun = False
doHomeRun = False
doPrint = False
doTestMotion = False
doShow = False
doMove = True

directionFront = 293.0
directionRight = 25.0
directionBack = 115.0
directionLeft = 203.0

motionDetectionBufferLength = 60 # number of images in motion detection buffer
motionDetectionBufferOffset = 5  # number of images that are kept before the motion is detected

def getNewImage( ):
    global globContinue, globBytes, globStream, globImg, globNewImageAvailable, globNewImageAvailableLock
    
    while globContinue == True:
        globBytes+=globStream.read(1024)
        a = globBytes.find('\xff\xd8')
        b = globBytes.find('\xff\xd9')
        if a!=-1 and b!=-1:
            jpg = globBytes[a:b+2]
            globBytes= globBytes[b+2:]
            
            globNewImageAvailableLock.acquire()
            globImg = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8),cv2.CV_LOAD_IMAGE_COLOR)
            globNewImageAvailable = True
            globNewImageAvailableLock.release()


def homeRun( ):
    global globContinue, globBytes, globStream, globImg, globNewImageAvailable, globNewImageAvailableLock
    
    globStream=urllib.urlopen('http://@localhost:44445/?action=stream')
    globBytes=''
    globNewImageAvailable = False
    globNewImageAvailableLock = thread.allocate_lock()
    globContinue = True
    thread.start_new_thread(getNewImage, ())

    correctApproachAngle = False
    correction = 0
    imgHeight, imgWidth = 0, 0
    imgCount = 0
    
    # Remove tmp_img and tmp_tmp_img files to be sure no tmp images are left from a previous run.
    stdOutAndErr = own_util.runShellCommandWait('rm -f /home/pi/DFRobotUploads/tmp_*img*')
    own_util.writeToLogFile(stdOutAndErr + '\n')

    while globContinue == True:
        globNewImageAvailableLock.acquire()
        newImageAvailable = globNewImageAvailable
        if newImageAvailable:
            img = globImg.copy()
            globNewImageAvailableLock.release()
            img_gray = cv2.cvtColor(img, cv2.cv.CV_BGR2GRAY)
            img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            imgHeight, imgWidth = img.shape[:2]
            
            # Set constants which depend on the size of the image.
            imgWidthFactor = imgWidth / 640.0  # calibrated with 640 * 480 image
            imgHeightFactor = imgHeight / 480.0  # calibrated with 640 * 480 image
            imgAreaFactor = (imgWidth * imgHeight) / (640.0 * 480.0)  # calibrated with 640 * 480 image
            sizeCorrect = 20.0 * imgWidthFactor  # calibrated with 640 * 480 image
            sizeSlow = 20.0 * imgWidthFactor  # calibrated with 640 * 480 image
            sizeStop = 40.0 * imgWidthFactor  # calibrated with 640 * 480 image
    
            # Get average brightness of hsv image by averaging the 'v' (value or brightness) bytes.
            totalPixel = cv2.sumElems(img_hsv)
            avgBrightness = totalPixel[2] / (imgWidth * imgHeight)
            if doPrint:
                print 'brightness:', avgBrightness

            # Setup SimpleBlobDetector parameters.
            params = cv2.SimpleBlobDetector_Params()

            # Change thresholds
            # The default value of params.thresholdStep (10?) seems to work well.
            # To speed processing up, increase to 20 or more.
            #params.thresholdStep = 20
            params.minThreshold = 20;
            params.maxThreshold = 200;

            # Filter by Area.
            # This prevents that many small blobs (one pixel) will be detected.
            # In addition tt is observed that in that case invalid keypoint coordinates are produced: nan (not a number).
            # When filterByArea is set to True with a minArea > 0 this problem does not occur.
            params.filterByArea = True
            params.minArea = 100 * imgAreaFactor
            params.maxArea = 100000 * imgAreaFactor

            # Filter by Circularity
            params.filterByCircularity = True
            params.minCircularity = 0.80

            # Filter by Convexity
            params.filterByConvexity = False
            params.minConvexity = 0.87

            # Filter by Inertia
            params.filterByInertia = False
            params.minInertiaRatio = 0.01
            
            #Filter by distance between blobs
            #params.minDistBetweenBlobs = 100
            
            # Detect blobs.
            detector = cv2.SimpleBlobDetector(params)
            blobs = detector.detect(img_gray)
            
            # Sort blobs on horizontal position and check if they are valid.
            sortedBlobs = sorted(blobs, key=lambda x: x.pt[0], reverse=False)
            blobLeft = None
            blobMiddle = None
            blobRight = None
            validBlobsFound = False
            for blob in sortedBlobs:
                # Fill in three blobs, left, middle, right.
                if blobLeft == None:
                    blobLeft = blob
                elif blobMiddle == None:
                    # Skip blop if it is significantly smaller than the first blob.
                    if blob.size < blobLeft.size/2.0:
                        continue
                    blobMiddle = blob
                elif blobRight == None:
                    # Skip blop if it is significantly smaller than the first blob.
                    if blob.size < blobLeft.size/2.0:
                        continue
                    blobRight = blob
                    # We have three blobs now, check if these are valid
                    # For now we consider the blobs valid if the left and right one have appr. equal size.
                    distBlobLeftBlobRight = blobRight.pt[0] - blobLeft.pt[0]
                    avgSizeBlobLeftBlobRight = (blobLeft.size + blobRight.size) / 2.0
                    if (blobLeft.size - blobRight.size) / avgSizeBlobLeftBlobRight < 0.3 and (distBlobLeftBlobRight - avgSizeBlobLeftBlobRight * 7.33) / ((distBlobLeftBlobRight + avgSizeBlobLeftBlobRight * 7.33) / 2.0) < 0.3:
                        validBlobsFound = True
                    else:
                        if doPrint:
                            print 'Blob conditions not met, left:', blobLeft.pt[0], blobLeft.size, 'middle:', blobMiddle.pt[0], blobMiddle.size, 'right:', blobRight.pt[0], blobRight.size, 'distBlobLeftBlobRight:', distBlobLeftBlobRight
                    if validBlobsFound:
                        # We have found three valid blobs, break out of loop.
                        break
                    else:
                        # No valid blobs found yet, shift one blob up.
                        # We assume that valid blobs are adjacent.
                        # This is reasonable as the real blobs will indeed be close to each other.
                        blobLeft = blobMiddle
                        blobMiddle = blobRight
                        blobRight = None

            if correctApproachAngle:
                # Going to check and correct the approach angle.
                if correction > 1.5:  # we have to turn to the left, move forward and then turn back again
                    if doPrint:
                        print '********** Going to do approach correction to the left.'
                        if validBlobsFound:
                            print '********** Valid blobs found!'
                            print 'left:', blobLeft.pt[0], blobLeft.size, 'middle:', blobMiddle.pt[0], blobMiddle.size, 'right:', blobRight.pt[0], blobRight.size, 'distBlobLeftBlobRight:', distBlobLeftBlobRight
                        else:
                            print '********** No valid blobs found.'
                    own_util.move('left', 240 - correction * 1, 1.0, doMove)
                    own_util.move('forward', 130 + correction * 3, 1.0, doMove)
                    # move back towards target and wait a bit longer for the image to stabilize
                    own_util.move('right', 240 - correction * 1, 5.0, doMove)
                    # approach correction finished
                    correctApproachAngle = False
                    if doPrint:
                        print 'Approach correction Finished.'
                elif correction < -1.5:  # we have to turn to the right, move forward and then turn back again
                    if doPrint:
                        print 'Going to do approach correction to the right.'
                    own_util.move('right', 240 + correction * 1, 1.0, doMove)
                    own_util.move('forward', 130 - correction * 3, 1.0, doMove)
                    # move back towards target and wait a bit longer for the image to stabilize
                    own_util.move('left', 240 + correction * 1, 5.0, doMove)
                    # approach correction finished
                    correctApproachAngle = False
                    if doPrint:
                        print 'Approach correction finished.'

            elif validBlobsFound:
                if doPrint:
                    print '********** Valid blobs found!'
                    print 'left:', blobLeft.pt[0], blobLeft.size, 'middle:', blobMiddle.pt[0], blobMiddle.size, 'right:', blobRight.pt[0], blobRight.size, 'distBlobLeftBlobRight:', distBlobLeftBlobRight
                # Go home!
                xmid = (blobLeft.pt[0] + blobRight.pt[0]) / 2.0
                ymid = (blobLeft.pt[1] + blobRight.pt[1]) / 2.0
                course = imgWidth / 2.0
                correction = (xmid - blobMiddle.pt[0]) / imgWidthFactor
                if doPrint:
                    print 'xmid, course, correction:', xmid, course, correction
                if xmid < course - imgWidth / 30.0:
                    if doPrint:
                        print 'turn left'
                    if xmid < course - imgWidth / 5.0:
                        own_util.move('left', 140, 1.0, doMove)
                    else:
                        own_util.move('left', 128, 1.0, doMove)
                elif xmid > course + imgWidth / 30.0:
                    if doPrint:
                        print 'turn right'
                    if xmid > course + imgWidth / 5.0:
                        own_util.move('right', 140, 1.0, doMove)
                    else:
                        own_util.move('right', 128, 1.0, doMove)
                elif abs(correction) > 2.0 and avgSizeBlobLeftBlobRight > sizeCorrect:
                    correctApproachAngle = True
                else:
                    if avgSizeBlobLeftBlobRight < sizeStop:
                        if doPrint:
                            print 'move forward'
                        # Move cam to vertically center the target.
                        own_util.moveCamRel(30 * (imgHeight/2 - ymid) / imgHeight)
                        if avgSizeBlobLeftBlobRight < sizeSlow:
                            own_util.move('forward', 160, 1.0, doMove)
                        else:
                            own_util.move('forward', 140, 1.0, doMove)
                    else:
                        # Move cam down again.
                        own_util.moveCamAbs(0)
                        compass.gotoDegreeRel(180, doMove)
                        for i in range(0, 10):
                            own_util.move('backward', 140, 1.0, doMove)
                        own_util.writeToLogFile('Home found!\n')
                        globContinue = False

            elif len(sortedBlobs) > 0:
                if doPrint:
                    print '**********', len(sortedBlobs), 'Blobs found, but not valid.'
                    print 'turn left'
                own_util.move('left', 160, 1.0, doMove)
            else:
                if doPrint:
                    print '********** No blobs found.'
                    print 'turn left'
                own_util.move('left', 160, 1.0, doMove)

            for blob in sortedBlobs:
                x = blob.pt[0]
                y = blob.pt[1]
                cv2.circle(img, (int(x), int(y)), int(blob.size), (0, 255, 0), 2)
            
            # Write images with name like 'tmp_img000042.jpg'.
            # Use leading zeros to make sure order is correct when using shell filename expansion.
            cv2.imwrite('/home/pi/DFRobotUploads/tmp_img' + str(imgCount).zfill(6) + '.jpg', img)
            
            if doShow:
                # Show keypoints
                cv2.imshow("Keypoints", img)
                cv2.waitKey(100)
            
            # Increase imgCount with a maximum for protection.
            imgCount = (imgCount + 1) % 600

            # Ready with movement. Make globNewImageAvailable false to make sure a new image is taken after movement.
            globNewImageAvailableLock.acquire()
            globNewImageAvailable = False
            globNewImageAvailableLock.release()
        else:
            globNewImageAvailableLock.release()
                
    # Close the stream to have a correct administration of the number of connections.
    globStream.close()
    # Convert the homerun images to a video and remove the images.
    stdOutAndErr = own_util.runShellCommandWait('mencoder mf:///home/pi/DFRobotUploads/tmp_img*.jpg -mf w=' + str(imgWidth) + ':h=' + str(imgHeight) + ':fps=2:type=jpg -ovc lavc -lavcopts vcodec=mpeg4:mbd=2:trell -oac copy -o /home/pi/DFRobotUploads/dfrobot_pivid_homerun.avi')
    own_util.writeToLogFile(stdOutAndErr + '\n')
    # Remove tmp_img and tmp_tmp_img files.
    stdOutAndErr = own_util.runShellCommandWait('rm -f /home/pi/DFRobotUploads/tmp_*img*')
    own_util.writeToLogFile(stdOutAndErr + '\n')


def motionDetection( ):
    global globContinue, globBytes, globStream, globImg, globNewImageAvailable, globNewImageAvailableLock
    
    globStream=urllib.urlopen('http://@localhost:44445/?action=stream')
    globBytes=''
    globNewImageAvailable = False
    globNewImageAvailableLock = thread.allocate_lock()
    globContinue = True
    thread.start_new_thread(getNewImage, ())
    
    img_gray = img_gray_prev = None
    imgCount = 0
    imgHeight = imgWidth = 0
    startDetection = motionDetected = prevMotionDetected = False
    noOfConsecutiveMotions = 0
    firstImageIndex = 0
    
    # Remove tmp_img and tmp_tmp_img files to be sure no tmp images are left from a previous run.
    stdOutAndErr = own_util.runShellCommandWait('rm -f /home/pi/DFRobotUploads/tmp_*img*')
    own_util.writeToLogFile(stdOutAndErr + '\n')

    while globContinue == True:
        stdOutAndErr = own_util.runShellCommandWait('netstat | grep -E \'44444.*ESTABLISHED|44445.*ESTABLISHED\' | wc -l')
        if int(stdOutAndErr) > 2:
            if doPrint:
                print 'stopping motion detection because there are active connections:', stdOutAndErr
            own_util.writeToLogFile('stopping motion detection because there are extra connections\n')
            globStream.close()
            globContinue = False
            return False
        globNewImageAvailableLock.acquire()
        newImageAvailable = globNewImageAvailable
        if newImageAvailable:
            img = globImg.copy()
            globNewImageAvailableLock.release()
            if img_gray != None:
                img_gray_prev = img_gray.copy()
            img_gray = cv2.cvtColor(img, cv2.cv.CV_BGR2GRAY)
            img_gray = cv2.GaussianBlur(img_gray, (21, 21), 0)
            
            imgHeight, imgWidth = img.shape[:2]

            # Set constants which depend on the size of the image.
            imgAreaFactor = (imgWidth * imgHeight) / (640.0 * 480.0)  # calibrated with 640 * 480 image
                
            if imgCount > 20:
                # Start motion detection  after image is stabilized.
                startDetection = True
                        
            if startDetection and img_gray_prev != None:
                img_gray_diff = cv2.absdiff(img_gray, img_gray_prev)
                img_bw_diff = cv2.threshold(img_gray_diff, 10, 255, cv2.THRESH_BINARY)[1]
                (cnts, _) = cv2.findContours(img_bw_diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
                if doPrint:
                    print 'number of contours:', len(cnts)

                # Loop over the contours.
                # If number of contours is too high, it is not normal motion.
                if len(cnts) < 200:
                    # xLeft, xRight, yTop, yBottom will be the coordinates of the outer bounding box of all contours.
                    xLeft = imgWidth
                    xRight = 0
                    yTop = imgHeight
                    yBottom = 0
                    nofValidContours = 0
                    for c in cnts:
                        # If the contour is too small, ignore it.
                        if cv2.contourArea(c) > 700 * imgAreaFactor:
                            # Compute the outer bounding box of all valid contours.
                            nofValidContours = nofValidContours + 1
                            x,y,w,h = cv2.boundingRect(c)
                            xLeft = x if x < xLeft else xLeft
                            xRight = x+w if x+w > xRight else xRight
                            yTop = y if y < yTop else yTop
                            yBottom = y+h if y+h > yBottom else yBottom
                            if doShow:
                                # Only with -show option draw all the contours.
                                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    if nofValidContours > 0:
                        totalArea = (xRight - xLeft) * (yBottom - yTop)
                        if doPrint:
                            print 'total area:', totalArea
                        if totalArea < (imgWidth * imgHeight) * 0.5:
                            # Motion is detected for this image.
                            # Consider true motion detected only after sufficient images in sequence with motion.
                            noOfConsecutiveMotions = noOfConsecutiveMotions + 1
                            if noOfConsecutiveMotions >= 3:
                                if doPrint:
                                    print '******************** MOTION DETECTED! ********************'
                                # Draw the outer bounding box of all contours.
                                cv2.rectangle(img, (xLeft, yTop), (xRight, yBottom), (0, 255, 255), 2)
                                if doTestMotion == False:
                                    motionDetected = True
                        else:
                            # Reset, images with motion have to be in sequence.
                            noOfConsecutiveMotions = 0
                
            # Write images with name like 'tmp_img000042.jpg'.
            # Use leading zeros to make sure order is correct when using shell filename expansion.
            cv2.imwrite('/home/pi/DFRobotUploads/tmp_tmp_img' + str(imgCount).zfill(6) + '.jpg', img)
                
            if motionDetected == True:
                # Motion is detected,
                # now acquire motionDetectionBufferLength - motionDetectionBufferOffset new images.
                # First determine where we are in the circular buffer.
                if prevMotionDetected == False and motionDetected == True:
                    firstImageIndex = imgCount
                    extraImgCount = 0
                    prevMotionDetected = True
                else:
                    extraImgCount = extraImgCount + 1
                    if doPrint:
                        print 'capturing extra image no:', extraImgCount

                    if extraImgCount == motionDetectionBufferLength - motionDetectionBufferOffset - 1:
                        # All required images for this motion are captured, stop the capturing.
                        globContinue = False

            if doShow:
                # Show motion
                cv2.imshow("Motion", img)
                cv2.waitKey(100)

            # imgCount keeps position in circular buffer.
            imgCount = (imgCount + 1) % motionDetectionBufferLength
            
            # Ready with this image. Make globNewImageAvailable false to make sure a new image is taken.
            globNewImageAvailableLock.acquire()
            globNewImageAvailable = False
            globNewImageAvailableLock.release()
        else:
            globNewImageAvailableLock.release()

    # Close the stream to have a correct administration of the number of connections.
    globStream.close()
    # Motion detection loop is finished. The images are in a circular buffer and the first image with
    # motion is at firstImageIndex. Before this image there are motionDetectionBufferOffset images
    # before the motion.
    # Before we can make a movie we have to shift the motion detection images so the preamble
    # starts at index 0.
    for i in range(0, motionDetectionBufferLength):
        # Rename images such that tmp_img000000.jpg is the first image to show in the movie.
        # Note that this is motionDetectionBufferOffset images before motion is detected.
        iOffset = i - (firstImageIndex - motionDetectionBufferOffset)
        # Map iOffset back into circular buffer.
        if iOffset < 0:
            iOffset = iOffset + motionDetectionBufferLength
        elif iOffset >= motionDetectionBufferLength:
            iOffset = iOffset - motionDetectionBufferLength
        # Rename the tmp_tmp_img file with index i to tmp_img files with the correct index iOffset.
        stdOutAndErr = own_util.runShellCommandWait('mv /home/pi/DFRobotUploads/tmp_tmp_img' + str(i).zfill(6) + '.jpg' + ' /home/pi/DFRobotUploads/tmp_img' + str(iOffset).zfill(6) + '.jpg')
    # Motion detection images are shifted now. Convert the images to a video and remove the images.
    stdOutAndErr = own_util.runShellCommandWait('mencoder mf:///home/pi/DFRobotUploads/tmp_img*.jpg -mf w=' + str(imgWidth) + ':h=' + str(imgHeight) + ':fps=2:type=jpg -ovc lavc -lavcopts vcodec=mpeg4:mbd=2:trell -oac copy -o /home/pi/DFRobotUploads/dfrobot_pivid_motion.avi')
    own_util.writeToLogFile(stdOutAndErr + '\n')
    # Remove tmp_img and tmp_tmp_img files.
    stdOutAndErr = own_util.runShellCommandWait('rm -f /home/pi/DFRobotUploads/tmp_*img*')
    own_util.writeToLogFile(stdOutAndErr + '\n')
    return True


# Main script.
own_util.writeToLogFile('START LOG  *****\n')

# Handle arguments.
for arg in sys.argv[1:]:  # The [1:] is to skip argv[0] which is the script name.
    if arg == '-fullrun':
        doFullRun = True
    elif arg == '-homerun':
        doHomeRun = True
    elif arg == '-print':
        doPrint = True
    elif arg == '-testmotion':
        doTestMotion = True
        doFullRun = True
        doPrint = True
    elif arg == '-show':
        doShow = True
    elif arg == '-nomove':
        doMove = False
    else:
        print 'illegal arguments, going to exit'
        own_util.writeToLogFile('illegal arguments, going to exit\n')
        exit(1)

# This script can run the robot in different modes:
# Full run:
#   The robot does motion detection and uploads a video to Google Drive when motion is detected.
#   Once every hour the robot drives out of its garage, makes an exploratory round
#   and returns to the garage where it makes connection with the charging station.
#   This video is also uploaded to Google Drive.
# Home run:
#   The robot finds and drives back to the garage where it makes connection with the charging station.
if doFullRun:
    # Full run
    while True:
        # First check if there are active connections. If so, do not continue.
        stdOutAndErr = own_util.runShellCommandWait('netstat | grep -E \'44444.*ESTABLISHED|44445.*ESTABLISHED\' | wc -l')
        if int(stdOutAndErr) > 0:
            if doPrint:
                print 'not going to do full run because there are active connections:', stdOutAndErr
        else:
            # Start MJPEG stream. Stop previous stream first if any.
            own_util.writeToLogFile('going to start stream\n')
            stdOutAndErr = own_util.runShellCommandWait('killall mjpg_streamer')
            time.sleep(0.5)
            own_util.runShellCommandNowait('LD_LIBRARY_PATH=/opt/mjpg-streamer/mjpg-streamer-experimental/ /opt/mjpg-streamer/mjpg-streamer-experimental/mjpg_streamer -i "input_raspicam.so -vf -hf -fps 2 -q 10 -x 800 -y 600" -o "output_http.so -p 44445 -w /opt/mjpg-streamer/mjpg-streamer-experimental/www"')
            # Delay to give stream time to start up.
            time.sleep(0.5)
            own_util.writeToLogFile('going to call detectMotion()\n')
            # Call motionDetection(). This function returns with True when motion is detected
            # and dfrobot_pivid_motion.avi is created. It returns false when no motion is detected but other
            # connectios are becoming active.
            motionDetected = motionDetection()
            # Stop MJPEG stream.
            stdOutAndErr = own_util.runShellCommandWait('killall mjpg_streamer')

            if motionDetected:
                own_util.writeToLogFile('motion detected!\n')
                # Upload and purge the video file.
                own_util.uploadAndPurge('dfrobot_pivid_motion.avi', 5)
elif doHomeRun:
    # Home run
    homeRun()
    # Upload and purge the video file.
    own_util.uploadAndPurge('dfrobot_pivid_homerun.avi', 3)

