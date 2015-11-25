#!/usr/bin/python
import thread
import time
import alsaaudio, audioop
import wolframalpha
import re
import logging
import own_util
import personal_assistant
import secret


# Global variables
globInteractive = False
globDoHomeRun = False
globCmd = ''


class Queue:
    """A sample implementation of a First-In-First-Out
        data structure."""
    def __init__(self):
        self.size = 35
        self.in_stack = []
        self.out_stack = []
        self.ordered = []
        self.debug = False
    def push(self, obj):
        self.in_stack.append(obj)
    def pop(self):
        if not self.out_stack:
            while self.in_stack:
                self.out_stack.append(self.in_stack.pop())
        return self.out_stack.pop()
    def clear(self):
        self.in_stack = []
        self.out_stack = []
    def makeOrdered(self):
        self.ordered = []
        for i in range(self.size):
            item = self.pop()
            self.ordered.append(item)
            self.push(item)
    
        if self.debug:
            i = 0
            for k in self.ordered:
                if i == 0: print "-- v1 --"
                if i == 5: print "-- v2 --"
                if i == 15: print "-- v3 --"
                if i == 20: print "-- v4 --"
                if i == 25: print "-- v5 --"
                
                for h in range(int(k/3)):
                    sys.stdout.write('#')
                print ""
                i=i+1

    def firstAvg(self):
        tot = 0
        for i in range(5):
            tot += self.ordered[i]
        return tot/5.0

    def secondAvg(self):
        tot = 0
        for i in range(5,15):
            tot += self.ordered[i]
        return tot/10.0

    def thirdAvg(self):
        tot = 0
        for i in range(15,20):
            tot += self.ordered[i]
        return tot/5.0

    def fourthAvg(self):
        tot = 0
        for i in range(20,30):
            tot += self.ordered[i]
        return tot/10.0

    def fifthAvg(self):
        tot = 0
        for i in range(30,35):
            tot += self.ordered[i]
        return tot/5.0


def checkClaps(v1, v2, v3, v4, v5):
    thresh = 5.0
    if v2 / v1 > thresh and v2 / v3 > thresh and v4 / v3 > thresh and v4 / v5 > thresh:
        return True
    else:
        return False


def checkSilence(v1, v2, v3, v4, v5):
    thresh = 2.0
    avg = (v1 + v2 + v3 + v4 + v5) / 5.0
    if abs(v1 - avg) / min(v1, avg) < thresh and abs(v2 - avg) / min(v2, avg) < thresh and abs(v3 - avg) / min(v3, avg) < thresh and abs(v4 - avg) / min(v4, avg) < thresh and abs(v5 - avg) / min(v5, avg) < thresh:
        return True
    else:
        return False


