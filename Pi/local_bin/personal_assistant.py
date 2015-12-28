#!/usr/bin/python
import thread
import time
import math
import re
import json
import datetime
import alsaaudio, audioop
from scipy import signal
import struct
import numpy as np
import wolframalpha
import feedparser
import logging
import own_util
import secret

# Global constants
SampleRate = 16000
NyquistFrequency = 0.5 * SampleRate
B, A = signal.butter(5, [4400.0/NyquistFrequency, 4600.0/NyquistFrequency], btype='band')
FirCoeff = signal.firwin(29, 4000.0/NyquistFrequency, pass_zero=False)

# Global variables
globInteractive = False
globDoHomeRun = False
globCmd = ''


# This function filters an audioBuffer which is a Python string of nsamples shorts.
# It returns the filtered signal as a Python string of nsamples shorts.
# The string type is used to serialize data in order to send it over a serial line.
def butterBandpassFilter(audioBuffer, nsamples):
    global SampleRate, NyquistFrequency, B, A
    floatArray = struct.unpack('h'*nsamples,audioBuffer)
    floatArrayFiltered = signal.lfilter(B, A, floatArray)
    # Make sure all values fit in a short to prevent errors in struct.pack().
    np.clip(floatArrayFiltered, -32768, 32767, floatArrayFiltered)
    return struct.pack('h'*nsamples,*floatArrayFiltered)


# This function filters an audioBuffer which is a Python string of nsamples shorts.
# It returns the filtered signal as a Python string of nsamples shorts.
# The string type is used to serialize data in order to send it over a serial line.
def firHighpassFilter(audioBuffer, nsamples):
    global SampleRate, NyquistFrequency, FirCoeff
    floatArray = struct.unpack('h'*nsamples,audioBuffer)
    floatArrayFiltered = signal.lfilter(FirCoeff, 1.0, floatArray)
    # Make sure all values fit in a short to prevent errors in struct.pack().
    np.clip(floatArrayFiltered, -32768, 32767, floatArrayFiltered)
    return struct.pack('h'*nsamples,*floatArrayFiltered)


def checkClaps(p1, p2, p3, p4, p5):
    minClapRatio = 8.0
    # Prevent division by zero.
    p1 = max(p1, 1.0)
    p2 = max(p2, 1.0)
    p3 = max(p3, 1.0)
    p4 = max(p4, 1.0)
    p5 = max(p5, 1.0)
    if p2 / p1 > minClapRatio and p2 / p3 > minClapRatio and p4 / p3 > minClapRatio and p4 / p5 > minClapRatio:
        return True
    else:
        return False


def checkSilence(p1, p2, p3, p4, p5):
    maxSilenceRatio = 3.0
    SilenceThreshold = 1000.0
    avg = (p1 + p2 + p3 + p4 + p5) / 5.0
    # Prevent division by zero.
    p1 = max(p1, 1.0)
    p2 = max(p2, 1.0)
    p3 = max(p3, 1.0)
    p4 = max(p4, 1.0)
    p5 = max(p5, 1.0)
    # Silence is True when all powers are below SilenceThreshold or when all powers are about equal.
    if (p1 < SilenceThreshold and p2 < SilenceThreshold and p3 < SilenceThreshold and p4 < SilenceThreshold and p5 < SilenceThreshold) or (abs(p1 - avg) / min(p1, avg) < maxSilenceRatio and abs(p2 - avg) / min(p2, avg) < maxSilenceRatio and abs(p3 - avg) / min(p3, avg) < maxSilenceRatio and abs(p4 - avg) / min(p4, avg) < maxSilenceRatio and abs(p5 - avg) / min(p5, avg) < maxSilenceRatio):
        return True
    else:
        return False


