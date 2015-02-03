#!/usr/bin/env python

import subprocess
import cgi
import cgitb

cgitb.enable()

print "Content-type: text/html\n\n"

# Create instance of FieldStorage
form = cgi.FieldStorage()

# Get data from fields
if form.getvalue('Start stream'):
    bashCommand = "LD_LIBRARY_PATH=/opt/mjpg-streamer/ /opt/mjpg-streamer/mjpg_streamer -i \"input_raspicam.so -vf -fps 15 -q 50 -ex sports -x 800 -y 600\" -o \"output_http.so -p 44445 -w /opt/mjpg-streamer/www\" > /dev/null 2>&1 &"
    output = subprocess.check_output(bashCommand, shell=True)

if form.getvalue('Stop stream'):
    bashCommand = "kill $(pgrep mjpg_streamer) > /dev/null 2>&1"
    output = subprocess.check_output(bashCommand, shell=True)

if output != "":
    print "<h1>error mjpg_streamer: " + output + "</h1>"
