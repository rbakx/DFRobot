#!/usr/bin/python
import time
import own_gpio


own_gpio.initGpio()
while True:
    distance = own_gpio.getUsSensorDistance(0)
    print "distance =", distance
    time.sleep(0.1)  # Wait for the echo to damp out.
