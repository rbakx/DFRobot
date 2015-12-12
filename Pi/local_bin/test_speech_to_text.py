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

def speechToText(service):
    if service == "Google":
        # Turn on and off light to indicate when the robot is listening.
        own_util.switchLight(True)
        stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -r 16000 -c 1 -f S16_LE -t wav | ffmpeg -loglevel panic -y -i - -ar 16000 -acodec flac /tmp/file.flac')
        own_util.switchLight(False)

        stdOutAndErr = own_util.runShellCommandWait('wget -q --post-file /tmp/file.flac --header="Content-Type: audio/x-flac; rate=16000" -O - "http://www.google.com/speech-api/v2/recognize?client=chromium&lang=en_US&key=' + secret.SpeechToTextGoogleApiKey + '"')
        print stdOutAndErr
        # Now stdOutAndErr is a multiline string containing possible transcripts with confidence levels.
        # The one with the highest confidence is listed first, so we filter out that one.

        # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
        regex = re.compile('.*?"transcript":"([^"]+).*', re.DOTALL)
        match = regex.match(stdOutAndErr)
        if match is not None:
            text = match.group(1)
        else:
            text = ""

    elif service == "Ibm":
        # Turn on and off light to indicate when the robot is listening.
        own_util.switchLight(True)
        stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -r 16000 -c 1 -f S16_LE -t wav | ffmpeg -loglevel panic -y -i - -ar 16000 -acodec flac /tmp/file.flac')
        own_util.switchLight(False)

        stdOutAndErr = own_util.runShellCommandWait('curl -u ' + secret.SpeechToTextIbmUsernamePassword + ' -H "content-type: audio/flac" --data-binary @"/tmp/file.flac" "https://stream.watsonplatform.net/speech-to-text/api/v1/recognize"')
        print stdOutAndErr
        # Now stdOutAndErr is a multiline string containing possible transcripts with confidence levels.
        # The one with the highest confidence is listed first, so we filter out that one.

        # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
        regex = re.compile('.*?"transcript": "([^"]+).*', re.DOTALL)
        match = regex.match(stdOutAndErr)
        if match is not None:
            text = match.group(1)
        else:
            text = ""

    # Remove leading and trailing whitespaces and return text.
    return text.strip()


print 'START'
text = speechToText("Google")
print 'END'

print "text:", text

