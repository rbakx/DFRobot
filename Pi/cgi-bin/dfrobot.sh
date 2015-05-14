#!/bin/bash

function handle_command {
    prompt=$(basename $0)
    # Reset the log file to zero length if the size gets too large.
    if [ $(stat -c %s /home/pi/log/dfrobot_log.txt) -gt 1000000 ]
    then
        echo -e "***** $(date), $prompt: START LOG  *****" > /home/pi/log/dfrobot_log.txt
    else
        echo -e "\n***** $(date), $prompt: START LOG  *****" >> /home/pi/log/dfrobot_log.txt
    fi

    if [ "${1}" == "start-stream" ]
    then
        echo "***** $(date), $prompt: 'start-stream' command received" >> /home/pi/log/dfrobot_log.txt
        uv4l --auto-video_nr --driver raspicam --encoding mjpeg --width 800 --height 600 --quality 10 --framerate 10 --exposure auto --hflip yes --vflip yes --server-option '--port=44445' >> /home/pi/log/dfrobot_log.txt 2>&1
    elif [ "${1}" == "stop-stream" ]
    then
        echo "***** $(date), $prompt: 'stop-stream' command received" >> /home/pi/log/dfrobot_log.txt
        killall uv4l
    elif [ "${1}" == "capture-start" ]
    then
        echo "***** $(date), $prompt: 'capture-start' command received" >> /home/pi/log/dfrobot_log.txt
        # Start capture video, time limit is set to 1 minute.
        echo "***** $(date), $prompt: going to call 'raspivid'" >> /home/pi/log/dfrobot_log.txt
        # Do not write output to logfile but to /dev/null to prevent filling up.
        raspivid -o /home/pi/DFRobotUploads/dfrobot_pivid.h264 -w 1280 -h 720 -vf -hf -t 60000 > /dev/null 2>&1 &
    elif [ "${1}" == "capture-stop" ]
    then
        echo "***** $(date), $prompt: 'capture-stop' command received" >> /home/pi/log/dfrobot_log.txt
        killall raspivid
        # Convert to mp4. Wait for it to finish before continuing.
        echo "***** $(date), $prompt: going to call 'MP4Box'" >> /home/pi/log/dfrobot_log.txt
        # Do not write output to logfile but to /dev/null to prevent filling up.
        MP4Box -fps 30 -new -add /home/pi/DFRobotUploads/dfrobot_pivid.h264 /home/pi/DFRobotUploads/dfrobot_pivid.mp4 > /dev/null 2>&1
        # Going to purge previously uploaded files to prevent filling up Google Drive. See below why 'sudo -u www-data' is used. Wait for it to finish before continuing.
        echo "***** $(date), $prompt: going to call 'purgeDFRobotUploads'" >> /home/pi/log/dfrobot_log.txt
        sudo -u www-data purgeDFRobotUploads
        # Going to upload the file to Google Drive using the 'drive' utility.
        # 'sudo -u www-data' is used here to behave as the exact same www-data user
        # as when the verification code was generated (using also sudo -u),
        # else Google will ask for a new verification code.
        # Apparently when Apache uses www-data it is different in a way.
        # To upload into the 'DFRobotUploads' folder, the -p option is used with the id of this folder.
        # When the 'DFRobotUploads' folder is changed, a new id has to be provided.
        # This id can be obtained using 'drive list -t DFRobotUploads'.
        # The uploaded file has a distinctive name to enable finding and removing it again with the 'drive' utility.
        echo "***** $(date), $prompt: going to call 'drive' to upload videofile" >> /home/pi/log/dfrobot_log.txt
        sudo -u www-data drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/DFRobotUploads/dfrobot_pivid.mp4 >> /home/pi/log/dfrobot_log.txt 2>&1 &
        echo "***** $(date), $prompt: going to call 'drive' to upload logfile" >> /home/pi/log/dfrobot_log.txt
        sudo -u www-data drive upload -p 0B1WIoyfCgifmMUwwcXNqeDl6U1k -f /home/pi/log/dfrobot_log.txt >> /home/pi/log/dfrobot_log.txt 2>&1 &
    elif [ "${1}" == "home" ]
    then
        echo "***** $(date), $prompt: 'home' command received" >> /home/pi/log/dfrobot_log.txt
    elif [ "${1}" == "forward" ]
    then
        echo "***** $(date), $prompt: 'forward' command received" >> /home/pi/log/dfrobot_log.txt
        i2c_cmd 1 ${2} > /dev/null 2>&1
    elif [ "${1}" == "backward" ]
    then
        echo "***** $(date), $prompt: 'backward' command received" >> /home/pi/log/dfrobot_log.txt
        i2c_cmd 2 ${2} > /dev/null 2>&1
    elif [ "${1}" == "left" ]
    then
        echo "***** $(date), $prompt: 'left' command received" >> /home/pi/log/dfrobot_log.txt
        i2c_cmd 3 ${2} > /dev/null 2>&1
    elif [ "${1}" == "right" ]
    then
        echo "***** $(date), $prompt: 'right' command received" >> /home/pi/log/dfrobot_log.txt
        i2c_cmd 4 ${2} > /dev/null 2>&1
    elif [ "${1}" == "cam-up" ]
    then
        echo "***** $(date), $prompt: 'cam-up' command received" >> /home/pi/log/dfrobot_log.txt
        i2c_cmd 10 > /dev/null 2>&1
    elif [ "${1}" == "cam-down" ]
    then
        echo "***** $(date), $prompt: 'cam-down' command received" >> /home/pi/log/dfrobot_log.txt
        i2c_cmd 11 > /dev/null 2>&1
    elif [ "${1}" == "light-on" ]
    then
        echo "***** $(date), $prompt: 'light-on' command received" >> /home/pi/log/dfrobot_log.txt
        i2c_cmd 20 > /dev/null 2>&1
    elif [ "${1}" == "light-off" ]
    then
        echo "***** $(date), $prompt: 'light-off' command received" >> /home/pi/log/dfrobot_log.txt
        i2c_cmd 21 > /dev/null 2>&1
    elif [ "${1}" == "status" ]
    then
        echo "***** $(date), $prompt: 'status' command received" >> /home/pi/log/dfrobot_log.txt
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


