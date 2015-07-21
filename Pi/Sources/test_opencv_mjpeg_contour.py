import cv2
import numpy as np
import urllib

stream=urllib.urlopen('http://@localhost:44445/?action=stream')
bytes=''

for i in range(0,10000):
    bytes+=stream.read(1024)
    a = bytes.find('\xff\xd8')
    b = bytes.find('\xff\xd9')
    if a!=-1 and b!=-1:
        jpg = bytes[a:b+2]
        bytes= bytes[b+2:]
        im = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8),cv2.CV_LOAD_IMAGE_COLOR)

        hsv_img = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
        COLOR_MIN = np.array([20, 80, 80],np.uint8)
        COLOR_MAX = np.array([40, 255, 255],np.uint8)
        frame_threshed = cv2.inRange(hsv_img, COLOR_MIN, COLOR_MAX)
        imgray = frame_threshed
        ret,thresh = cv2.threshold(frame_threshed,127,255,0)
        contours, hierarchy = cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)

        # Find the index of the largest contour
        areas = [cv2.contourArea(c) for c in contours]
        if areas:
            max_index = np.argmax(areas)
            cnt=contours[max_index]

            x,y,w,h = cv2.boundingRect(cnt)
            print x,y,w,h
            #cv2.rectangle(im,(x,y),(x+w,y+h),(0,255,0),2)
            #cv2.imshow("Show",im)
            #cv2.waitKey(100)
            #cv2.destroyAllWindows()
        else:
            print 'no areas detected'
