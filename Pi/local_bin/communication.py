#!/usr/bin/python

import os
import shutil
import sys
import thread
import socket
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import re
import logging
import time
import own_util
import personal_assistant
import telepot
import secret


# Global variables
globWebSocketInteractive = False
globWebSocketInMsg = ''


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
            
            # Handle messages.
            msg = receiveTelegramMsg()
            # Check for reboot command coming in via Telegram right here, other parts of the code might not run anymore.
            if msg == "reboot":
                own_util.ownReboot("reboot requested by user")
                msg = ""  # Indicate message is handled.
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


def statusUpdateThread():
    while True:
        own_util.updateUptime()
        own_util.updatePowerInfo()
        own_util.updateWifiStatus()
        own_util.updateDistanceInfo()
        # Wait for next status update. Keep this sleep time equal to the personal_assistant.waitForProximity() update time.
        time.sleep(0.5)


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    previousExtPowerAvailable = False
    previousIntPowerLevel = 0
    previousDistance = 0
    previousWifiLevel = 0
    def open(self):
        logging.getLogger("MyLog").info("New websocket connection")
    
    def on_message(self, message):
        global globWebSocketInteractive, globWebSocketInMsg
        globWebSocketInteractive = True
        globWebSocketInMsg = str(message) # message received is Unicode. Convert back to ASCII.
        # Check for reboot command coming in via the websocket right here, other parts of the code might not run anymore.
        if globWebSocketInMsg == "reboot":
            own_util.ownReboot("reboot requested by user")
            globWebSocketInMsg = ""  # Indicate message is handled.
        # During a Home run the standard command handler in run_dfrobot.py does not run.
        # So we indicate here a stop command is received by setting own_util.globStop to True.
        if globWebSocketInMsg == "stop":
            own_util.globStop = True
        # Send back message
        if own_util.globExtPowerAvailable != self.previousExtPowerAvailable or own_util.globIntPowerLevel != self.previousIntPowerLevel or own_util.globWifiLevel != self.previousWifiLevel or own_util.globDistance != self.previousDistance:
            if own_util.globExtPowerAvailable == True:
                powerStr = "ext pow: "
            else:
                powerStr = "bat: "
            self.write_message(powerStr + str(own_util.globIntPowerLevel) + "<br>" + str(own_util.globWifiLevel) + "<br>dis: " + str(own_util.globDistance))
            self.previousExtPowerAvailable = own_util.globExtPowerAvailable
            self.previousIntPowerLevel = own_util.globIntPowerLevel
            self.previousDistance = own_util.globDistance
            self.previousWifiLevel = own_util.globWifiLevel
    
    def on_close(self):
        logging.getLogger("MyLog").info("Websocket closed")
    
    def check_origin(self, origin):
        return True


def startWebSocketServer():
    application = tornado.web.Application([(r'/ws', WebSocketHandler),])
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(44447)
    myIP = socket.gethostbyname(socket.gethostname())
    logging.getLogger("MyLog").info('*** Websocket Server Started at %s***' % myIP)
    thread.start_new_thread(tornado.ioloop.IOLoop.instance().start, ())



