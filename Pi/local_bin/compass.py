#!/usr/bin/python

import RPi.GPIO as GPIO
import smbus
import time
import math
import subprocess
import own_util

rev = GPIO.RPI_REVISION
if rev == 2 or rev == 3:
    bus = smbus.SMBus(1)
else:
    bus = smbus.SMBus(0)

address = 0x1e

def read_byte(adr):
    return bus.read_byte_data(address, adr)

def read_word(adr):
    high = bus.read_byte_data(address, adr)
    low = bus.read_byte_data(address, adr+1)
    val = (high << 8) + low
    return val

def read_word_2c(adr):
    val = read_word(adr)
    if (val >= 0x8000):
        return -((65535 - val) + 1)
    else:
        return val

def write_byte(adr, value):
    bus.write_byte_data(address, adr, value)

def readCompass(debug = False):
    own_util.createI2cLock() # Create i2c lock if it does not exist yet.
    # Lock  i2c communication for this thread.
    own_util.globI2cLock.acquire()
    
    write_byte(0, 0b01110000) # Set to 8 samples @ 15Hz.
    write_byte(1, 0b00100000) # 1.3 gain LSb / Gauss 1090 (default).
    write_byte(2, 0b00000000) # Continuous-Measurement Mode.
    
    time.sleep(0.006)  # Wait 6 ms as specified in data sheet.

    x_out_raw = read_word_2c(3)
    y_out_raw = read_word_2c(7)
    z_out_raw = read_word_2c(5)

    # When supplying a 'True' as parameter to this function the raw X Y Z data and the corrected data will be printed.
    # From measurements of these raw values it shows that we have to compensate quite a bit with a gain and offset.
    # This is because the HMC5883L is mounted on the robot and is very sensitive to surrounding metal and fields.
    # Actual measurements:
    # x_out range: [-174 .. 233]
    # y_out range: [-255 .. 173]
    # We apply a scale and ofset to both x_out and y_out so the range will be [-200 .. 200]
    x_out = x_out_raw * 0.98 - 28.99
    y_out = y_out_raw * 0.93 + 38.32

    bearing  = math.atan2(y_out, x_out)
    if (bearing < 0):
        bearing += 2 * math.pi
    degrees = math.degrees(bearing)
    
    # Delay for i2c communication.
    time.sleep(0.01)

    # Release i2c communication for this thread.
    own_util.globI2cLock.release()

    if debug:
        return x_out_raw, y_out_raw, z_out_raw, x_out, y_out, degrees
    else:
        return degrees

# The below function is to test the compass.
def testCompass():
    while True:
        (x_out_raw, y_out_raw, z_out_raw, x_out, y_out, degrees) = readCompass(True)
        print 'raw X Y Z:', x_out_raw, y_out_raw, z_out_raw
        print 'corrected X Y and degrees:', int(x_out), int(y_out), round(degrees,2)
        time.sleep(0.5)

# The below function is to find the calibration values for the compass.
def calibrateCompass():
    x_out_raw_min = float("infinity")
    x_out_raw_max = float("-infinity")
    y_out_raw_min = float("infinity")
    y_out_raw_max = float("-infinity")
    # Turn around a few times to make sure all angles are measured.
    for i in range(600):
        (x_out_raw, y_out_raw, z_out_raw, x_out, y_out, degrees) = readCompass(True)
        own_util.move('right', 128, 0.2, True)
        if x_out_raw_min > x_out_raw:
            x_out_raw_min = x_out_raw
        if x_out_raw_max < x_out_raw:
            x_out_raw_max = x_out_raw
        if y_out_raw_min > y_out_raw:
            y_out_raw_min = y_out_raw
        if y_out_raw_max < y_out_raw:
            y_out_raw_max = y_out_raw
        print str(i) + ':', 'x_out_raw y_out_raw z_out_raw =', x_out_raw, y_out_raw, z_out_raw
    x_factor = 400.0 / (x_out_raw_max - x_out_raw_min)
    x_offset = 200.0 - x_out_raw_max * x_factor
    y_factor = 400.0 / (y_out_raw_max - y_out_raw_min)
    y_offset = 200.0 - y_out_raw_max * y_factor
    print 'x_out_raw_min x_out_raw_max =', round(x_out_raw_min,2), round(x_out_raw_max,2)
    print 'y_out_raw_min y_out_raw_max =', round(y_out_raw_min,2), round(y_out_raw_max,2)
    print 'x-factor =', round(x_factor,2)
    print 'x-offset =', round(x_offset,2)
    print 'y-factor =', round(y_factor,2)
    print 'y-offset =', round(y_offset,2)

def gotoDegreeAbs(targetDegree, doMove):
    currentDegree = readCompass()
    diffAngle = targetDegree - currentDegree
    if diffAngle > 180:
        diffAngle = diffAngle - 360
    elif diffAngle < -180:
        diffAngle = diffAngle + 360
    if doMove == False:
        return diffAngle
    while abs(diffAngle) > 1.0:
        if diffAngle > 0:
            if abs(diffAngle) < 20:
                own_util.move('right', 128, 1.0, True)
            elif abs(diffAngle) < 50:
                own_util.move('right', 140, 1.0, True)
            else:
                own_util.move('right', 160, 1.0, True)
        else:
            if abs(diffAngle) < 20:
                own_util.move('left', 128, 1.0, True)
            elif abs(diffAngle) < 50:
                own_util.move('left', 140, 1.0, True)
            else:
                own_util.move('left', 160, 1.0, True)
        currentDegree = readCompass()
        diffAngle = targetDegree - currentDegree
        if diffAngle > 180:
            diffAngle = diffAngle - 360
        elif diffAngle < -180:
            diffAngle = diffAngle + 360
    return diffAngle

def gotoDegreeRel(targetDegree, doMove):
    currentDegree = readCompass()
    diffAngle = gotoDegreeAbs(currentDegree + targetDegree, doMove)
    return diffAngle

