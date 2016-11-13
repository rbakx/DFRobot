#!/usr/bin/python

import time
import re
import json
import base64
import own_util
import secret

# Global constants
# hints are the phrases which are likely to be spoken. They are used to improve speech recognition.
hints = ["james", "alarm", "at", "date", "time", "lights", "on", "off", "demonstration", "news", "netherlands", "local", "weather", "radio", "hits", "salsa", "christmas"]


# Set microphone capturing volume and gain control.
# To do this we have to find out which card is the capturing device with 'arecord -l'.
# Suppose the capturing card is 'card 1', then its capabilities can be listed with 'amixer --card 1 contents'.
# These capabilities can differ per capturing device.
# This will show the numid's of its interfaces. Look for the 'Mic Capture Volume' which has for example numid=3.
# The microphone capturing volume can now be set with 'amixer -c 1 cset numid=3 16' which will set
# the capturing volume to 16.
# The microphone Auto Gain Control can be switched off with 'amixer -c 1 cset numid=4 0'.
stdOutAndErr = own_util.runShellCommandWait('amixer -c 1 cset numid=3 16')
stdOutAndErr = own_util.runShellCommandWait('amixer -c 1 cset numid=4 0')


# Converts a text containing a time indication in words or in digits to a uniform (hours,minutes) tuple.
# It supports the formats of multiple STT engines.
def textToHoursAndMinutes(text, format):
    if format == 'Google':
        # Below the regular expression to deal with different time formats which the Google Speech To Text service can return.
        # Formats that can be handled are like: '23:15', 'zero 0 7', '0:07', '0 0 7', 'zero3zero' etc.
        m = re.search('alarm at ((?:[0-9]|zero)(?:| )(?:[0-9]|zero){0,1})[^0-9]*((?:[0-9]|zero)(?:| )(?:[0-9]|zero))$', text, re.IGNORECASE)
        if m and m.group(1) and m.group(2) and m.group(1) != "" and m.group(2) != "":  # be safe
            hours = m.group(1).replace(" ", "").replace("zero", "0")  # Remove spaces and replace "zero" with "0".
            minutes = m.group(2).replace(" ", "").replace("zero", "0")  # Remove spaces and replace "zero" with "0".
            hoursStr = str(hours)
            minutesStr = str(minutes)
        else:
            (hoursStr,minutesStr) = ("invalid","invalid")

    elif format == 'Ibm':
        numbers = {
            'zero':0,
            'one':1,
            'two':2,
            'three':3,
            'four':4,
            'five':5,
            'six':6,
            'seven':7,
            'eight':8,
            'nine':9,
            'ten':10,
            'eleven':11,
            'twelve':12,
            'thirteen':13,
            'fourteen':14,
            'fifteen':15,
            'sixteen':16,
            'seventeen':17,
            'eighteen':18,
            'nineteen':19,
            'twenty':20,
            'thirty':30,
            'fourty':40,
            'fifty':50,
        }
        # Below the regular expression to deal with different time formats which the Ibm Speech To Text service can return.
        # Formats that can be handled are like: 'twelve nineteen', 'eight thirty five', 'eight three five', 'five zero one', 'zero zero seven', 'twenty three twenty five' etc.
        m = re.search('alarm at ([^\s]+)\s+([^\s]+)(?:|\s+([^\s]+)(?:|\s+([^\s]+)))\s*$', text, re.IGNORECASE)
        if m and m.group(1) and m.group(2) and m.group(1) in numbers and m.group(2) in numbers:  # be safe
            hours = numbers[m.group(1)]
            minutes = numbers[m.group(2)]
            if minutes >=1 and minutes <=3:
                hours = hours + minutes
                minutes = 0
            if m.group(3) and m.group(3) in numbers:
                minutes = minutes + numbers[m.group(3)]
            if m.group(4) and m.group(4) in numbers:
                minutes = minutes + numbers[m.group(4)]
            hoursStr = str(hours)
            minutesStr = str(minutes)
        else:
            (hoursStr,minutesStr) = ("invalid","invalid")
    return (hoursStr,minutesStr)


