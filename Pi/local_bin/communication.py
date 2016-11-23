#!/usr/bin/python

import os
import shutil
import sys
import thread
import socket
import re
import logging
import time
import own_util
import personal_assistant
import telepot
import secret


# Global variables
globInteractive = False
globDoHomeRun = False
globCmd = ''


def TelegramClient():
    global globTelegramContinue
    global globTelegramMsgOut, globTelegramMsgOutType, globITelegramMediaOut, globTelegramMsgOutAvailable, globTelegramMsgOutAvailableLock

    # Start Telegram bot and attach callback.
    telegramBot = telepot.Bot(secret.TelegramApiToken)
    telegramBot.message_loop(telegramCallback)
    while globTelegramContinue:
        try:
            globTelegramMsgOutAvailableLock.acquire()
            if globTelegramMsgOutAvailable:
                # Copy to keep critical section as short as possible.
                msgOutType = globTelegramMsgOutType
                if msgOutType == 'Image' or msgOutType == 'Video':
                    # Copy media file to Telegram_client_media.xxx so this image can be sent without another thread
                    # overwriting the media file.
                    mediaOut = '/home/pi/DFRobotUploads/Telegram_client_media' + os.path.splitext(globITelegramMediaOut)[1]
                    shutil.copy(globITelegramMediaOut, mediaOut)
                msgOut = globTelegramMsgOut
                globTelegramMsgOutAvailable = False
                globTelegramMsgOutAvailableLock.release()
                if msgOutType == 'Image':
                    telegramBot.sendPhoto(secret.TelegramChatId, open(mediaOut, "rb"), caption = msgOut)
                elif msgOutType == 'Video':
                    telegramBot.sendVideo(secret.TelegramChatId, open(mediaOut, "rb"), caption = msgOut)
                else:
                    telegramBot.sendMessage(secret.TelegramChatId, msgOut)
            else:
                globTelegramMsgOutAvailableLock.release()
            
            # Update charging status of batteries.
            own_util.checkCharging()

            # Handle messages.
            msg = receiveTelegramMsg()
            if msg != "":
                (intent,value) = personal_assistant.textToIntent(msg)
                response = personal_assistant.handleIntent(intent, value, "text")
                if response != "":
                    sendTelegramMsg(response)
        except Exception,e:
            logging.getLogger("MyLog").info('TelegramClient exception: ' + str(e))
            # Signal to restart this TelegramClient thread.
            globTelegramRestart = True


def telegramCallback(msg):
    global globTelegramMsgIn, globTelegramMsgInAvailable, globTelegramMsgInAvailableLock
    chat_id = msg['chat']['id']
    # Keep critical section as short as possible.
    globTelegramMsgInAvailableLock.acquire()
    globTelegramMsgIn = msg['text']
    globTelegramMsgInAvailable = True
    globTelegramMsgInAvailableLock.release()


def startTelegramClient():
    global globTelegramContinue
    global globTelegramMsgIn, globTelegramMsgInAvailable, globTelegramMsgInAvailableLock
    global globTelegramMsgOut, globTelegramMsgOutAvailable, globTelegramMsgOutAvailableLock
    logging.getLogger("MyLog").info('going to start TelegramClient')
    globTelegramMsgInAvailableLock = thread.allocate_lock()
    globTelegramMsgOutAvailableLock = thread.allocate_lock()
    globTelegramMsgInAvailable = globTelegramMsgOutAvailable = False
    globTelegramContinue = True
    thread.start_new_thread(TelegramClient, ())


def stopTelegramClient():
    global globTelegramContinue
    logging.getLogger("MyLog").info('going to stop TelegramClient')
    globTelegramContinue = False


def sendTelegramMsg(msg):
    global globTelegramMsgOut, globTelegramMsgOutType, globTelegramMsgOutAvailable, globTelegramMsgOutAvailableLock
    # Keep critical section as short as possible.
    logging.getLogger("MyLog").info('going to send Telegram message "' + msg + '"')
    globTelegramMsgOutAvailableLock.acquire()
    globTelegramMsgOut = msg
    globTelegramMsgOutType = 'Text'
    globTelegramMsgOutAvailable = True
    globTelegramMsgOutAvailableLock.release()


