import cv2
import numpy as np
import urllib

template = cv2.imread('template.jpg', 0)
w, h = template.shape[::-1]
stream=urllib.urlopen('http://@localhost:44445/?action=stream')
bytes=''

for i in range(0,10000):
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
    
        print top_left, bottom_right
        cv2.rectangle(img,top_left, bottom_right, 255, 2)
        cv2.imshow("Show",img)
        cv2.waitKey(100)
