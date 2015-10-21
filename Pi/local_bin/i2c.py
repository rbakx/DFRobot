#!/usr/bin/python

import thread
import RPi.GPIO as GPIO
import smbus
import logging

# Global variables
globI2cLock = None
# globI2cDelay is the minimum time needed between two I2C commands to give the Arduino time to handle the commands.
# The Arduino does not buffer the I2C commands. If the Raspberry issues an I2C command too fast for the Arduino,
# it will overwrite the previous command on the Arduino.
globI2cDelay = 0.1


def createI2cLock():
    global globI2cLock
    # Create lock for i2c communication; only one thread may take the i2c bus.
    if globI2cLock == None:
        globI2cLock = thread.allocate_lock()


def get_smbus():
    try:
        rev = GPIO.RPI_REVISION
        if rev == 2 or rev == 3:
            bus = smbus.SMBus(1)
        else:
            bus = smbus.SMBus(0)
        return bus
    except Exception,e:
        logging.getLogger("MyLog").info('I2C get_smbus exception: ' + str(e))
        return None

def read_byte(slaveAddr, adr):
    try:
        bus = get_smbus()
        byte = bus.read_byte_data(slaveAddr, adr)
        return byte
    except Exception,e:
        logging.getLogger("MyLog").info('I2C read_byte exception: ' + str(e))
        return 0

def read_word(slaveAddr, adr):
    try:
        bus = get_smbus()
        high = bus.read_byte_data(slaveAddr, adr)
        low = bus.read_byte_data(slaveAddr, adr+1)
        val = (high << 8) + low
        return val
    except Exception,e:
        logging.getLogger("MyLog").info('I2C read_word exception: ' + str(e))
        return 0

def read_word_2c(slaveAddr, adr):
    try:
        val = read_word(slaveAddr, adr)
        if (val >= 0x8000):
            return -((65535 - val) + 1)
        else:
            return val
    except Exception,e:
        logging.getLogger("MyLog").info('I2C read_word_2c exception: ' + str(e))
        return 0

def write_byte(slaveAddr, adr, value):
    try:
        bus = get_smbus()
        bus.write_byte_data(slaveAddr, adr, value)
    except Exception,e:
        logging.getLogger("MyLog").info('I2C write_byte exception: ' + str(e))
