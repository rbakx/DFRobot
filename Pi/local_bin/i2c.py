#!/usr/bin/python

import thread
import RPi.GPIO as GPIO
import smbus

# Global variables
globI2cLock = None
globI2cDelay = 0.1


def createI2cLock():
    global globI2cLock
    # Create lock for i2c communication; only one thread may take the i2c bus.
    if globI2cLock == None:
        globI2cLock = thread.allocate_lock()


def get_smbus():
    rev = GPIO.RPI_REVISION
    if rev == 2 or rev == 3:
        bus = smbus.SMBus(1)
    else:
        bus = smbus.SMBus(0)
    return bus

def read_byte(slaveAddr, adr):
    bus = get_smbus()
    return bus.read_byte_data(slaveAddr, adr)

def read_word(slaveAddr, adr):
    bus = get_smbus()
    high = bus.read_byte_data(slaveAddr, adr)
    low = bus.read_byte_data(slaveAddr, adr+1)
    val = (high << 8) + low
    return val

def read_word_2c(slaveAddr, adr):
    val = read_word(slaveAddr, adr)
    if (val >= 0x8000):
        return -((65535 - val) + 1)
    else:
        return val

def write_byte(slaveAddr, adr, value):
    bus = get_smbus()
    bus.write_byte_data(slaveAddr, adr, value)
