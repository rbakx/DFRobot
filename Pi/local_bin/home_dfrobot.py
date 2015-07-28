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
doShow = False
doMove = True

directionFront = 312.0
directionRight = 24.0
directionBack = 160.0
directionLeft = 258.0

def homeRobot( ):
    stream=urllib.urlopen('http://@localhost:44445/?action=stream')
    bytes=''
    isHome = False
    
    move1Done = move2Done = move3Done = correctApproach = False
    correction = 0
    while isHome == False:
        bytes+=stream.read(1024)
        a = bytes.find('\xff\xd8')
        b = bytes.find('\xff\xd9')
        if a!=-1 and b!=-1:
            jpg = bytes[a:b+2]
            bytes= bytes[b+2:]
            
            img = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8),cv2.CV_LOAD_IMAGE_COLOR)
            img_gray = cv2.cvtColor(img, cv2.cv.CV_BGR2GRAY)
            img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            imgHeight, imgWidth = img.shape[:2]
            if doPrint:
                print 'imgWidth, imgHeight:', imgWidth, imgHeight
            
            # Set constants which depend on the size of the image.
            imgWidthFactor = imgWidth / 640.0  # calibrated with 640 * 480 image
            imgHeightFactor = imgHeight / 480.0  # calibrated with 640 * 480 image
            imgAreaFactor = (imgWidth * imgHeight) / (640.0 * 480.0)  # calibrated with 640 * 480 image
            sizeCorrect = 20.0 * imgWidthFactor  # calibrated with 640 * 480 image
            sizeSlow = 30.0 * imgWidthFactor  # calibrated with 640 * 480 image
            sizeStop = 40.0 * imgWidthFactor  # calibrated with 640 * 480 image
    
            # Get average brightness of hsv image by averaging the 'v' (value or brightness) bytes.
            totalPixel = cv2.sumElems(img_hsv)
            avgBrightness = totalPixel[2] / (imgWidth * imgHeight)
            if doPrint:
                print 'brightness:', avgBrightness

            # Setup SimpleBlobDetector parameters.
            params = cv2.SimpleBlobDetector_Params()

            # Change thresholds
            # The default value of params.thresholdStep (about 10?) seems to work well.
            # To speed processing up, increase to 20 or more.
            #params.thresholdStep = 20
            params.minThreshold = 20;
            params.maxThreshold = 200;

            # Filter by Area.
            # This prevents that many small blobs (one pixel) will be detected.
            # In addition tt is observed that in that case invalid keypoint coordinates are produced: nan (not a number).
            # When filterByArea is set to True with a minArea > 0 this problem does not occur.
            params.filterByArea = True
            params.minArea = 100
            params.maxArea = 100000

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
            
            # Sort blobs on size and check if they are valid.
            sortedBlobs = sorted(blobs, key=lambda x: x.pt[0], reverse=False)
            blobLeft = None
            blobMiddle = None
            blobRight = None
            validBlobsFound = False
            for blob in sortedBlobs:
                # Fill in three blobs, left, middle right.
                if blobLeft == None:
                    blobLeft = blob
                elif blobMiddle == None:
                    blobMiddle = blob
                elif blobRight == None:
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

            if correctApproach:
                # Going to check and correct the approach angle.
                if correction > 0.5:  # we have to turn to the left, move forward and then turn back again
                    if doPrint:
                        print 'Going to do approach correction to the left.'
                    if not move1Done:
                        move1Done = own_util.move('left', 255 - correction * 1, doMove)
                    elif not move2Done:
                        move2Done = own_util.move('forward', 128 + correction * 4, doMove)
                    elif not move3Done:
                        move3Done = own_util.move('right', 255 - correction * 1, doMove)
                    else:
                        # approach correction finished
                        move1Done = move2Done = move3Done = correctApproach = False
                        if doPrint:
                            print 'Approach correction Finished.'
                elif correction < -0.5:  # we have to turn to the right, move forward and then turn back again
                    if doPrint:
                        print 'Going to do approach correction to the right.'
                    if not move1Done:
                        move1Done = own_util.move('right', 255 + correction * 1, doMove)
                    elif not move2Done:
                        move2Done = own_util.move('forward', 128 - correction * 4, doMove)
                    elif not move3Done:
                        move3Done = own_util.move('left', 255 + correction * 1, doMove)
                    else:
                        # approach correction finished
                        move1Done = move2Done = move3Done = correctApproach = False
                        if doPrint:
                            print 'Approach correction finished.'
                                
            elif validBlobsFound:
                if doPrint:
                    print '********** Valid blobs found!'
                    print 'left:', blobLeft.pt[0], blobLeft.size, 'middle:', blobMiddle.pt[0], blobMiddle.size, 'right:', blobRight.pt[0], blobRight.size, 'distBlobLeftBlobRight:', distBlobLeftBlobRight
                    # Go home!
                    xmid = (blobLeft.pt[0] + blobRight.pt[0]) / 2.0
                    course = imgWidth / 2.0
                    correction = (xmid - blobMiddle.pt[0]) / imgWidthFactor
                    if doPrint:
                        print 'xmid, course, correction:', xmid, course, correction
                    if xmid < course - imgWidth / 30.0:
                        if doPrint:
                            print 'turn left'
                        if xmid < course - imgWidth / 5.0:
                            own_util.move('left', 128, doMove)
                        else:
                            own_util.move('left', 128, doMove)
                    elif xmid > course + imgWidth / 30.0:
                        if doPrint:
                            print 'turn right'
                        if xmid > course + imgWidth / 5.0:
                            own_util.move('right', 128, doMove)
                        else:
                            own_util.move('right', 128, doMove)
                    elif abs(correction) > 0.5 and avgSizeBlobLeftBlobRight > sizeCorrect:
                        correctApproach = True
                    else:
                        if avgSizeBlobLeftBlobRight < sizeStop:
                            if doPrint:
                                print 'turn left'
                            if avgSizeBlobLeftBlobRight < sizeSlow:
                                own_util.move('forward', 160, doMove)
                            else:
                                own_util.move('forward', 130, doMove)
                        else:
                            isHome = True

            elif len(sortedBlobs) > 0:
                if doPrint:
                    print '**********', len(sortedBlobs), 'Blobs found, but not valid.'
                    print 'turn left'
                own_util.move('left', 160, doMove)
            else:
                if doPrint:
                    print '********** No blobs found.'
                    print 'turn left'
                own_util.move('left', 160, doMove)

            for blob in sortedBlobs:
                x = blob.pt[0]
                y = blob.pt[1]
                cv2.circle(img, (int(x), int(y)), int(blob.size), (0, 255, 0), 2)
            if doShow:
                # Show keypoints
                cv2.imshow("Keypoints", img)
                cv2.waitKey(100)


# Main script.
own_util.writeToLogFile('START LOG  *****\n')

# Handle arguments.
for arg in sys.argv[1:]:  # The [1:] is to skip argv[0] which is the script name.
    if arg == '-print':
        doPrint = True
    elif arg == '-nomove':
        doMove = False
    elif arg == '-show':
        doShow = True
    else:
        print 'illegal arguments, going to exit'
        own_util.writeToLogFile('illegal arguments, going to exit\n')
        exit(1)

# Call homeRobot()
homeRobot()