def waitForTriggerSound():
    # Open the device in blocking capture mode. During the blocking other threads can run.
    card = 'sysdefault:CARD=AK5370'
    inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE,alsaaudio.PCM_NORMAL, card)
    
    # Set attributes: Mono, 16000 Hz, 16 bit little endian samples
    inp.setchannels(1)
    inp.setrate(16000)
    inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    
    # The period size controls the internal number of samples per period.
    # The significance of this parameter is documented in the ALSA api.
    # For our purposes, it is suficcient to know that reads from the device
    # will return this many periods. Each sample being 2 bytes long.
    inp.setperiodsize(160)

    queue = Queue();
    
    n = 0;
    doContinue1 = True
    doContinue2 = True
    silenceCount = 0
    while doContinue1 or doContinue2:
        # Read data from device
        l,data = inp.read()
        if l:
            # 160 samples read = 10 msec = 1 period.
            err = False
            volume = -1
            try:
                volume = audioop.max(data, 2)
            except Exception,e:
                logging.getLogger("MyLog").info('personal assistant exception: ' + str(e))
                err = True
            if err: continue
            
            # Insert next period in queue.
            queue.push(volume)
            n = n + 1
            
            if n > queue.size:  # If queue is filled proceed with analyzing the sound.
                # 35 periods = 350 msec = 1 frame.

                queue.pop();
                queue.makeOrdered();
                v1 = queue.firstAvg();  # 50 ms
                v2 = queue.secondAvg(); # 100 ms
                v3 = queue.thirdAvg();  # 50 ms
                v4 = queue.fourthAvg(); # 100 ms
                v5 = queue.fifthAvg();  # 50 ms
                
                # The code below will be executed every period = 160 samples = 10 ms.
                # Five volumes v1..v5 are available of the last 350 ms (1 frame) divided in 5, 10, 5, 10, 5 ms respectively.
                # We check if there is first a frame with silence, then a frame with two claps, then a frame with silence again.
                if doContinue1:
                    # Check if there is a frame of silence.
                    if checkSilence(v1, v2, v3, v4, v5):
                        # A silence is detected of queue.size periods = 1 frame.
                        # Set the silenceCount to this value to reserve time for detecting two claps.
                        silenceCount = queue.size
                    elif silenceCount > 0:
                        # There is no silence any more. So two claps have to occur in the next silenceCount periods.
                        # As soon as this time is exceeded (silenceCount == 0) we have to wait for the next silence.
                        if checkClaps(v1, v2, v3, v4, v5):
                            # Two claps are detected. Start checking for silence again.
                            # Clear the queue so it will be filled again with the next frame which should contain silence.
                            queue.clear()
                            n = 0
                            doContinue1 = False
                            # Set silenceCount to 0 to prevent jumping directly to detecting claps in case of a next iteration.
                            silenceCount = 0
                        silenceCount = max(silenceCount - 1, 0)
                elif doContinue2:
                    # Check if there is silence after the two claps.
                    if checkSilence(v1, v2, v3, v4, v5):
                        # Trigger sound detected! Return from this function.
                        doContinue2 = False
                    else:
                        # Start over again.
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


def switchOnLoudspeaker():
    stdOutAndErr = own_util.runShellCommandWait('sudo /usr/local/bin/own_gpio.py --loudspeaker on')


def switchOffLoudspeaker():
    stdOutAndErr = own_util.runShellCommandWait('sudo /usr/local/bin/own_gpio.py --loudspeaker off')


def speechToText():
    stdOutAndErr = own_util.runShellCommandWait('arecord -d 5 -D "plughw:1,0" -q -f cd -t wav | ffmpeg -loglevel panic -y -i - -ar 16000 -acodec flac file.flac')

    stdOutAndErr = own_util.runShellCommandWait('wget -q --post-file file.flac --header="Content-Type: audio/x-flac; rate=16000" -O - "http://www.google.com/speech-api/v2/recognize?client=chromium&lang=en_US&key=' + secret.SpeechToTextApiKey + '"')
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


def textToSpeech(text):
    stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer -ao alsa -really-quiet -noconsolecontrols "http://api.voicerss.org/?key=' + secret.VoiceRSSApiKey + '&hl=en-us&f=16khz_16bit_mono&src=' + text + '"')


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
        # Encode uuencoded string to ASCII.
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
            switchOnLoudspeaker()
            stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')

            text = speechToText()
            logging.getLogger("MyLog").info('speecht to text: ' + text)
            if text != "":
                if re.search('james lights on please', text, re.IGNORECASE):
                    tmpCmd = 'light-on'
                    response = 'lights on'
                elif re.search('james lights off please', text, re.IGNORECASE):
                    tmpCmd = 'light-off'
                    response = 'lights off'
                elif re.search('james demo please', text, re.IGNORECASE):
                    tmpCmd = 'demo-start'
                    response = 'demo activated'
                    globDoHomeRun = True
                elif re.search('james stop', text, re.IGNORECASE):
                    response = 'demo stopped'
                    tmpCmd = 'demo-stop'
                    globDoHomeRun = False
                else:
                    response = query(text)
            else:
                response = "Sorry, I do not understand the question"
            logging.getLogger("MyLog").info('response: ' + response)
            textToSpeech(response)
            switchOffLoudspeaker()
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