# This function waits for an event like the trigger sound or alarm and returns when the event has occurred.
def waitForEvent():
    global globAlarmStatus, globAlarm
    global SampleRate
    # Constants used in this function.
    PeriodSizeInSamples = 500
    BytesPerSample = 2 # Corresponding to the PCM_FORMAT_S16_LE setting.
    PeriodSizeInBytes = PeriodSizeInSamples * BytesPerSample
    SegmentSizeInBytes = 4 * PeriodSizeInBytes
    FiveSegmentSizeInBytes = 5 * SegmentSizeInBytes
    ClapCountInPeriods = FiveSegmentSizeInBytes / PeriodSizeInBytes
    SilenceCountInPeriods = 1.5 * FiveSegmentSizeInBytes / PeriodSizeInBytes  # the 1.5 because of echoes.
    
    # Open the device in blocking capture mode. During the blocking other threads can run.
    card = 'sysdefault:CARD=Device'
    inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE,alsaaudio.PCM_NORMAL, card)
    
    # Set attributes: mono, SampleRate, 16 bit little endian samples
    inp.setchannels(1)
    inp.setrate(SampleRate)
    inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    
    # The period size sets the period size in samples which is read every blocking read() call.
    # However, currently this setting does not have to seem to have any effect and the period size
    # effectively is always 341. This might be an alsaaudio bug.
    # For the code below it does not really matter.
    inp.setperiodsize(PeriodSizeInSamples)
    
    doContinue1 = True
    doContinue2 = True
    clapCount = 0
    silenceCount = 0
    audioBuffer = ""
    while doContinue1 or doContinue2:
        # Check for Alarm event.
        if globAlarmStatus == 'SET' and datetime.datetime.now().time() > datetime.time(*globAlarm):
            # Indicate alarm and return.
            globAlarmStatus = 'ALARMSET'
            return
        
        # Read PeriodSizeInSamples audio samples from the audio input which is PeriodSizeInBytes bytes.
        # newAudioData will be a sequence of audio samples, stored as a Python string.
        l,newAudioDataUnfiltered = inp.read()
        newAudioData = butterBandpassFilter(newAudioDataUnfiltered, l)
        audioBuffer = audioBuffer + newAudioData
        if len(audioBuffer) >= FiveSegmentSizeInBytes:
            p1 = math.pow(audioop.rms(audioBuffer[0:1*SegmentSizeInBytes], BytesPerSample), 2)
            p2 = math.pow(audioop.rms(audioBuffer[1*SegmentSizeInBytes:2*SegmentSizeInBytes], BytesPerSample), 2)
            p3 = math.pow(audioop.rms(audioBuffer[2*SegmentSizeInBytes:3*SegmentSizeInBytes], BytesPerSample), 2)
            p4 = math.pow(audioop.rms(audioBuffer[3*SegmentSizeInBytes:4*SegmentSizeInBytes], BytesPerSample), 2)
            p5 = math.pow(audioop.rms(audioBuffer[4*SegmentSizeInBytes:5*SegmentSizeInBytes], BytesPerSample), 2)
            audioBuffer = audioBuffer[PeriodSizeInBytes:]
            # The code below will be executed every period or PeriodSizeInSamples samples.
            # With 16 KHz sample rate this means every 31.25 ms.
            # Five powers p1..p5 are available of the last 5 segments.
            # We check if there are first 5 segments with silence,
            # then 5 segments with two claps (with the claps in segment 2 and 4),
            # then 5 segments with silence again.
            if doContinue1:
                # Check if there are 5 segments of silence.
                if checkSilence(p1, p2, p3, p4, p5):
                    # A silence is detected for 5 segments.
                    # Set the clapCount to this value to reserve time for detecting two claps.
                    clapCount = ClapCountInPeriods
                elif clapCount > 0:
                    # There is no silence any more. So two claps have to occur in the next clapCount periods.
                    # As soon as this time is exceeded (clapCount == 0) we start over again.
                    if checkClaps(p1, p2, p3, p4, p5):
                        # Two claps are detected. Start checking for silence again.
                        silenceCount = SilenceCountInPeriods;
                        n = 0
                        doContinue1 = False
                        # Set clapCount to 0 to prevent jumping directly to detecting claps in case of a next iteration.
                        clapCount = 0
                    clapCount = max(clapCount - 1, 0)
            elif doContinue2:
                # Check if there is silence after the two claps.
                if checkSilence(p1, p2, p3, p4, p5):
                    # Trigger sound detected! Return from this function.
                    doContinue2 = False
                else:
                    silenceCount = max(silenceCount - 1, 0)
                    if silenceCount == 0:
                        # No silence detected in tome, so start over again.
                        doContinue1 = True


