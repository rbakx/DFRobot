#!/usr/bin/python
# This script is created to be able to run it as root,
# which is required to control the GPIO pins.
import sys
import argparse
import RPi.GPIO as GPIO ## Import GPIO library
import time
import own_util


# Global constants
LOUDSPEAKER_POWER_PIN = 4
US_PIN_TRIG = [12,16,20,21]
US_PIN_ECHO = [6,13,19,26]


def initGpio():
    # Modify ownership an access permissions so GPIO can be accessed without being root.
    stdOutAndErr = own_util.runShellCommandWait('sudo chown root.gpio /dev/gpiomem')
    stdOutAndErr = own_util.runShellCommandWait('sudo chmod g+rw /dev/gpiomem')
    # Switch off GPIO warnings to prevent the 'RuntimeWarning: This channel is already in use' warning.
    # This warning occurs when multiple GPIO scripts are running and also when one GPIO script is called
    # multiple times. Because this script runs multiple times we disable the warning.
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM) # Use board pin numbering
    GPIO.setup(LOUDSPEAKER_POWER_PIN, GPIO.OUT) # Setup GPIO Pin LOUDSPEAKER_POWER_PIN to OUT.
    for triggerPin in US_PIN_TRIG:
        GPIO.setup(triggerPin, GPIO.OUT)        # Set trigger pin as GPIO out
    for echoPin in US_PIN_ECHO:
        GPIO.setup(echoPin, GPIO.IN)            # Set echo pin as GPIO in


# Gets the distance in cm using the ultrasonic sensor.
# Returns 0 if an invalid value is measured.
def getUsSensorDistance(UsSensorId):
    GPIO.output(US_PIN_TRIG[UsSensorId], False)            # Set triggerpin to LOW
    GPIO.output(US_PIN_TRIG[UsSensorId], True)             # Set triggerpin to HIGH
    time.sleep(0.00001)                                    # Delay of 0.00001 seconds
    GPIO.output(US_PIN_TRIG[UsSensorId], False)            # Set triggerpin to LOW

    # Use waitTime as a guard to make sure this loop ends.
    waitTime = 0
    startTime = time.time()
    while GPIO.input(US_PIN_ECHO[UsSensorId])==0 and waitTime < 0.001:  # waitTime should be around 0.0004
        pulse_start = time.time()            # Saves the last known time of LOW pulse
        waitTime = pulse_start - startTime
    if waitTime == 0 or waitTime >= 0.001:
        return 0

    # Use waitTime as a guard to make sure this loop ends.
    waitTime = 0
    startTime = time.time()
    while GPIO.input(US_PIN_ECHO[UsSensorId])==1 and waitTime < 0.02: # At 3.5 meter waitTime is about 0.02
        pulse_end = time.time()              # Saves the last known time of HIGH pulse
        waitTime = pulse_end - startTime
    if waitTime == 0 or waitTime >= 0.02:
        return 0

    pulse_duration = pulse_end - pulse_start # Get pulse duration to a variable

    distance = pulse_duration * 17150        # Multiply pulse duration by 17150 to get distance in cm
    distance = round(distance, 2)            # Round to two decimal points
    # Check if the measured distance makes sense, alse return 0.
    if distance < 3.0 or distance > 300.0:
        distance = 0
    return distance


# Switch on the loudspeaker.
def switchOnLoudspeaker():
    GPIO.output(LOUDSPEAKER_POWER_PIN, True)  # Turn on loudspeaker.


# Switch off the loudspeaker.
def switchOffLoudspeaker():
    GPIO.output(LOUDSPEAKER_POWER_PIN, False) # Turn on loudspeaker.


# Get power status of the loudspeaker. Returns 1 if power is on, else 0.
def getStatusLoudspeaker():
    return GPIO.input(LOUDSPEAKER_POWER_PIN) # Return power status of loudspeaker.


# The code below is used when this script is run as a separate python script.
# This is used to turn on or of the loadspeaker from a system thread (using own_util.runShellCommandNowait) in combination with playing speech or musoc.
if __name__ == '__main__':
    # Handle arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument('--loudspeaker', choices = ['on','off'])
    args = parser.parse_args()
    
    # Modify ownership an access permissions so GPIO can be accessed without being root.
    stdOutAndErr = own_util.runShellCommandWait('sudo chown root.gpio /dev/gpiomem')
    stdOutAndErr = own_util.runShellCommandWait('sudo chmod g+rw /dev/gpiomem')
    # Switch off GPIO warnings to prevent the 'RuntimeWarning: This channel is already in use' warning.
    # This warning occurs when multiple GPIO scripts are running and also when one GPIO script is called
    # multiple times. Because this script runs multiple times we disable the warning.
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM) # Use board pin numbering

    # Loudspeaker GPIO pin to switch loudspeaker on or off.
    GPIO.setup(LOUDSPEAKER_POWER_PIN, GPIO.OUT) # Setup GPIO Pin LOUDSPEAKER_POWER_PIN to OUT.
    if args.loudspeaker == 'on':
        GPIO.output(LOUDSPEAKER_POWER_PIN,True) # Turn on loudspeaker.
    elif args.loudspeaker == 'off':
        GPIO.output(LOUDSPEAKER_POWER_PIN,False) # Turn off loudspeaker.
