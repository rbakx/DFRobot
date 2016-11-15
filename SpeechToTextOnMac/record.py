#!/usr/local/bin/python
import pyaudio
import wave
import subprocess


FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 3
WAVE_OUTPUT_FILENAME = "mic.wav"


# runShellCommandWait(cmd) will block until 'cmd' is finished.
# This because the communicate() method is used to communicate to interact with the process through the redirected pipes.
def runShellCommandWait(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0]


audio = pyaudio.PyAudio()

# start Recording
stream = audio.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,
                    frames_per_buffer=CHUNK)
print "recording..."
frames = []

for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)
print "finished recording"


# stop Recording
stream.stop_stream()
stream.close()
audio.terminate()

waveFile = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
waveFile.setnchannels(CHANNELS)
waveFile.setsampwidth(audio.get_sample_size(FORMAT))
waveFile.setframerate(RATE)
waveFile.writeframes(b''.join(frames))
waveFile.close()

# Convert recorded .wav file into .flac which is the required format for Google Cloud Speech API.
stdOutAndErr = runShellCommandWait('avconv -i mic.wav -acodec flac -b: 128k mic.flac -y')
