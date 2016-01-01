#!/usr/bin/python

import time
import math
import alsaaudio, audioop
from scipy import signal
import struct
import numpy as np
import own_util

# Global constants
SampleRate = 16000
NyquistFrequency = 0.5 * SampleRate
B, A = signal.butter(5, [4400.0/NyquistFrequency, 4600.0/NyquistFrequency], btype='band')
FirCoeff = signal.firwin(29, 4000.0/NyquistFrequency, pass_zero=False)


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
        print '******************************** CLAPS DETECTED *****'
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
        print '***** SILENCE DETECTED *****'
        return True
    else:
        return False


def waitForTriggerSound():
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
    # effectively is always 341 samples. This might be an alsaaudio bug.
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
            print p1, p2, p3, p4, p5
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
                        # No silence detected in time, so start over again.
                        doContinue1 = True


stdOutAndErr = own_util.runShellCommandWait('amixer -c 1 cset numid=3 16')
stdOutAndErr = own_util.runShellCommandWait('amixer -c 1 cset numid=4 0')
waitForTriggerSound()