# Records speech from the microphone and translates this into a (text,intent,value) tuple.
# It supports the formats of multiple STT engines.
def speechToIntent(sttEngine):
    confidence = ""
    text = ""
    intent = ""
    value = None
    if sttEngine == "Google" or sttEngine == "Ibm":
        # Turn on and off light to indicate when the robot is listening.
        own_util.switchLight(True)
        stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -r 16000 -c 1 -f S16_LE -t wav | avconv -i pipe:0 -acodec flac -b: 128k /tmp/file.flac -y')
        own_util.switchLight(False)
        if sttEngine == "Google":
            with open("/tmp/file.flac", 'rb') as speech:
                speech_content = base64.b64encode(speech.read())
            payload = {
                "config": {
                    "encoding":"FLAC",
                    "sampleRate": 16000,
                    "languageCode": "en-US",
                    "speechContext": {
                        "phrases": hints
                    }
                },
                "audio": {
                    "content": speech_content.decode("UTF-8")
                }
            }
            jsonData=json.dumps(payload)
            stdOutAndErr = own_util.runShellCommandWait('curl -s -X POST -H "Content-Type: application/json" --data-binary \'' + jsonData + '\' "https://speech.googleapis.com/v1beta1/speech:syncrecognize?key=' + secret.SpeechToTextGoogleCloudApiKey + '"')
            # Now stdOutAndErr contains the JSON response from the STT engine.
            print stdOutAndErr
            decoded = json.loads(stdOutAndErr)
            try:
                confidence = decoded["results"][0]["alternatives"][0]["confidence"]  # not a string but a float
            except Exception,e:
                print "json exception: " + str(e)
                pass
            try:
                # Use encode() to convert the Unicode strings contained in JSON to ASCII.
                text = decoded["results"][0]["alternatives"][0]["transcript"].encode('ascii', 'ignore')
            except Exception,e:
                print "json exception: " + str(e)
                pass

        elif sttEngine == "Ibm":
            stdOutAndErr = own_util.runShellCommandWait('curl -s -u ' + secret.SpeechToTextIbmUsernamePassword + ' --header "content-type: audio/flac" --data-binary @"/tmp/file.flac" "https://stream.watsonplatform.net/speech-to-text/api/v1/recognize"')
            # Now stdOutAndErr contains the JSON response from the STT engine.
            print stdOutAndErr
            decoded = json.loads(stdOutAndErr)
            try:
                confidence = decoded["results"][0]["alternatives"][0]["confidence"]  # not a string but a float
            except Exception,e:
                print "json exception: " + str(e)
                pass
            try:
                # Use encode() to convert the Unicode strings contained in JSON to ASCII.
                text = decoded["results"][0]["alternatives"][0]["transcript"].encode('ascii', 'ignore')
            except Exception,e:
                print "json exception: " + str(e)
                pass

        # Now text contains the text as received from the STT engine.
        # All voice commands have to start with 'James'.
        m = re.search('james (.*)', text, re.IGNORECASE)
        if m and m.group(1) and m.group(1) != "":  # be safe
            text = m.group(1).strip()  # Use strip() to remove leading and trailing whitespaces if any.
        else:
            # Return only text and empty intent and value to indicate the voice command is invalid.
            return (text,intent,value)
            
        # 'text' now containes the voice command without 'James'.
        # Get intent and value.
        if re.search('(?:volume|vol).*', text, re.IGNORECASE):
            m = re.search('(?:volume|vol) ([0-9]|10)$', text, re.IGNORECASE)
            if m and m.group(1) and m.group(1) != "":  # be safe
                intent = "volume"
                value = m.group(1)
            else:
                intent = "volume"
                value = "invalid"
        elif re.search('alarm at.*', text, re.IGNORECASE):
            (hours,minutes) = textToHoursAndMinutes(text, sttEngine)
            intent = "alarm"
            value = (hours,minutes)
        elif re.search('alarm$', text, re.IGNORECASE):
            intent = "alarm"
            value = None
        elif re.search('date$|time$', text, re.IGNORECASE):
            intent = "time"
            value = None
        elif re.search('lights on$', text, re.IGNORECASE):
            intent = "light"
            value = "on"
        elif re.search('lights off$', text, re.IGNORECASE):
            intent = "light"
            value = "off"
        elif re.search('demo$', text, re.IGNORECASE):
            intent = "demo"
            value = "start"
        elif re.search('stop$', text, re.IGNORECASE):
            intent = "demo"
            value = "stop"
        elif re.search('news$', text, re.IGNORECASE):
            intent = "news"
            value = "world"
        elif re.search('news netherlands$', text, re.IGNORECASE):
            intent = "news"
            value = "netherlands"
        elif re.search('news local$', text, re.IGNORECASE):
            intent = "news"
            value = "eindhoven"
        elif re.search('weather$', text, re.IGNORECASE):
            intent = "weather"
            value = None
        elif re.search('radio hits$', text, re.IGNORECASE):
            intent = "radio"
            value = "hits"
        elif re.search('radio salsa$', text, re.IGNORECASE):
            intent = "radio"
            value = "salsa"
        elif re.search('radio christmas$', text, re.IGNORECASE):
            intent = "radio"
            value = "christmas"
        elif text != "":
            intent = "query"
            value = text

    elif sttEngine == "WitAi":
        # Turn on and off light to indicate when the robot is listening.
        own_util.switchLight(True)
        stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -r 16000 -c 1 -f S16_LE -t wav | avconv -i pipe:0 -acodec mp3 -b: 128k /tmp/file.mp3 -y')
        own_util.switchLight(False)
        stdOutAndErr = own_util.runShellCommandWait('curl -s -X POST --header "Content-Type: audio/mpeg3" --header "Authorization: Bearer ' + secret.WitAiToken + '" --data-binary @"/tmp/file.mp3" "https://api.wit.ai/speech?v=20141022"')
        # Now stdOutAndErr contains the JSON response from the STT engine.
        print stdOutAndErr
        decoded = json.loads(stdOutAndErr)
        try:
            confidence = decoded["outcomes"][0]["confidence"]  # not a string but a float
        except Exception,e:
            print "json exception: " + str(e)
            pass
        try:
            # Use encode() to convert the Unicode strings contained in JSON to ASCII.
            text = decoded["outcomes"][0]["_text"].encode('ascii', 'ignore')
        except Exception,e:
            print "json exception: " + str(e)
            pass
        try:
            # Use encode() to convert the Unicode strings contained in JSON to ASCII.
            intent = decoded["outcomes"][0]["intent"].encode('ascii', 'ignore')
        except Exception,e:
            print "json exception: " + str(e)
            pass
        
        # Now text contains the text as received from the STT engine.
        # All voice commands have to start with 'James'.
        m = re.search('james (.*)', text, re.IGNORECASE)
        if m and m.group(1) and m.group(1) != "":  # be safe
            text = m.group(1).strip()  # Use strip() to remove leading and trailing whitespaces if any.
        else:
            # Return only text and empty intent and value to indicate the voice command is invalid.
            intent = ""
            value = None
            return (text,intent,value)
        
        # If intent is 'alarm', get the value of the time entity.
        if intent == "alarm":
            try:
                # Use encode() to convert the Unicode strings contained in JSON to ASCII.
                value = decoded["outcomes"][0]["entities"]["datetime"][0]["value"].encode('ascii', 'ignore')
            except Exception,e:
                print "json exception: " + str(e)
                pass
            # Reformat time to a tuple (hours,minutes) so it can be used to set the alarm.
            m = re.search('.*?([0-9]+):([0-9]+).*', value, re.IGNORECASE)
            if m and m.group(1) and m.group(2) and m.group(1) != "" and m.group(2) != "":  # be safe
                value = (m.group(1),m.group(2))
            else:
                value = None
        # If intent is 'query' then the text should be passed to a knowledge engine, so put it in 'value'.
        elif intent == "query":
            value = text
        
    return (text,intent,value)


print 'START'
(text,intent,value) = speechToIntent("Google")
print 'END'

print "text, intent, value: " + str(text) + ", " + str(intent) + ", " + str(value)

