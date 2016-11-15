#!/usr/local/bin/python
import sys
import subprocess
# Import the secret.py module which is in a differend directory outside GitHub.
sys.path.insert(0, sys.path[0]+"/../../NotForGitHub/")
import secret


# runShellCommandWait(cmd) will block until 'cmd' is finished.
# This because the communicate() method is used to communicate to interact with the process through the redirected pipes.
def runShellCommandWait(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0]


stdOutAndErr = runShellCommandWait('curl -XPOST "https://api.wit.ai/speech?v=20160526" -i -L -H "Authorization: Bearer ' + secret.WitAiToken + '" -H "Content-Type: audio/wav" --data-binary "@mic.wav"')

print stdOutAndErr
