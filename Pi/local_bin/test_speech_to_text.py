#!/usr/bin/python

import time
import re
import own_util
import secret


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


def speechToIntent(speechEngine):
    text = ""
    intent = ""
    value = None
    if speechEngine == "Google" or speechEngine == "Ibm":
        if speechEngine == "Google":
            # Turn on and off light to indicate when the robot is listening.
            own_util.switchLight(True)
            stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -r 16000 -c 1 -f S16_LE -t wav | avconv -i pipe:0 -acodec flac -b: 128k /tmp/file.flac -y')
            own_util.switchLight(False)

            stdOutAndErr = own_util.runShellCommandWait('wget -q --post-file /tmp/file.flac --header="Content-Type: audio/x-flac; rate=16000" -O - "http://www.google.com/speech-api/v2/recognize?client=chromium&lang=en_US&key=' + secret.SpeechToTextGoogleApiKey + '"')
            print stdOutAndErr
            # Now stdOutAndErr is a multiline string containing possible transcripts with confidence levels.
            # First get confidence and only continue if confidence is high enough.
            # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
            m = re.search('.*?"confidence":((?:[0-9]|\.)+).*', stdOutAndErr, re.IGNORECASE | re.DOTALL)
            if m and m.group(1) and m.group(1) != "":  # be safe
                try:
                    confidence = float(m.group(1))
                    print "confidence:", confidence
                except ValueError:
                    confidence = 0.0
                if confidence < 0.1:
                    # Not enough confidence, return with empty result.
                    return (text,intent,value)
            else:
                # Not enough confidence, return with empty result.
                return (text,intent,value)
            # The transcript with the highest confidence is listed first, so we filter out that one.
            m = re.search('.*?"transcript":"([^"]+).*', stdOutAndErr, re.IGNORECASE | re.DOTALL)
            if m and m.group(1) and m.group(1) != "":  # be safe
                text = m.group(1).strip()
                # Now text contains the text as received by the speech service.
                # All voice commands have to start with 'James'.
                m = re.search('james (.*)', text, re.IGNORECASE)
                if m and m.group(1) and m.group(1) != "":  # be safe
                    text = m.group(1)

        elif speechEngine == "Ibm":
            # Turn on and off light to indicate when the robot is listening.
            own_util.switchLight(True)
            stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -r 16000 -c 1 -f S16_LE -t wav | avconv -i pipe:0 -acodec flac -b: 128k /tmp/file.flac -y')
            own_util.switchLight(False)

            stdOutAndErr = own_util.runShellCommandWait('curl -u ' + secret.SpeechToTextIbmUsernamePassword + ' -H "content-type: audio/flac" --data-binary @"/tmp/file.flac" "https://stream.watsonplatform.net/speech-to-text/api/v1/recognize"')
            print stdOutAndErr
            # Now stdOutAndErr is a multiline string containing possible transcripts with confidence levels.
            # First get confidence and only continue if confidence is high enough.
            # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
            m = re.search('.*?"confidence": ((?:[0-9]|\.)+).*', stdOutAndErr, re.IGNORECASE | re.DOTALL)
            if m and m.group(1) and m.group(1) != "":  # be safe
                try:
                    confidence = float(m.group(1))
                    print "confidence:", confidence
                except ValueError:
                    confidence = 0.0
                if confidence < 0.1:
                    # Not enough confidence, return with empty result.
                    return (text,intent,value)
            else:
                # Not enough confidence, return with empty result.
                return (text,intent,value)
            # The transcript with the highest confidence is listed first, so we filter out that one.
            m = re.search('.*?"transcript": "([^"]+).*', stdOutAndErr, re.IGNORECASE | re.DOTALL)
            if m and m.group(1) and m.group(1) != "":  # be safe
                text = m.group(1).strip()
                # Now text contains the text as received by the speech service.
                # All voice commands have to start with 'James'.
                m = re.search('james (.*)', text, re.IGNORECASE)
                if m and m.group(1) and m.group(1) != "":  # be safe
                    text = m.group(1)
            
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
            (hours,minutes) = textToHoursAndMinutes(text, speechEngine)
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
        else:
            intent = "query"
            value = text

    elif speechEngine == "WitAi":
        # Turn on and off light to indicate when the robot is listening.
        own_util.switchLight(True)
        stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -r 16000 -c 1 -f S16_LE -t wav | avconv -i pipe:0 -acodec mp3 -b: 128k /tmp/file.mp3 -y')
        own_util.switchLight(False)

        stdOutAndErr = own_util.runShellCommandWait('curl -XPOST "https://api.wit.ai/speech?v=20141022" -i -L -H "Authorization: Bearer ES2VFF3RZNQ2BTCW3CHWD7FTHOVA3HYW" -H "Content-Type: audio/mpeg3" --data-binary @"/tmp/file.mp3"')
        print stdOutAndErr
        # Now stdOutAndErr is a multiline string containing text, intents and values.
        # First get confidence and only continue if confidence is high enough.
        # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
        m = re.search('.*?"confidence" : ((?:[0-9]|\.)+).*', stdOutAndErr, re.IGNORECASE | re.DOTALL)
        if m and m.group(1) and m.group(1) != "":  # be safe
            try:
                confidence = float(m.group(1))
                print "confidence:", confidence
            except ValueError:
                confidence = 0.0
            if confidence < 0.1:
                # Not enough confidence, return with empty result.
                return (text,intent,value)
        else:
            # Not enough confidence, return with empty result.
            return (text,intent,value)
        # Get text.
        m = re.search('.*?"_text" : "([^"]+).*', stdOutAndErr, re.IGNORECASE | re.DOTALL)
        if m and m.group(1) and m.group(1) != "":  # be safe
            text = m.group(1).strip()
            # Now text contains the text as rece ived by the speech service.
            # All voice commands have to start with 'James'.
            m = re.search('james (.*)', text, re.IGNORECASE)
            if m and m.group(1) and m.group(1) != "":  # be safe
                text = m.group(1)
                # 'text' now containes the voice command without 'James'.
                # Get intent.
                m = re.search('.*?"intent" : "([^"]+).*', stdOutAndErr, re.IGNORECASE | re.DOTALL)
                if m and m.group(1) and m.group(1) != "":  # be safe
                    intent = m.group(1).strip()
                    # Get value.
                    m = re.search('.*?"value" : "([^"]+).*', stdOutAndErr, re.IGNORECASE | re.DOTALL)
                    if m and m.group(1) and m.group(1) != "":  # be safe
                        value = m.group(1).strip()
                        if intent == "alarm":
                            # If intent = "alarm" then value must be a time.
                            # Reformat time to a tuple (hours,minutes) so it can be used to set the alarm.
                            m = re.search('.*?([0-9]+):([0-9]+).*', value, re.IGNORECASE)
                            if m and m.group(1) and m.group(2) and m.group(1) != "" and m.group(2) != "":  # be safe
                                value = (m.group(1),m.group(2))
                            else:
                                value = ""
                    # If intent is "james" then the command should be passed to a knowledge engine.
                    if intent == "query":
                        value = text

    return (text,intent,value)


print 'START'
(text,intent,value) = speechToIntent("Google")
print 'END'

print "text, intent, value: " + str(text) + ", " + str(intent) + ", " + str(value)