def initMicrophone():
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


def initLoudspeaker():
    # Set maximum playback volume on 3 mm headphones jack.
    stdOutAndErr = own_util.runShellCommandWait('amixer set PCM -- 100%')


def setVolumeLoudspeaker(volume):
    # Set maximum playback volume on 3 mm headphones jack.
    stdOutAndErr = own_util.runShellCommandWait('amixer set PCM -- ' + volume)


def switchOnLoudspeaker():
    stdOutAndErr = own_util.runShellCommandWait('sudo /usr/local/bin/own_gpio.py --loudspeaker on')


def switchOffLoudspeaker():
    stdOutAndErr = own_util.runShellCommandWait('sudo /usr/local/bin/own_gpio.py --loudspeaker off')


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
            stdOutAndErr = own_util.runShellCommandWait('curl -s -X POST --header "content-type: audio/x-flac; rate=16000;" --data-binary @"/tmp/file.flac" "http://www.google.com/speech-api/v2/recognize?client=chromium&lang=en_US&key=' + secret.SpeechToTextGoogleApiKey + '"')
            # Google always replies with an empty JSON response '{"result":[]}' on the first line.
            # If there is speech, The second line contains the actual JSON result.
            # If there is no speech, there is no second line so we have to check this.
            if len(stdOutAndErr.splitlines()) != 2:
                # Return empty text, intent and value to indicate the voice command is invalid.
                return (text,intent,value)
            stdOutAndErr = stdOutAndErr.splitlines()[1]
            # Now stdOutAndErr contains the JSON response from the STT engine.
            decoded = json.loads(stdOutAndErr)
            try:
                confidence = decoded["result"][0]["alternative"][0]["confidence"]  # not a string but a float
            except Exception,e:
                pass
            try:
                # Use encode() to convert the Unicode strings contained in JSON to ASCII.
                text = decoded["result"][0]["alternative"][0]["transcript"].encode('ascii', 'ignore')
            except Exception,e:
                pass

        elif sttEngine == "Ibm":
            stdOutAndErr = own_util.runShellCommandWait('curl -s -u ' + secret.SpeechToTextIbmUsernamePassword + ' --header "content-type: audio/flac" --data-binary @"/tmp/file.flac" "https://stream.watsonplatform.net/speech-to-text/api/v1/recognize"')
            # Now stdOutAndErr contains the JSON response from the STT engine.
            decoded = json.loads(stdOutAndErr)
            try:
                confidence = decoded["results"][0]["alternatives"][0]["confidence"]  # not a string but a float
            except Exception,e:
                pass
            try:
                # Use encode() to convert the Unicode strings contained in JSON to ASCII.
                text = decoded["results"][0]["alternatives"][0]["transcript"].encode('ascii', 'ignore')
            except Exception,e:
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
        elif re.search('demonstration$', text, re.IGNORECASE):
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
        decoded = json.loads(stdOutAndErr)
        try:
            confidence = decoded["outcomes"][0]["confidence"]  # not a string but a float
        except Exception,e:
            pass
        try:
            # Use encode() to convert the Unicode strings contained in JSON to ASCII.
            text = decoded["outcomes"][0]["_text"].encode('ascii', 'ignore')
        except Exception,e:
            pass
        try:
            # Use encode() to convert the Unicode strings contained in JSON to ASCII.
            intent = decoded["outcomes"][0]["intent"].encode('ascii', 'ignore')
        except Exception,e:
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


