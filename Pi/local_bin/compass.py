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
    # x_out range: [-170 .. 228]
    # y_out range: [-480 .. -55]
    # We apply a scale and ofset to both x_out and y_out so the range will be [-200 .. 200]
    x_out = x_out_raw * 1.005 - 29.14
    y_out = y_out_raw * 0.941 + 251.68

    bearing  = math.atan2(y_out, x_out)
    if (bearing < 0):
        bearing += 2 * math.pi
    degrees = math.degrees(bearing)
    
    if debug == True:
        print 'raw X Y Z:', x_out_raw, y_out_raw, z_out_raw
        print 'corrected X Y and degrees:', int(x_out), int(y_out), round(degrees,2)
    
    return degrees

# The below function is to test the compass and check which values to use for calibration.
def testCompass():
    while True:
        readCompass(True)
        time.sleep(0.5)

def gotoDegree(targetDegree, doMove):
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
                own_util.moveDirect('right', 128, True)
                time.sleep(0.5)
            elif abs(diffAngle) < 50:
                own_util.moveDirect('right', 140, True)
                time.sleep(0.5)
            else:
                own_util.moveDirect('right', 160, True)
                time.sleep(0.5)
        else:
            if abs(diffAngle) < 20:
                own_util.moveDirect('left', 128, True)
                time.sleep(0.5)
            elif abs(diffAngle) < 50:
                own_util.moveDirect('left', 140, True)
                time.sleep(0.5)
            else:
                own_util.moveDirect('left', 160, True)
                time.sleep(0.5)
        currentDegree = readCompass()
        diffAngle = targetDegree - currentDegree
        if diffAngle > 180:
            diffAngle = diffAngle - 360
        elif diffAngle < -180:
            diffAngle = diffAngle + 360
    return diffAngle

