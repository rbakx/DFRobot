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

    def totalAvg(self):
        tot = 0
        for el in self.in_stack:
            tot += el

        for el in self.out_stack:
            tot += el
            
        return float(tot) / (len(self.in_stack) + len(self.out_stack))

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

def waitForSound():
    # Open the device in nonblocking capture mode. The last argument could
    # just as well have been zero for blocking mode. Then we could have
    # left out the sleep call in the bottom of the loop
    card = 'sysdefault:CARD=AK5370'
    inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE,alsaaudio.PCM_NONBLOCK, card)
    
    # Set attributes: Mono, 8000 Hz, 16 bit little endian samples
    inp.setchannels(1)
    inp.setrate(16000)
    inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    
    # The period size controls the internal number of frames per period.
    # The significance of this parameter is documented in the ALSA api.
    # For our purposes, it is suficcient to know that reads from the device
    # will return this many frames. Each frame being 2 bytes long.
    # This means that the reads below will return either 320 bytes of data
    # or 0 bytes of data. The latter is possible because we are in nonblocking
    # mode.
    inp.setperiodsize(160)
    
    last = 0
    max = 0
    clapped = False
    out = False
    
    queue = Queue();
    avgQueue = Queue();
    
    n = 0;
    n2=0;
    doContinue = True
    while doContinue:
        # Read data from device
        l,data = inp.read()
        if l:
            err = False
            volume = -1
            try:
                volume = audioop.max(data, 2)
            except:
                #print "err";
                err = True
            if err: continue
            
            queue.push(volume)
            avgQueue.push(volume)
            n = n + 1
            n2 = n2 + 1
            if n2 > 500:
                avgQueue.pop()
        
            if n > queue.size:
                avg = avgQueue.totalAvg()
                #print "avg last fragments: " + str(avg)
                
                low_limit = avg + 10
                #high_limit = avg + 30
                high_limit = avg + 300
                
                queue.pop();
                queue.makeOrdered();
                v1 = queue.firstAvg();
                v2 = queue.secondAvg();
                v3 = queue.thirdAvg();
                v4 = queue.fourthAvg();
                v5 = queue.fifthAvg();
                #if v1 < low_limit: print str(n)+": v1 ok"                 #if v2 > high_limit: print str(n)+": v2 ok"
                #if v3 < low_limit: print str(n)+": v3 ok"                 #if v4 > high_limit: print str(n)+": v4 ok"
                #if v5 < low_limit: print str(n)+": v5 ok"
                
                if v1 < low_limit and v2 > high_limit and v3 < low_limit and v4 > high_limit and v5 < low_limit:
                    #print str(time.time())+": sgaMED"
                    out = not out
                    queue.clear()
                    n = 0
                    doContinue = False

        time.sleep(0.01)


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
    switchOnLoudspeaker()
    stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')
    switchOffLoudspeaker()
    while True:
        try:
            waitForSound()
            switchOnLoudspeaker()
            stdOutAndErr = own_util.runShellCommandWait('/usr/bin/mplayer /home/pi/Sources/james.mp3')

            text = speechToText()
            logging.getLogger("MyLog").info('speecht to text: ' + text)
            if text != "":
                response = query(text)
            else:
                response = "Sorry, I do not understand the question"
            logging.getLogger("MyLog").info('response: ' + response)
            textToSpeech(response)
            switchOffLoudspeaker()
        except Exception,e:
            logging.getLogger("MyLog").info('personalAssistant exception: ' + str(e))


def startPersonalAssistant():
    initMicrophone()
    initLoudspeaker()
    thread.start_new_thread(personalAssistant, ())

