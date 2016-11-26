#!/usr/bin/python
import thread
import time
import math
import re
import json
import base64
import datetime
import alsaaudio, audioop
from scipy import signal
import struct
import numpy as np
import wolframalpha
import feedparser
import logging
import own_util
import own_gpio
import secret

# Global constants
# Phrase hints are the phrases which are likely to be spoken. They are used to improve speech recognition.
phraseHints = ["radio salsa", "radio hits", "radio christmas", "volume", "demo"]
SampleRate = 16000
NyquistFrequency = 0.5 * SampleRate
B, A = signal.butter(5, [4400.0/NyquistFrequency, 4600.0/NyquistFrequency], btype='band')
FirCoeff = signal.firwin(29, 4000.0/NyquistFrequency, pass_zero=False)

# Global variables
globInteractive = False
globDoHomeRun = False
globDistance = 1000
globProximityCount = 0
globCmd = ''
globVolumeVoice = '90%'  # Volume used for voice responses.
globVolumeAlarm = '90%'  # Volume used for alarm.
globVolumeMusic = '70%'  # Volume used for music, can be set by voice command.
globDoMotionDetection = False
globTelegramSendPicture = False


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
    minClapRatio = 10.0
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


# This function waits for the claps event or alarm and returns when the event has occurred.
def waitForClaps():
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


# This function waits for an event like the proximity event or alarm and returns when the event has occurred.
def waitForProximity():
    global globAlarmStatus, globAlarm
    global globDistance, globProximityCount
    while True:
        # Check for alarm event.
        if globAlarmStatus == 'SET' and datetime.datetime.now().time() > datetime.time(*globAlarm):
            # Indicate alarm and return.
            globAlarmStatus = 'ALARMSET'
            return
        # Check for proximity event. Only consider it as an event when the distance gets below the treshhold for the first n times.
        # The 'n' times is because the distance measurement occasionally shows wrong values.
        # Only consider the 'first' n times to prevent new events occurring when for example a hand is kept in front of the robot.
        # Do not check for proximity during a Home run, this because during a Home run the proximity to objects can be small.
        if globDoHomeRun == False:
            if globDistance > 0.0 and globDistance < 20.0:
                globProximityCount = globProximityCount + 1
                if globProximityCount == 2:
                    # Proximity event detected!
                    logging.getLogger("MyLog").info('proximity event')
                    # Because handling the event means listening to a spoken command through the microphone,
                    # first stop the DFRobot webpage microphone streaming audio if any to free the microphone.
                    # Use pkill -f with regular expression to kill te right vlc process.
                    stdOutAndErr = own_util.runShellCommandWait('sudo pkill -f "vlc -I.*alsa"')
                    return
            elif globDistance >= 20.0:
                globProximityCount = 0;
        # No proximity detected, so microphone will not be used by the Personal Assistent to record local speech.
        # This means the micropone audio stream for the DFRobot webpage can be enabled.
        # It was tried to start the microphone audio stream only after the user clicks a 'Mic' button on the DFRobot webpage.
        # This does not work because then the webpage starts listening before the stream is actually started and it will not connect to the stream.
        # Therefore we now start the microphone audio stream for the DFRobot webpage whenever it is not used by the Personal assistant to record local speech.
        # First check if the microphone audio stream is already running. If not, start it.
        # The 'cvlc alsa://hw:1,0' part of the command specifies that VLC will use the Linux ALSA API and connect to card 1, device 0.
        # Using 'arecord -l' (which lists the 'CAPTURE Hardware Devices') one can see that this is 'card 1: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]', which means the USB microphone.
        # This device has a default format of 'PCM S16LE' (PCM signed 16-bit little-endian) at 48000 Hz, Mono.
        # The 48000 Hz is a bit overkill for the USB microphone so to save bandwidth we want to use 16000Hz.
        # However, it is not clear whether it is possible to put the ALSA USB Audio device directly into a lower bitrate.
        # Therefore with VLC we transcode the audio stream into 's16le' at 16000 Hz.
        stdOutAndErr = own_util.runShellCommandWait('ps -ef | grep "vlc -I.* alsa" | wc -l')
        if int(stdOutAndErr) < 3:  # 1 extra line is found because of grep command itself and 1 extra line because of the stdOutAndErr output ending with a newline.
            stdOutAndErr = own_util.runShellCommandNowait('cvlc alsa://hw:1,0 --sout \'#transcode{acodec= s16le,channels=1,samplerate=16000}:standard{access=http,mux=ogg,dst=:44446}\'')

        # Sleep to enable other threads to run. The sleep time can be the same as used in the proximityLoop.
        time.sleep(0.1)


