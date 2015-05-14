#!/bin/bash
# Start with a touch of this script to feed the watchdog daemon a.s.a.p.

prompt=$(basename $0)
# Reset the log file to zero length if the size gets too large.
if [ $(stat -c %s /home/pi/log/dfrobot_log.txt) -gt 1000000 ]
then
  echo -e "***** $(date), $prompt: START LOG  *****" > /home/pi/log/dfrobot_log.txt
else
  echo -e "\n***** $(date), $prompt: START LOG  *****" >> /home/pi/log/dfrobot_log.txt
fi

count=0

touch -m $0
while [ 1 ]
do
  # Start with a sleep to give network time to come up.
  sleep 10
  # Check for router and Android Wifi hotspot
  if [ "$(ping -c 1 -W 2 192.168.1.254 | grep '100% packet loss')" -a "$(ping -c 1 -W 2 192.168.43.1 | grep '100% packet loss')" ]
  then
    echo "***** $(date), $prompt: ping failed, going to restart network!" >> /home/pi/log/dfrobot_log.txt
    sudo ifconfig wlan0 down && sudo ifconfig wlan0 up
    sudo /etc/init.d/networking restart
    sudo dhclient wlan0
  else
    # Touch this script to feed the watchdog daemon.
    touch -m $0
    # Write to logfile every 5 minutes when ping is ok.
    if [ $count -ge 30 ]
    then
      echo "***** $(date), $prompt: ping ok" >> /home/pi/log/dfrobot_log.txt
      count=0
    fi
  fi
  count=$((count+1))
done