def sendTelegramImg(img, caption):
    global globTelegramMsgOut, globTelegramMsgOutType, globITelegramMediaOut, globTelegramMsgOutAvailable, globTelegramMsgOutAvailableLock
    # Keep critical section as short as possible.
    globTelegramMsgOutAvailableLock.acquire()
    logging.getLogger("MyLog").info('going to send Telegram image ' + img + ' with caption "' + caption + '"')
    # Copy img to Telegram_img.jpg so this thread can continue preparing the next img.
    # The TelegramClient thread will copy Telegram_img.jpg to Telegram_client_img.jpg using the same
    # critical section lock. This way it is guaranteed that Telegram_client_img.jpg will not be overwritten
    # by this thread while it is sent by the TelegramClient thread.
    globITelegramMediaOut = '/home/pi/DFRobotUploads/Telegram_img' + os.path.splitext(img)[1]
    shutil.copy(img, globITelegramMediaOut)
    globTelegramMsgOut = caption
    globTelegramMsgOutType = 'Image'
    globTelegramMsgOutAvailable = True
    globTelegramMsgOutAvailableLock.release()


def sendTelegramVideo(video, caption):
    global globTelegramMsgOut, globTelegramMsgOutType, globITelegramMediaOut, globTelegramMsgOutAvailable, globTelegramMsgOutAvailableLock
    # Keep critical section as short as possible.
    globTelegramMsgOutAvailableLock.acquire()
    logging.getLogger("MyLog").info('going to send Telegram video ' + video + ' with caption "' + caption + '"')
    # Copy video to Telegram_video.avi so this thread can continue preparing the next video.
    # The TelegramClient thread will copy Telegram_video.avi to Telegram_client_video.avi using the same
    # critical section lock. This way it is guaranteed that Telegram_client_video.avi will not be overwritten
    # by this thread while it is sent by the TelegramClient thread.
    globITelegramMediaOut = '/home/pi/DFRobotUploads/Telegram_video' + os.path.splitext(video)[1]
    shutil.copy(video, globITelegramMediaOut)
    globTelegramMsgOut = caption
    globTelegramMsgOutType = 'Video'
    globTelegramMsgOutAvailable = True
    globTelegramMsgOutAvailableLock.release()


def receiveTelegramMsg():
    global globTelegramMsgIn, globTelegramMsgInAvailable, globTelegramMsgInAvailableLock
    msg = ''
    # Keep critical section as short as possible.
    globTelegramMsgInAvailableLock.acquire()
    if globTelegramMsgInAvailable:
        msg = globTelegramMsgIn
        globTelegramMsgInAvailable = False
        logging.getLogger("MyLog").info('Telegram message received: "' + msg + '"')
        globTelegramMsgInAvailableLock.release()
    else:
        globTelegramMsgInAvailableLock.release()
    return msg