def proximityLoop():
    global globDistance
    while True:
        # Check for proximity event.
        globDistance = own_gpio.getUsSensorDistance(0)
        time.sleep(0.1)  # Wait for the echo to damp out.


def initMicrophone():
    # Set microphone capturing volume and gain control.
    # To do this we have to find out which card is the capturing device with 'arecord -l', which lists the 'CAPTURE Hardware Devices'.
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


# Records speech from the microphone and translates this into a text.
# It supports the formats of multiple STT engines.
def speechToText(sttEngine):
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
                        "phrases": phraseHints
                    }
                },
                "audio": {
                    "content": speech_content.decode("UTF-8")
                }
            }
            jsonData=json.dumps(payload)
            stdOutAndErr = own_util.runShellCommandWait('curl -s -X POST -H "Content-Type: application/json" --data-binary \'' + jsonData + '\' "https://speech.googleapis.com/v1beta1/speech:syncrecognize?key=' + secret.SpeechToTextGoogleCloudApiKey + '"')
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

    # Now text contains the spoken text.
    return text


# Translates a text into a (intent,value) tuple.
def textToIntent(text):
    intent = ""
    value = ""
    if re.search('(?:volume|vol).*', text, re.IGNORECASE):
        m = re.search('^(?:volume|vol) ([0-9]|10)$', text, re.IGNORECASE)
        if m and m.group(1) and m.group(1) != "":  # be safe
            intent = "volume"
            value = m.group(1)
        else:
            intent = "volume"
            value = "invalid"
    elif re.search('^alarm at.*', text, re.IGNORECASE):
        (hours,minutes) = textToHoursAndMinutes(text, sttEngine)
        intent = "alarm"
        value = (hours,minutes)
    elif re.search('^alarm$', text, re.IGNORECASE):
        intent = "alarm"
        value = None
    elif re.search('^date$|^time$', text, re.IGNORECASE):
        intent = "time"
        value = None
    elif re.search('^lights on$', text, re.IGNORECASE):
        intent = "light"
        value = "on"
    elif re.search('^lights off$', text, re.IGNORECASE):
        intent = "light"
        value = "off"
    elif re.search('^demo$', text, re.IGNORECASE):
        intent = "demo"
        value = "start"
    elif re.search('^stop$', text, re.IGNORECASE):
        intent = "demo"
        value = "stop"
    elif re.search('^go home$', text, re.IGNORECASE):
        intent = "home"
        value = "start"
    elif re.search('^news$', text, re.IGNORECASE):
        intent = "news"
        value = "world"
    elif re.search('^news netherlands$', text, re.IGNORECASE):
        intent = "news"
        value = "netherlands"
    elif re.search('^news local$', text, re.IGNORECASE):
        intent = "news"
        value = "eindhoven"
    elif re.search('^weather$', text, re.IGNORECASE):
        intent = "weather"
        value = None
    elif re.search('^radio hits$', text, re.IGNORECASE):
        intent = "radio"
        value = "hits"
    elif re.search('^radio salsa$', text, re.IGNORECASE):
        intent = "radio"
        value = "salsa"
    elif re.search('^radio christmas$', text, re.IGNORECASE):
        intent = "radio"
        value = "christmas"
    elif re.search('^radio off$', text, re.IGNORECASE):
        intent = "radio"
        value = "off"
    elif re.search('^motion on$', text, re.IGNORECASE):
        intent = "motion"
        value = "on"
    elif re.search('^motion off$', text, re.IGNORECASE):
        intent = "motion"
        value = "off"
    elif re.search('^picture$', text, re.IGNORECASE):
        intent = "picture"
        value = ""
    elif re.search('^hi$', text, re.IGNORECASE):
        intent = "greet"
        value = ""
    elif re.search('^battery$', text, re.IGNORECASE):
        intent = "battery"
        value = ""
    elif re.search('^awake$', text, re.IGNORECASE):
        intent = "awake"
        value = ""
    elif re.search('^joke$', text, re.IGNORECASE):
        intent = "joke"
        value = ""
    elif text != "":
        intent = "query"
        value = text
    return (intent,value)


