#!/usr/bin/env python

import subprocess
import cgi
import cgitb

cgitb.enable()

# Create instance of FieldStorage
form = cgi.FieldStorage()

# Get data from fields
output = ""
if form.getvalue('Start stream'):
    bashCommand = "LD_LIBRARY_PATH=/opt/mjpg-streamer/ /opt/mjpg-streamer/mjpg_streamer -i \"input_raspicam.so -vf -hf -fps 15 -q 50 -ex sports -x 800 -y 600\" -o \"output_http.so -p 44445 -w /opt/mjpg-streamer/www\" > /dev/null 2>&1 &"
    output = subprocess.check_output(bashCommand, shell=True)

if form.getvalue('Stop stream'):
    bashCommand = "kill $(pgrep mjpg_streamer) > /dev/null 2>&1"
    output = subprocess.check_output(bashCommand, shell=True)

if output != "":
    print "<h1>error mjpg_streamer: " + output + "</h1>"

# Now we must return a valid HTTP header to the client, otherwise an "Internal Server Error" will be generated.
# Below are three options:
# 1. Use HTTP header "Content-type" and then add an HTML meta 'refresh' to force a refresh of the page.
#    This has the disadvantage that the refresh is visible, dependent of the browser.
# 2. Use HTTP header "Location" and point it to the original page so this will also refresh the page.
#    This has the disadvantage that the refresh is visible, dependent of the browser.
# 3. Use the HTTP header "Status" and return code 304, which means "Not Modified".
#    This will prevent most browsers from reloading the page and is the preferred method.
#    The disadvantage that the new html content like the robot status is not updated.
# The best option might be to use option 3 when no status update is needed else option 2.
 
#print "Location: ../index1.html\n\n"
print "Status:304\n\n"