def textToSpeech(text, language, speed):
    # Use runShellCommandNowait() to be able to continue and to stop this process if needed.
    # When speech is finished the loudspeaker is turned off.
    own_util.runShellCommandNowait('/usr/bin/mplayer -ao alsa -really-quiet -noconsolecontrols "http://api.voicerss.org/?key=' + secret.VoiceRSSApiKey + '&hl=' + language + '&r=' + speed + '&f=16khz_16bit_mono&src=' + text + '"' + ';sudo /usr/local/bin/own_gpio.py --loudspeaker off')


def query(queryStr):
    client = wolframalpha.Client(secret.WolfRamAlphaAppId)
    res = client.query(queryStr)
    if len(res.pods) > 0:
        response = ""
        pod = res.pods[1]
        if pod.text:
            response = pod.text
        else:
            response = "I have no answer for that"
        # WolframAlpha can return Unicode, so encode response to ASCII.
        response = response.encode('ascii', 'ignore')
        # Remove words between brackets and the brackets as this is less relevant information.
        regex = re.compile('\(.+?\)')
        response = regex.sub('', response)
        # Add space after 'euro' as WolframAlpha returns for example "euro25.25".
        regex = re.compile('euro(?=[0-9])')  # only add space after 'euro' followed by a digit.
        response = regex.sub('euro ', response)
    else:
        response = "Sorry, I am not sure."
    return response


