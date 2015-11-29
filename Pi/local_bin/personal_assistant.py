#!/usr/bin/python
import thread
import time
import math
import re
import alsaaudio, audioop
import wolframalpha
import feedparser
import logging
import own_util
import personal_assistant
import secret


# Global variables
globInteractive = False
globDoHomeRun = False
globCmd = ''


def checkClaps(p1, p2, p3, p4, p5):
    minClapRatio = 5.0
    if p2 / p1 > minClapRatio and p2 / p3 > minClapRatio and p4 / p3 > minClapRatio and p4 / p5 > minClapRatio:
        return True
    else:
        return False


def checkSilence(p1, p2, p3, p4, p5):
    maxSilenceRatio = 3.0
    SilenceThreshold = 10000000.0
    avg = (p1 + p2 + p3 + p4 + p5) / 5.0
    # First check for zero to prevent division by zero.
    if (p1 == 0 or p2 == 0 or p3 == 0 or p4 == 0 or p5 == 0):
        return False
    # Silence is True when all powers are below SilenceThreshold or when all powers are about equal.
    if (p1 < SilenceThreshold and p2 < SilenceThreshold and p3 < SilenceThreshold and p4 < SilenceThreshold and p5 < SilenceThreshold) or (abs(p1 - avg) / min(p1, avg) < maxSilenceRatio and abs(p2 - avg) / min(p2, avg) < maxSilenceRatio and abs(p3 - avg) / min(p3, avg) < maxSilenceRatio and abs(p4 - avg) / min(p4, avg) < maxSilenceRatio and abs(p5 - avg) / min(p5, avg) < maxSilenceRatio):
        return True
    else:
        return False


def waitForTriggerSound():
    # Constants used in this function.
    SampleRate = 16000
    PeriodSizeInSamples = 500
    BytesPerSample = 2 # Corrsponding to the PCM_FORMAT_S16_LE setting.
    PeriodSizeInBytes = PeriodSizeInSamples * BytesPerSample
    FiveSegmentsSizeInBytes = 20000
    SegmentSizeInBytes = 4000
    ClapCountInPeriods = FiveSegmentsSizeInBytes / PeriodSizeInBytes
    SilenceCountInPeriods = 2 * FiveSegmentsSizeInBytes / PeriodSizeInBytes  # the 2 because of echoes.
    
    # Open the device in blocking capture mode. During the blocking other threads can run.
    card = 'sysdefault:CARD=AK5370'
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
        # Read PeriodSizeInSamples audio samples from the audio input which is PeriodSizeInBytes bytes.
        # newAudioData will be a sequence of audio samples, stored as a Python string.
        l,newAudioData = inp.read()
        audioBuffer = audioBuffer + newAudioData
        if len(audioBuffer) >= FiveSegmentsSizeInBytes:
            p1 = math.pow(audioop.rms(audioBuffer[0:1*SegmentSizeInBytes], BytesPerSample), 2)
            p2 = math.pow(audioop.rms(audioBuffer[1*SegmentSizeInBytes:2*SegmentSizeInBytes], BytesPerSample), 2)
            p3 = math.pow(audioop.rms(audioBuffer[2*SegmentSizeInBytes:3*SegmentSizeInBytes], BytesPerSample), 2)
            p4 = math.pow(audioop.rms(audioBuffer[3*SegmentSizeInBytes:4*SegmentSizeInBytes], BytesPerSample), 2)
            p5 = math.pow(audioop.rms(audioBuffer[4*SegmentSizeInBytes:5*SegmentSizeInBytes], BytesPerSample), 2)
            audioBuffer = audioBuffer[PeriodSizeInBytes:]
            # The code below will be executed every period or PeriodSizeInSamples samples.
            # With 16 KHz sample rate this means every 31.25 ms.
            # Five powers p1..p5 are available of the last 5 segments.
            # We check if there are first 5 segments with silence, then 5 segments with two claps, then 5 segments with silence again.
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
    # Set microphone capturing volume.
    # To do this we have to find out which card is the capturing device with 'arecord -l'.
    # Suppose the capturing card is 'card 1', then its capabilities can be listed with 'amixer --card 1 contents'.
    # This will show the numid's of its interfaces. Look for the ''Mic Capture Volume' which has for example numid=3.
    # The microphone capturing volume can now be set with 'amixer -c 1 cset numid=3 78' which will set
    # the capturing volume to 78.
    # The maximum capturing volume can be checked by filling a higher value and check if this is set.
    stdOutAndErr = own_util.runShellCommandWait('amixer -c 1 cset numid=3 78')


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