def socketServer():
    global globSocketMsgIn, globSocketMsgInAvailable, globSocketMsgInAvailableLock
    global globSocketMsgOut, globSocketMsgOutAvailable, globSocketMsgOutAvailableLock
    global globInteractive, globDoHomeRun
    global globCmd
    # We use a UDP socket here as we send small control commands and real time data.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)         # Create a socket object.
    port = 12345                # Reserve a port for your service.
    s.bind(('', port)) # Bind to any host and specific port.
    # Set socket timeout to prevent the s.accept() call from blocking.
    # Instead it will generate a 'timed out' exception.
    s.settimeout(1.0)
    interactiveInactivityCount = 0
    while True:
        try:
            # Establish connection.
            # We have set s.settimeout(...) which means s.recvfrom() will generate a 'timed out' exception
            # when there is no message received within the timeout time.
            # This way we can still do some processing.
            msg = None
            try:
                # Receive message.
                msg, addr = s.recvfrom(1024)  # Will receive any message with a maximum length of 1024 characters.
            except Exception,e:
                pass

            # Increase interactive inactivity count.
            interactiveInactivityCount = interactiveInactivityCount + 1
            if interactiveInactivityCount > 60:
                # Interactive is inactive, set globInteractive to False so the server can take appropriate action,
                # for example continue motion detection.
                globInteractive = False

            if not msg:
                # No message received, continue with next iteration.
                continue

            # Message is received, so interactive mode is active,
            # set globInteractive to True so the server can take appropriate action, for example stop motion detection.
            globInteractive = True
            # Reset interactive inacivity count because there is activity.
            interactiveInactivityCount = 0

            # Keep critical section as short as possible.
            globSocketMsgInAvailableLock.acquire()
            globSocketMsgIn = msg
            globSocketMsgInAvailable = True
            globSocketMsgInAvailableLock.release()

            # Handle messages.
            # receiveSocketMsg() which has a locking mechanism is used to handle the message.
            # Running in this thread this would not be needed but it might be in the future.
            msg = receiveSocketMsg()
            # First handle the commands which change the run mode. The mode is set here in this thread
            # so the mode can be changed or interrupted at any time in the other thread.
            # For all messages received send a message back as the other side might expect this.
            if re.search('home-start', msg, re.IGNORECASE):
                sendSocketMsg('ok')
                globCmd = 'home-start'
                globDoHomeRun = True
            elif re.search('home-stop', msg, re.IGNORECASE):
                sendSocketMsg('ok')
                globCmd = 'home-stop'
                globDoHomeRun = False
            elif re.search('status', msg, re.IGNORECASE):
                # Get status for webpage.
                if own_util.checkCharging() == True:
                    chargingStr = 'charging'
                else:
                    chargingStr = 'not charging'
                statusForWebPage = '<br>' + own_util.getWifiStatus() + '<br>' + 'uptime: ' + own_util.getUptime() + '<br>' + 'battery: ' + str(own_util.getBatteryLevel()) + ' (154 = 6V), ' + chargingStr
                sendSocketMsg(statusForWebPage)
            elif re.search('get_distance', msg, re.IGNORECASE):
                distance = own_util.runShellCommandWait('sudo /usr/local/bin/own_gpio.py --us_sensor 1')
                sendSocketMsg(distance)
            else:
                # Handle the interactive commands which take at most a few seconds and do not change the mode.
                sendSocketMsg('ok')
                m = re.search('(.*)', msg, re.IGNORECASE)
                if m is not None:
                    globCmd = m.group(1)

            # Send message.
            # This must be done at the end of this loop iteration because one iteration consists of
            # a 'read message' - 'compose response' - 'send response' sequence.
            # This because the client expects an immediate answer otherwise it will block.
            # Keep critical section as short as possible.
            globSocketMsgOutAvailableLock.acquire()
            if globSocketMsgOutAvailable == True:
                msg = globSocketMsgOut
                globSocketMsgOutAvailable = False
                globSocketMsgOutAvailableLock.release()
                # Add new line as other side will stop reading after a newline.
                s.sendto(msg + '\n', addr)
            else:
                globSocketMsgOutAvailableLock.release()

        except Exception,e:
            logging.getLogger("MyLog").info('socketServer exception: ' + str(e))


def startSocketServer():
    global globSocketMsgIn, globSocketMsgInAvailable, globSocketMsgInAvailableLock
    global globSocketMsgOut, globSocketMsgOutAvailable, globSocketMsgOutAvailableLock
    logging.getLogger("MyLog").info('going to start socketServer')
    globSocketMsgInAvailableLock = thread.allocate_lock()
    globSocketMsgOutAvailableLock = thread.allocate_lock()
    globSocketMsgInAvailable = False
    globSocketMsgOutAvailable = False
    thread.start_new_thread(socketServer, ())


def receiveSocketMsg():
    global globSocketMsgIn, globSocketMsgInAvailable, globSocketMsgInAvailableLock
    msg = ''
    # Keep critical section as short as possible.
    globSocketMsgInAvailableLock.acquire()
    if globSocketMsgInAvailable:
        msg = globSocketMsgIn
        globSocketMsgInAvailable = False
        logging.getLogger("MyLog").info('Socket message received: "' + msg + '"')
        globSocketMsgInAvailableLock.release()
    else:
        globSocketMsgInAvailableLock.release()
    return msg


def sendSocketMsg(msg):
    global globSocketMsgOut, globSocketMsgOutAvailable, globSocketMsgOutAvailableLock
    # Keep critical section as short as possible.
    globSocketMsgOutAvailableLock.acquire()
    globSocketMsgOut = msg
    globSocketMsgOutAvailable = True
    logging.getLogger("MyLog").info('Socket message sent: "' + msg + '"')
    globSocketMsgOutAvailableLock.release()
