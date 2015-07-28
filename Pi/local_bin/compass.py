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

def readCompass():
    write_byte(0, 0b01110000) # Set to 8 samples @ 15Hz
    write_byte(1, 0b00100000) # 1.3 gain LSb / Gauss 1090 (default)
    write_byte(2, 0b00000000) # Continuous sampling
    
    scale = 0.92
    
    x_out = read_word_2c(3) * scale
    y_out = read_word_2c(7) * scale
    z_out = read_word_2c(5) * scale
    
    bearing  = math.atan2(y_out, x_out)
    if (bearing < 0):
        bearing += 2 * math.pi
    
    return math.degrees(bearing)

def gotoDegree(targetDegree, doMove):
    currentDegree = readCompass()
    diffAngle = targetDegree - currentDegree
    if diffAngle > 180:
        diffAngle = diffAngle - 360
    elif diffAngle < -180:
        diffAngle = diffAngle + 360
    if doMove == False:
        return diffAngle
    while abs(diffAngle) > 2:
        if diffAngle > 0:
            if abs(diffAngle) < 10:
                own_util.moveDirect('right', 128, True)
                time.sleep(0.5)
            elif abs(diffAngle) < 40:
                own_util.moveDirect('right', 140, True)
                time.sleep(0.5)
            else:
                own_util.moveDirect('right', 160, True)
                time.sleep(0.5)
        else:
            if abs(diffAngle) < 10:
                own_util.moveDirect('left', 128, True)
                time.sleep(0.5)
            elif abs(diffAngle) < 40:
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