def speechToText():
    stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -f cd -t wav | ffmpeg -loglevel panic -y -i - -ar 16000 -acodec flac /tmp/file.flac')

    stdOutAndErr = own_util.runShellCommandWait('wget -q --post-file /tmp/file.flac --header="Content-Type: audio/x-flac; rate=16000" -O - "http://www.google.com/speech-api/v2/recognize?client=chromium&lang=en_US&key=' + secret.SpeechToTextApiKey + '"')
    # Now stdOutAndErr is a multiline string containing possible transcripts with confidence levels.
    # The one with the highest confidence is listed first, so we filter out that one.

    # Use DOTALL (so '.' will also match a newline character) because stdOutAndErr can be multiline.
    regex = re.compile('.*?"transcript":"([^"]+).*', re.DOTALL)
    match = regex.match(stdOutAndErr)
    if match is not None:
        text = match.group(1)
    else:
        text = ""

    return text


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
    switchOnLoudspeaker()
    stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')
    switchOffLoudspeaker()
    while True:
        try:
            tmpCmd = ''
            # Wait for the trigger sound. This contains a sleep to enable other threads to run.
            waitForTriggerSound()
            # Check if the previous command is still running. If so, kill it and continue waiting for the next trigger sound.
            # This way it is possible to start a command with two claps and also stop a running command with two claps.
            stdOutAndErr = own_util.runShellCommandWait('sudo killall mplayer')
            if stdOutAndErr == "":
                switchOffLoudspeaker()
                continue
            stdOutAndErr = own_util.runShellCommandWait('mpc current')
            if stdOutAndErr != "" and 'error' not in stdOutAndErr:
                # Stop playing music and stop Music Player Daemon service.
                stdOutAndErr = own_util.runShellCommandWait('mpc stop;mpc clear;sudo service mpd stop')
                switchOffLoudspeaker()
                continue
            switchOnLoudspeaker()
            setVolumeLoudspeaker('100%')  # default volume
            stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')

            text = speechToText()
            logging.getLogger("MyLog").info('speecht to text: ' + text)
            response = ''
            if text != "":
                if re.search('james lights on', text, re.IGNORECASE):
                    tmpCmd = 'light-on'
                    language = 'en-us'
                    response = 'lights on'
                elif re.search('james lights off', text, re.IGNORECASE):
                    tmpCmd = 'light-off'
                    language = 'en-us'
                    response = 'lights off'
                elif re.search('james demo', text, re.IGNORECASE):
                    tmpCmd = 'demo-start'
                    language = 'en-us'
                    response = 'demo activated'
                    globDoHomeRun = True
                elif re.search('james stop', text, re.IGNORECASE):
                    tmpCmd = 'demo-stop'
                    language = 'en-us'
                    response = 'demo stopped'
                    globDoHomeRun = False
                elif re.search('james news', text, re.IGNORECASE):
                    d = feedparser.parse('http://www.ed.nl/cmlink/1.3280365')
                    response = ''
                    for post in d.entries[:10]:  # Restrict to 10 entries.
                        # feedparser can return Unicode strings, so convert to ASCII.
                        response = response + '\n' + post.title.encode('ascii', 'ignore')
                    language = 'nl-nl'
                elif re.search('james news netherlands', text, re.IGNORECASE):
                    d = feedparser.parse('http://www.ed.nl/cmlink/1.3280352')
                    response = ''
                    for post in d.entries[:10]:  # Restrict to 10 entries.
                        # feedparser can return Unicode strings, so convert to ASCII.
                        response = response + '\n' + post.title.encode('ascii', 'ignore')
                    language = 'nl-nl'
                elif re.search('james news local', text, re.IGNORECASE):
                    d = feedparser.parse('http://www.ed.nl/cmlink/1.4419308')
                    response = ''
                    for post in d.entries[:1000]:  # Restrict to 10 entries.
                        # feedparser can return Unicode strings, so convert to ASCII.
                        response = response + '\n' + post.title.encode('ascii', 'ignore')
                    language = 'nl-nl'
                elif re.search('james weather', text, re.IGNORECASE):
                    d = feedparser.parse('http://projects.knmi.nl/RSSread/rss_KNMIverwachtingen.php')
                    response = d['entries'][0]['description']
                    # feedparser can return Unicode strings, so convert to ASCII.
                    response = response.encode('ascii', 'ignore')
                    language = 'nl-nl'
                elif re.search('james radio', text, re.IGNORECASE):
                    # Start Music Player Daemon service and play music.
                    station = 'http://50.7.56.2:8020'
                    setVolumeLoudspeaker('70%')
                    stdOutAndErr = own_util.runShellCommandWait('sudo service mpd start;mpc clear;mpc add ' + station + ';mpc play')
                else:
                    language = 'en-us'
                    response = query(text)
            else:
                language = 'en-us'
                response = "Sorry, I do not understand the question"
            if response != '':
                logging.getLogger("MyLog").info('response: ' + response)
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


def startPersonalAssistant():
    initMicrophone()
    initLoudspeaker()
    thread.start_new_thread(personalAssistant, ())

