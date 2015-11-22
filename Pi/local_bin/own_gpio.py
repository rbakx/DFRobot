#!/usr/bin/python
# This script is created to be able to run it as root,
# which is required to control the GPIO pins.

import sys
import argparse
import RPi.GPIO as GPIO ## Import GPIO library

# Handle arguments.
parser = argparse.ArgumentParser()
parser.add_argument('--loudspeaker')
args = parser.parse_args()

GPIO.setmode(GPIO.BCM) ## Use board pin numbering
# Loudspeaker GPIO pin to switch loudspeaker on or off.
GPIO.setup(4, GPIO.OUT) # Setup GPIO Pin 4 to OUT.
if args.loudspeaker == 'on':
    GPIO.output(4,True) # Turn on loudspeaker.
if args.loudspeaker == 'off':
    GPIO.output(4,False) # Turn off loudspeaker.