def personalAssistant():
    global globInteractive, globDoHomeRun, globCmd
    global globAlarmStatus, globAlarm
    switchOnLoudspeaker()
    stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')
    switchOffLoudspeaker()
    volumeVoice = '90%' # Volume used for voice responses.
    volumeAlarm = '80%'  # Volume used for alarm.
    volumeMusic = '70%'  # Volume used for music, can be set by voice command.
    globAlarmStatus = ''
    while True:
        try:
            language = 'en-us' # default language
            tmpCmd = ''
            # Wait for an event like the trigger sound or alarm. This contains a sleep to enable other threads to run.
            waitForEvent()
            # Event occurred. An event can be for example two claps to request a servie, two claps to interrupt an action or an alarm.
            # 'eventHandled' is used to check whether the event is handled or not.
            eventHandled = False
            # Check if the previous command is still running. If so, kill it and continue waiting for the next trigger sound.
            # This way it is possible to start a command with two claps and also stop a running command with two claps.
            stdOutAndErr = own_util.runShellCommandWait('sudo killall mplayer')
            if stdOutAndErr == "":
                switchOffLoudspeaker()
                eventHandled = True  # Indicate the event is handled.
            stdOutAndErr = own_util.runShellCommandWait('mpc current')
            if stdOutAndErr != "" and 'error' not in stdOutAndErr:
                # Stop playing music and stop Music Player Daemon service.
                stdOutAndErr = own_util.runShellCommandWait('mpc stop;mpc clear;sudo service mpd stop')
                switchOffLoudspeaker()
                eventHandled = True  # Indicate the event is handled.
            if globAlarmStatus == 'ALARMSET':
                # Switch on loadspeaker, sound the alarm and switch off loudspeaker.
                setVolumeLoudspeaker(volumeVoice)
                switchOnLoudspeaker()
                # Use runShellCommandNowait() to be able to continue and to stop this process if needed.
                # When speech is finished the loudspeaker is turned off.
                setVolumeLoudspeaker(volumeAlarm)
                own_util.runShellCommandNowait('/usr/bin/mplayer /home/pi/Sources/alarm.mp3;sudo /usr/local/bin/own_gpio.py --loudspeaker off')
                globAlarmStatus = ''  # reset alarm
                eventHandled = True   # Indicate the event is handled.
            if globDoHomeRun == True:
                globDoHomeRun = False
                eventHandled = True   # Indicate the event is handled.
            # If event is handled already here, continue to wait for the next event.
            if eventHandled == True:
                continue
            # Speak out greeting.
            setVolumeLoudspeaker(volumeVoice)
            switchOnLoudspeaker()
            stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')

            # Listen and translate speech to text.
            (text,intent,value) = speechToIntent("Google")
            logging.getLogger("MyLog").info('speech to text, intent, value: ' + str(text) + ", " + str(intent) + ", " + str(value))
            response = ''
            # Handle the intent.
            if intent == "volume":
                if value != "invalid":
                    volumeMusic = str(int(value) * 10) + '%'
                    response = 'volume ' + value
                else:
                    response = 'volume not valid'
            elif intent == "alarm":
                if value is None:
                    if globAlarmStatus == 'SET':
                        response = 'alarm set at ' + alarmString
                    else:
                        response = 'alarm not set'
                else:
                    (hours,minutes) = value
                    if hours != "invalid":
                        # 'alarmString' will be a string like "11:15" or "0:07".
                        alarmString = hours + ":" + minutes
                        globAlarm = (int(hours),int(minutes))  # Integer tuple containing hours and minutes.
                        globAlarmStatus = 'SET'
                        response = 'alarm set at ' + alarmString
                    else:
                        globAlarmStatus = ''  # Set off any previous alarm.
                        response = 'alarm not valid'
            elif intent == "time":
                response = "{:%B %d %Y, %H:%M}".format(datetime.datetime.now())
            elif intent == "light":
                if value == "on":
                    tmpCmd = 'light-on'
                    response = 'lights on'
                else:
                    tmpCmd = 'light-off'
                    response = 'lights off'
            elif intent == "demo":
                if value == "start":
                    tmpCmd = 'demo-start'
                    response = 'demo activated'
                    globDoHomeRun = True
                else:
                    tmpCmd = 'demo-stop'
                    response = 'demo stopped'
                    globDoHomeRun = False
            elif intent == "news":
                if value == "world":
                    d = feedparser.parse('http://www.ed.nl/cmlink/1.3280365')
                elif value == "netherlands":
                    d = feedparser.parse('http://www.ed.nl/cmlink/1.3280352')
                else:
                    d = feedparser.parse('http://www.ed.nl/cmlink/1.4419308')
                response = ''
                for post in d.entries[:1000]:  # Restrict to 10 entries.
                    # feedparser can return Unicode strings, so convert to ASCII.
                    response = response + '\n' + post.title.encode('ascii', 'ignore')
                language = 'nl-nl'
            elif intent == "weather":
                d = feedparser.parse('http://projects.knmi.nl/RSSread/rss_KNMIverwachtingen.php')
                response = d['entries'][0]['description']
                # feedparser can return Unicode strings, so convert to ASCII.
                response = response.encode('ascii', 'ignore')
                language = 'nl-nl'
            elif intent == "radio":
                if value == "hits":
                    station = 'http://87.118.122.45:30710'
                elif value == "salsa":
                    station = 'http://50.7.56.2:8020'
                else:
                    station = 'http://108.61.73.117:8124'
                # Start Music Player Daemon service and play music.
                setVolumeLoudspeaker(volumeMusic)
                stdOutAndErr = own_util.runShellCommandWait('sudo service mpd start;mpc clear;mpc add ' + station + ';mpc play')
            elif intent == "query":
                response = query(text)
            else:
                # Not a valid intent.
                stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/nocomprendo.mp3')
                switchOffLoudspeaker()
            if response != '':
                logging.getLogger("MyLog").info('response: ' + response)
                setVolumeLoudspeaker(volumeVoice)
                # Non blocking call to textToSpeech() which will turn off the loudspeaker when it's done.
                textToSpeech(response, language, '0')
                # Now we activate the interactive command, after the speech response is generated.
                if tmpCmd != '':
                    globCmd = tmpCmd
                    # set globInteractive to True so the server can take appropriate action, for example stop motion detection.
                    globInteractive = True
                    # Sleep to give server time to start the command. Then set globInteractive to False again.
                    time.sleep(1.0)
                    globInteractive = False
        except Exception,e:
            logging.getLogger("MyLog").info('personalAssistant exception: ' + str(e))
            # Switch off the loudspeaker if it is still on.
            switchOffLoudspeaker()


def startPersonalAssistant():
    initMicrophone()
    initLoudspeaker()
    thread.start_new_thread(personalAssistant, ())