def textToSpeech(text, language, speed):
    # Use runShellCommandNowait() to be able to continue and to stop this process if needed.
    # First turn loudspeaker on, then play speech. When speech is finished the loudspeaker is turned off.
    own_util.runShellCommandNowait(' /usr/local/bin/own_gpio.py --loudspeaker on;/usr/bin/mplayer -ao alsa -really-quiet -noconsolecontrols "http://api.voicerss.org/?key=' + secret.VoiceRSSApiKey + '&hl=' + language + '&r=' + speed + '&f=16khz_16bit_mono&src=' + text + '"' + ';/usr/local/bin/own_gpio.py --loudspeaker off')


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


# Handle the intent and initiate the corresponding action.
# 'client' can be:
#  - "speech" for handling the intent and corresponding action for a person nearby the robot.
#  - "text" for handling the intent and corresponding action for a person connected via Telegram with the robot.
# Returns a text response.
def handleIntent(intent, value, client):
    global globInteractive, globDoHomeRun, globCmd
    global globAlarmStatus, globAlarm
    global globVolumeVoice, globVolumeAlarm, globVolumeMusic
    global globDoMotionDetection, globTelegramSendPicture
    try:
        language = 'en-us' # default language
        response = ''
        tmpCmd = ''
        if intent == "volume":
            if value != "invalid":
                globVolumeMusic = str(int(value) * 10) + '%'
                response = 'volume ' + value
                setVolumeLoudspeaker(globVolumeMusic)
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
        elif intent == "home":
            if value == "start":
                tmpCmd = 'home-start'
                response = 'going home'
                globDoHomeRun = True
            else:
                tmpCmd = 'home-stop'
                response = 'home stopped'
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
            elif value == "christmas":
                station = 'http://108.61.73.117:8124'
            elif value == "off":
                station = ''
            if station != '':
                # Start Music Player Daemon service and play music.
                setVolumeLoudspeaker(globVolumeMusic)
                own_gpio.switchOnLoudspeaker()
                stdOutAndErr = own_util.runShellCommandWait('sudo service mpd start;mpc clear;mpc add ' + station + ';mpc play')
            else:
                # Stop playing music and stop Music Player Daemon service.
                stdOutAndErr = own_util.runShellCommandWait('mpc stop;mpc clear;sudo service mpd stop')
                own_gpio.switchOffLoudspeaker()
        elif intent =="motion":
            if value == "on":
                globDoMotionDetection = True
                response = 'motion detection is on'
            else:
                globDoMotionDetection = False
                response = 'motion detection is off'
        elif intent =="picture":
            globTelegramSendPicture = True
        elif intent =="greet":
            response = 'hi there!'
        elif intent == "battery":
            if own_util.checkCharging() == True:
                response = 'I am charging, my battery level is ' + str(own_util.getBatteryLevel())
            else:
                response = 'I am not charging, my battery level is ' + str(own_util.getBatteryLevel())
        elif intent == "awake":
            response = 'I am awake for ' + own_util.getUptime()
        elif intent == "joke":
            response = '\'What does your robot do, Sam?\' .......... \'It collects data about the surrounding environment, then discards it and drives into walls\''
        elif intent == "query":
            response = query(value)
        else:
            # Not a valid intent.
            if client == "speech":
                own_gpio.switchOnLoudspeaker()
                stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/nocomprendo.mp3')
                own_gpio.switchOffLoudspeaker()
            elif client == "text":
                response = "no comprendo"
        if response != '':
            logging.getLogger("MyLog").info('response: ' + response)
            if client == "speech":
                setVolumeLoudspeaker(globVolumeVoice)
                # Non blocking call to textToSpeech() which will turn off the loudspeaker when it's done.
                textToSpeech(response, language, '0')
        # Initiate the corresponding action.
        if tmpCmd != '':
            globCmd = tmpCmd
            # set globInteractive to True so the server can take appropriate action, for example stop motion detection.
            globInteractive = True
            # Sleep to give server time to start the command. Then set globInteractive to False again.
            time.sleep(1.0)
            globInteractive = False
    except Exception,e:
        logging.getLogger("MyLog").info('handleIntent exception: ' + str(e))
        # Switch off the loudspeaker if it is still on.
        own_gpio.switchOffLoudspeaker()
    return response


