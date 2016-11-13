#!/usr/bin/python
import time
import own_util

while True:
    distance = own_util.getDistance("1")
    print "distance =", distance
    time.sleep(0.5)
