#!/usr/bin/python

import RPi.GPIO as GPIO
import smbus
import time
import math
import subprocess
import i2c
import own_util


# Global variables.
slaveAddressCompass = 0x1e


def readCompass(debug = False):
    # Create i2c lock if it does not exist yet.
    i2c.createI2cLock()
    # Lock  i2c communication for this thread.
    i2c.globI2cLock.acquire()
    
    i2c.write_byte(slaveAddressCompass, 0, 0b01110000) # Set to 8 samples @ 15Hz.
    i2c.write_byte(slaveAddressCompass, 1, 0b00100000) # 1.3 gain LSb / Gauss 1090 (default).
    i2c.write_byte(slaveAddressCompass, 2, 0b00000000) # Continuous-Measurement Mode.
    
    time.sleep(0.006)  # Wait 6 ms as specified in data sheet.

    x_out_raw = i2c.read_word_2c(slaveAddressCompass, 3)
    y_out_raw = i2c.read_word_2c(slaveAddressCompass, 7)
    z_out_raw = i2c.read_word_2c(slaveAddressCompass, 5)


    # Calibration procedure:
    # Run calibrateCompass() and below fill in the resulting values.
    # Run testCompass() and position the robot such that raw degrees equals 0.
    # Then physically rotate the robot 180 degrees and fill in raw degrees in rawDegreesAt180Degrees below.
    # This calibration will result in x_out and y_out varying between -200 and +200.
    # Because the HMC5883L is not exactly linear or mounted exactly horizontal,
    # we apply an extra correction (offsetCorrectionAt180Degrees) at 180 degrees to straigten the curve.
    x_factor = 0.97
    x_offset = -24.70
    y_factor = 0.90
    y_offset = 30.77
    rawDegreesAt180Degrees = 199.87
    
    offsetCorrectionAt180Degrees = 180.0 - rawDegreesAt180Degrees
    
    # When supplying a 'True' as parameter to this function the raw X Y Z data and the corrected data will be printed.
    # From measurements of these raw values it shows that we have to compensate quite a bit with a gain and offset.
    # This is because the HMC5883L is mounted on the robot and is very sensitive to surrounding metal and fields.
    # We apply a scale and ofset to both x_out and y_out so the range will be [-200 .. 200]
    x_out = x_out_raw * x_factor + x_offset
    y_out = y_out_raw * y_factor + y_offset

    bearing  = math.atan2(y_out, x_out)
    if (bearing < 0):
        bearing += 2 * math.pi
    degrees_raw = math.degrees(bearing)
    # Correct for offset at 180 degrees.
    if degrees_raw < 180:
        degrees = degrees_raw + (degrees_raw / 180.0) * offsetCorrectionAt180Degrees
    else:
        degrees = degrees_raw + (360.0 - degrees_raw) / 180.0 * offsetCorrectionAt180Degrees

    # Delay for i2c communication.
    time.sleep(i2c.globI2cDelay)

    # Release i2c communication for this thread.
    i2c.globI2cLock.release()

    if debug:
        return x_out_raw, y_out_raw, z_out_raw, x_out, y_out, degrees_raw, degrees
    else:
        return degrees

# The below function is to test the compass.
def testCompass():
    while True:
        (x_out_raw, y_out_raw, z_out_raw, x_out, y_out, raw_degrees, degrees) = readCompass(True)
        print 'raw X Y Z and raw degrees:', x_out_raw, y_out_raw, z_out_raw, round(raw_degrees,2)
        print 'corrected X Y and degrees:', int(x_out), int(y_out), round(degrees,2)
        time.sleep(0.5)

# The below function is to find the calibration values for the compass.
def calibrateCompass():
    x_out_raw_min = float("infinity")
    x_out_raw_max = float("-infinity")
    y_out_raw_min = float("infinity")
    y_out_raw_max = float("-infinity")
    # Turn around a few times to make sure all angles are measured.
    for i in range(300):
        (x_out_raw, y_out_raw, z_out_raw, x_out, y_out, raw_degrees, degrees) = readCompass(True)
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
    print 'x_factor =', round(x_factor,2)
    print 'x_offset =', round(x_offset,2)
    print 'y_factor =', round(y_factor,2)
    print 'y_offset =', round(y_offset,2)

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

