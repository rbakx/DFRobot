#!/usr/local/bin/python
import sys
import subprocess
import json
import base64
# Import the secret.py module which is in a differend directory outside GitHub.
sys.path.insert(0, sys.path[0]+"/../../NotForGitHub/")
import secret


# runShellCommandWait(cmd) will block until 'cmd' is finished.
# This because the communicate() method is used to communicate to interact with the process through the redirected pipes.
def runShellCommandWait(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0]


with open("mic.flac", 'rb') as speech:
    speech_content = base64.b64encode(speech.read())

payload = {
    "config": {
        "encoding":"FLAC",
        "sampleRate": 16000,
        "languageCode": "en-US",
        "speechContext": {
            "phrases": ["james radio salsa", "radio", "salsa"]
        }
    },
    "audio": {
        "content": speech_content.decode("UTF-8")
    }
}

data=json.dumps(payload)
stdOutAndErr = runShellCommandWait('curl -s -X POST -H "Content-Type: application/json" --data-binary \'' + data + '\' "https://speech.googleapis.com/v1beta1/speech:syncrecognize?key=' + secret.SpeechToTextGoogleCloudApiKey + '"')

print stdOutAndErr