# Let the robot be a personal assistant.
def personalAssistant():
    global globDoHomeRun
    global globAlarmStatus
    global globVolumeVoice, globVolumeAlarm, globVolumeMusic
    own_gpio.switchOnLoudspeaker()
    stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')
    own_gpio.switchOffLoudspeaker()
    globAlarmStatus = ''
    while True:
        try:
            # Wait for the claps event, proximity event or alarm. These functions contain a sleep to enable other threads to run.
            # Choose waitForClaps() or waitForProximity() below.
            waitForProximity()
            # Event occurred. An event can be for example two claps to request a servie, two claps to interrupt an action or an alarm.
            # 'eventHandled' is used to check whether the event is handled or not.
            eventHandled = False
            # Check if the previous command is still running. If so, kill it and continue waiting for the next trigger sound.
            # This way it is possible to start a command with two claps and also stop a running command with two claps.
            stdOutAndErr = own_util.runShellCommandWait('sudo killall mplayer')
            if stdOutAndErr == "":
                own_gpio.switchOffLoudspeaker()
                eventHandled = True  # Indicate the event is handled.
            stdOutAndErr = own_util.runShellCommandWait('mpc current')
            if stdOutAndErr != "" and 'error' not in stdOutAndErr:
                # Stop playing music and stop Music Player Daemon service.
                stdOutAndErr = own_util.runShellCommandWait('mpc stop;mpc clear;sudo service mpd stop')
                own_gpio.switchOffLoudspeaker()
                eventHandled = True  # Indicate the event is handled.
            if globAlarmStatus == 'ALARMSET':
                # Switch on loadspeaker, sound the alarm and switch off loudspeaker.
                setVolumeLoudspeaker(globVolumeVoice)
                # Use runShellCommandNowait() to be able to continue and to stop this process if needed.
                # First turn loudspeaker on, then play alarm. When alarm is finished the loudspeaker is turned off.
                setVolumeLoudspeaker(globVolumeAlarm)
                own_util.runShellCommandNowait('/usr/local/bin/own_gpio.py --loudspeaker on;/usr/bin/mplayer /home/pi/Sources/alarm.mp3;/usr/local/bin/own_gpio.py --loudspeaker off')
                globAlarmStatus = ''  # reset alarm
                eventHandled = True   # Indicate the event is handled.
            if globDoHomeRun == True:
                globDoHomeRun = False
                eventHandled = True   # Indicate the event is handled.
            # If event is handled already here, continue to wait for the next event.
            if eventHandled == True:
                continue
            # Speak out greeting.
            setVolumeLoudspeaker(globVolumeVoice)
            own_gpio.switchOnLoudspeaker()
            stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')
            own_gpio.switchOffLoudspeaker()

            # Listen and translate speech to text.
            text = speechToText("Google")
            (intent,value) = textToIntent(text)
            logging.getLogger("MyLog").info('speech to text, intent, value: ' + str(text) + ", " + str(intent) + ", " + str(value))
            # Handle the intent.
            handleIntent(intent, value, "speech")
        except Exception,e:
            logging.getLogger("MyLog").info('personalAssistant exception: ' + str(e))
            # Switch off the loudspeaker if it is still on.
            own_gpio.switchOffLoudspeaker()


def startPersonalAssistant():
    own_gpio.initGpio()
    initMicrophone()
    initLoudspeaker()
    thread.start_new_thread(personalAssistant, ())
    # Start thread for measuring distance using the ultrasonic sensor. A seperate thread is needed because measuring distance is time critical.
    thread.start_new_thread(proximityLoop, ())

