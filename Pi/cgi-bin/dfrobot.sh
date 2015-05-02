#!/bin/bash

function handle_command {
    if [ "${1}" == "start-stream" ]
    then
        LD_LIBRARY_PATH=/opt/mjpg-streamer/ /opt/mjpg-streamer/mjpg_streamer -i "input_raspicam.so -vf -hf -fps 15 -q 50 -ex sports -x 800 -y 600" -o "output_http.so -p 44445 -w /opt/mjpg-streamer/www" > /dev/null 2>&1 &
    elif [ "${1}" == "stop-stream" ]
    then
        kill $(pgrep mjpg_streamer) > /dev/null 2>&1
    elif [ "${1}" == "capture-start" ]
    then
        # Start capture video, time limit is set to 1 minute.
        raspivid -o /tmp/pivid.h264 -w 1280 -h 720 -vf -hf -t 60000 > /dev/null 2>&1 &
    elif [ "${1}" == "capture-stop" ]
    then
        killall raspivid
        # Convert to mp4. Do wait for it to finish before starting the upload so no '&' at the end.
        MP4Box -fps 30 -new -add /tmp/pivid.h264 /tmp/pivid.mp4 > /dev/null 2>&1
        # Going to upload the file to Google Drive using the 'drive' utility.
        # 'sudo -u www-data' is used here to behave as the exact same www-data user
        # as when the verification code was generated (using also sudo -u),
        # else Google will ask for a new verification code.
        # Apparently when Apache uses www-data it is different in a way.
        sudo -u www-data drive upload -f /tmp/pivid.mp4 > /dev/null 2>&1 &
    elif [ "${1}" == "home" ]
    then
        echo hello
    elif [ "${1}" == "forward" ]
    then
        i2c_cmd 1 ${2} > /dev/null 2>&1
    elif [ "${1}" == "backward" ]
    then
        i2c_cmd 2 ${2} > /dev/null 2>&1
    elif [ "${1}" == "left" ]
    then
        i2c_cmd 3 ${2} > /dev/null 2>&1
    elif [ "${1}" == "right" ]
    then
        i2c_cmd 4 ${2} > /dev/null 2>&1
    elif [ "${1}" == "cam-up" ]
    then
        i2c_cmd 10 > /dev/null 2>&1
    elif [ "${1}" == "cam-down" ]
    then
        i2c_cmd 11 > /dev/null 2>&1
    elif [ "${1}" == "light-on" ]
    then
        i2c_cmd 20 > /dev/null 2>&1
    elif [ "${1}" == "light-off" ]
    then
        i2c_cmd 21 > /dev/null 2>&1
    elif [ "${1}" == "status" ]
    then
        do_update=true
    fi
}

do_update=false

# CGI POST method handling code below taken from http://tuxx-home.at/cmt.php?article=/2005/06/17/T09_07_39/index.html
if [ "$REQUEST_METHOD" = "POST" ]; then
    read POST_STRING

    # replace all escaped percent signs with a single percent sign
    POST_STRING=$(echo $POST_STRING | sed 's/%%/%/g')

    # replace all ampersands with spaces for easier handling later
    POST_STRING=$(echo $POST_STRING | sed 's/&/ /g')

    # Now $POST_STRING contains 'cmd=<value>' where 'cmd' and '<value>' correspond with the
    # 'name' and 'value' attribute of the button pressed in the client side html file.
    # Filter out <value> and store it in $COMMAND.
    COMMAND_PLUS_PARAMETER="$(echo $POST_STRING | sed -n 's/^.*cmd=\([^ ]*\).*$/\1/p')"
    COMMAND="$(echo $COMMAND_PLUS_PARAMETER | sed -n 's/\([^.]*\).*$/\1/p')"
    PARAMETER="$(echo $COMMAND_PLUS_PARAMETER | sed -n 's/[^.]*\.\(.*$\)/\1/p')"

    # Call command handler.
    handle_command $COMMAND $PARAMETER
fi

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

#echo -e "Location: ../index1.html\n"

if [ $do_update = false ]
then
    echo -e "Status:304\n"
else
    # Get actual status so it can be sent to the web client.
    wifistatus=/sbin/iwconfig
    status="<br>$($wifistatus | sed -n 's/^.*ESSID:"\([^"]*\).*$/\1/p') level = $($wifistatus | sed -n 's/^.*level=\([^ ]*\).*$/\1/p') dBm<br>uptime = $(/usr/bin/uptime | sed -n 's/.*up \([^,]*\).*/\1/p')<br>battery = $(i2c_cmd 0 | sed -n 's/^.*Received \([^ ]*\).*$/\1/p') (154 = 6V)"

    # Send 'index1.html' to the web client, after replacing the 'feedbackstring' with the actual status.
    echo -e "Content-type: text/html\n"
    while read line
    do
        # Replace 'feedbackstring' in original string with the actual status.
        echo -e ${line/feedbackstring/$status}
    done < ${1}
fi


