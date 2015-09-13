#!/usr/bin/python

import os
import shutil
import sys
import thread
import re
import logging
import time
import own_util

from yowsup.layers                                      import YowLayerEvent
from yowsup.layers.network                              import YowNetworkLayer
from yowsup.layers.interface                            import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers.auth                                 import YowAuthenticationProtocolLayer, AuthError
from yowsup.layers.protocol_media.protocolentities      import *
from yowsup.layers.protocol_media.mediauploader         import MediaUploader
from yowsup.layers.protocol_messages.protocolentities   import TextMessageProtocolEntity
from yowsup.layers.protocol_receipts.protocolentities   import OutgoingReceiptProtocolEntity
from yowsup.layers.protocol_acks.protocolentities       import OutgoingAckProtocolEntity
from yowsup.layers.protocol_messages                    import YowMessagesProtocolLayer
from yowsup.layers.protocol_receipts                    import YowReceiptProtocolLayer
from yowsup.layers.protocol_acks                        import YowAckProtocolLayer
from yowsup.layers.protocol_presence.protocolentities   import *
from yowsup.layers.coder                                import YowCoderLayer
from yowsup.layers.axolotl                              import YowAxolotlLayer
from yowsup.common                                      import YowConstants
from yowsup.stacks                                      import YowStack, YOWSUP_CORE_LAYERS, YOWSUP_PROTOCOL_LAYERS_FULL
from yowsup                                             import env

# Global variables
globDoMotionDetection = False
globSendPicture = False


class Disconnect(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class MediaDiscover(object):
    EXT_IMAGE=['jpg','png']
    EXT_AUDIO=['mp3','wav','aac','wma','ogg','oga']
    EXT_VIDEO=['mp4']
    
    @staticmethod
    def getMediaType(path):
        for ext in MediaDiscover.EXT_IMAGE:
            if path.endswith(ext):
                return "image"
        for ext in MediaDiscover.EXT_VIDEO:
            if path.endswith(ext):
                return "video"
        for ext in MediaDiscover.EXT_AUDIO:
            if path.endswith(ext):
                return "audio"
        return None


# SendReceiveLayer is the custom upper layer for sending and receiving messages.
class SendReceiveLayer(YowInterfaceLayer):
    PROP_MESSAGES = 'org.openwhatsapp.yowsup.prop.sendclient.queue'  # list of (jid, path) tuples
    # Custom events which can be triggered from outside with stack.broadcastEvent().
    EVENT_SEND_MESSAGE = "send_message"
    EVENT_DISCONNECT = "disconnect"
    
    def __init__(self):
        super(SendReceiveLayer,self).__init__()
        self.MEDIA_TYPE=None
        self.ackQueue=[]
    
    def disconnect(self,result):
        self.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))
        raise Disconnect(result)
    
    # Handle custom events.
    def onEvent(self, layerEvent):
        # Event to send a message.
        if layerEvent.getName() == SendReceiveLayer.EVENT_SEND_MESSAGE:
            self.main()
        # Event to disconnect.
        elif layerEvent.getName() == SendReceiveLayer.EVENT_DISCONNECT:
            self.disconnect("SendReceiveLayer.EVENT_DISCONNECT")

    @ProtocolEntityCallback("message")
    def onMessage(self, messageProtocolEntity):
        global globMsgIn, globMsgInAvailable, globMsgInAvailableLock
        #send receipt otherwise we keep receiving the same message over and over
        
        # Use 'hasattr' to protect against video and audio messages, which do not have a 'getBody' attribute.
        if hasattr(messageProtocolEntity, 'getBody'):
            # Keep critical section as short as possible.
            globMsgInAvailableLock.acquire()
            globMsgIn = messageProtocolEntity.getBody()
            globMsgInAvailable = True
            globMsgInAvailableLock.release()

            receipt = OutgoingReceiptProtocolEntity(messageProtocolEntity.getId(), messageProtocolEntity.getFrom(), 'read', messageProtocolEntity.getParticipant())
            self.toLower(receipt)
    
    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        ack = OutgoingAckProtocolEntity(entity.getId(), "receipt", entity.getType(), entity.getFrom())
        self.toLower(ack)
   
    @ProtocolEntityCallback('success')
    def onSuccess(self,entity):
        entity = AvailablePresenceProtocolEntity()
        self.toLower(entity)
        #self.main()
    
    @ProtocolEntityCallback('ack')
    def onAck(self,entity):
        if entity.getId() in self.ackQueue:
            self.ackQueue.pop(self.ackQueue.index(entity.getId()))
#        if not len(self.ackQueue):
#            print 'going to disconnect'
#            self.disconnect("MEDIA SENT")

    def onRequestUploadResult(self,jid,filePath,resultRequestUploadIqProtocolEntity,requestUploadIqProtocolEntity,caption = None):
        if resultRequestUploadIqProtocolEntity.isDuplicate():
            if self.MEDIA_TYPE=="image":
                self.doSendImage(filePath,resultRequestUploadIqProtocolEntity.getUrl(),jid,resultRequestUploadIqProtocolEntity.getIp(),caption)
            elif self.MEDIA_TYPE=="video":
                self.doSendVideo(filePath,resultRequestUploadIqProtocolEntity.getUrl(),jid,resultRequestUploadIqProtocolEntity.getIp())
            elif self.MEDIA_TYPE=="audio":
                self.doSendAudio(filePath,resultRequestUploadIqProtocolEntity.getUrl(),jid,resultRequestUploadIqProtocolEntity.getIp())
        else:
            successFn = lambda filePath, jid, url: self.onUploadSuccess(filePath, url, jid, resultRequestUploadIqProtocolEntity.getIp(), caption)
            mediaUploader=MediaUploader(jid,self.getOwnJid(),filePath,resultRequestUploadIqProtocolEntity.getUrl(),resultRequestUploadIqProtocolEntity.getResumeOffset(),successFn,self.onUploadError,self.onUploadProgress,async=False)
            mediaUploader.start()

    def onRequestUploadError(self,jid,path,errorRequestUploadIqProtocolEntity,requestUploadIqProtocolEntity):
        self.disconnect("ERROR REQUEST")
    
    def onUploadSuccess(self,filePath,url,jid,ip=None,caption=None):
        if self.MEDIA_TYPE=="image":
            self.doSendImage(filePath,url,jid,ip,caption)
        elif self.MEDIA_TYPE=="video":
            self.doSendVideo(filePath,url,jid)
        elif self.MEDIA_TYPE=="audio":
            self.doSendAudio(filePath,url,jid)

    def onUploadError(self,filePath,jid,url):
        self.disconnect("ERROR UPLOAD")
    
    def onUploadProgress(self,filePath,jid,url,progress):
        #print(progress)
        pass

    def doSendImage(self,filePath,url,to,ip=None, caption=None):
        entity=ImageDownloadableMediaMessageProtocolEntity.fromFilePath(filePath,url,ip,to,caption=caption)
        self.toLower(entity)
    
    def doSendVideo(self,filePath,url,to,ip=None):
        entity=DownloadableMediaMessageProtocolEntity.fromFilePath(filePath,url,"video",ip,to)
        self.toLower(entity)
    
    def doSendAudio(self,filePath,url,to,ip=None):
        entity=DownloadableMediaMessageProtocolEntity.fromFilePath(filePath,url,"audio",ip,to)
        self.toLower(entity)
    
    def main(self):
        for target in self.getProp(self.__class__.PROP_MESSAGES,[]):
            jid,path,caption=target
            jid='%s@s.whatsapp.net' % jid
            if path != '':
                self.MEDIA_TYPE=MediaDiscover.getMediaType(path)
                if self.MEDIA_TYPE is None:
                    self.disconnect("ERROR MEDIA")
                entity = None
                if self.MEDIA_TYPE=="image":
                    entity=RequestUploadIqProtocolEntity(RequestUploadIqProtocolEntity.MEDIA_TYPE_IMAGE,filePath=path)
                elif self.MEDIA_TYPE=="video":
                    entity=RequestUploadIqProtocolEntity(RequestUploadIqProtocolEntity.MEDIA_TYPE_VIDEO,filePath=path)
                elif self.MEDIA_TYPE=="audio":
                    entity=RequestUploadIqProtocolEntity(RequestUploadIqProtocolEntity.MEDIA_TYPE_AUDIO,filePath=path)
                successFn=lambda successEntity, originalEntity: self.onRequestUploadResult(jid,path,successEntity,originalEntity,caption)
                errorFn=lambda errorEntity,originalEntity: self.onRequestUploadError(jid,path,errorEntity,originalEntity)
                self._sendIq(entity,successFn,errorFn)
            else:
                outgoingMessageProtocolEntity = TextMessageProtocolEntity(caption, to = jid)
                self.toLower(outgoingMessageProtocolEntity)


def credentials():
    return "31629394320","ZIkoLpfIWcPDkYILVKdrrJo7md8=" # Put your credentials here!


def whatsAppClient():
    global globContinueWhatsApp, globRestartWhatsApp
    global globMsgIn, globMsgInAvailable, globMsgInAvailableLock
    global globMsgOut, globMsgOutType, globImgOut, globMsgOutAvailable, globMsgOutAvailableLock
    global globDoMotionDetection, globSendPicture

    # YowAxolotlLayer added to prevent 'Unimplemented notification type "encrypt"' crash.
    layers=(SendReceiveLayer,)+(YOWSUP_PROTOCOL_LAYERS_FULL,YowAxolotlLayer)+YOWSUP_CORE_LAYERS
    
    stack = YowStack(layers)
    stack.setProp(YowAuthenticationProtocolLayer.PROP_CREDENTIALS, credentials())         #setting credentials
    stack.setProp(YowNetworkLayer.PROP_ENDPOINT, YowConstants.ENDPOINTS[0])    #whatsapp server address
    stack.setProp(YowCoderLayer.PROP_DOMAIN, YowConstants.DOMAIN)
    stack.setProp(YowCoderLayer.PROP_RESOURCE, env.CURRENT_ENV.getResource())          #info about us as WhatsApp client
    stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))   #sending the connect signal
    while globContinueWhatsApp:
        try:
            globMsgOutAvailableLock.acquire()
            if globMsgOutAvailable:
                # Copy to keep critical section as short as possible.
                msgOutType = globMsgOutType
                if msgOutType == 'Image':
                    # Copy image to whatsapp_client_img.jpg so this image can be sent without another thread
                    # overwriting the image.
                    imgOut = '/home/pi/DFRobotUploads/whatsapp_client_img.jpg'
                    shutil.copy(globImgOut, imgOut)
                msgOut = globMsgOut
                globMsgOutAvailable = False
                globMsgOutAvailableLock.release()
                if msgOutType == 'Image':
                    messages = [(["31613484264", imgOut, msgOut])]
                else:
                    messages = [(["31613484264", '', msgOut])]
                stack.setProp(SendReceiveLayer.PROP_MESSAGES,messages)
                stack.broadcastEvent(YowLayerEvent(SendReceiveLayer.EVENT_SEND_MESSAGE))
            else:
                globMsgOutAvailableLock.release()
            # stack.loop() will call asyncore.loop() for an asynchronous I/O (socket) polling loop,
            # to poll for WhatsApp I/O. WhatsApp uses non-SSL data over SSL port 443.
            # The count parameter indicates the number of passes of the polling loop for each I/O channel.
            # The timeout argument sets the timeout parameter for the appropriate select() or poll() call,
            # measured in seconds. It indicates the wait time (blocking) for an I/O channel (file descriptor)
            # to become ready.
            stack.loop(timeout = 1.0, count=1)
            # Sleep to save cpu.
            time.sleep(1.0)
            # Update charging status of batteries.
            own_util.checkCharging()

            # Handle messages.
            msg = receiveWhatsAppMsg()
            if re.search('.*motion.*on.*', msg, re.IGNORECASE):
                globDoMotionDetection = True
                sendWhatsAppMsg('motion detection is on')
            elif re.search('.*motion.*off.*', msg, re.IGNORECASE):
                globDoMotionDetection = False
                sendWhatsAppMsg('motion detection is off')
            elif re.search('picture', msg, re.IGNORECASE):
                globSendPicture = True;
            elif re.search('hi', msg, re.IGNORECASE):
                sendWhatsAppMsg('hi there!')
            elif re.search('.*feel.*', msg, re.IGNORECASE):
                level = own_util.getBatteryLevel()
                if level != 'unknown':
                    if int(level) > 190:
                        sendWhatsAppMsg('I feel great, my energy level is ' + level)
                    elif int(level) > 170:
                        sendWhatsAppMsg('I feel ok, my energy level is ' + level)
                    else:
                        sendWhatsAppMsg('I feel a bit weak, my energy level is ' + level)
                else:
                    sendWhatsAppMsg('I am not sure, my energy level is unknown')
            elif re.search('how are you', msg, re.IGNORECASE):
                sendWhatsAppMsg('I am fine, thx for asking!')
            elif re.search('battery', msg, re.IGNORECASE):
                charging = own_util.checkCharging()
                if charging == True:
                    sendWhatsAppMsg('I am charging, my battery level is ' + own_util.getBatteryLevel())
                else:
                    sendWhatsAppMsg('I am not charging, my battery level is ' + own_util.getBatteryLevel())
            elif re.search('awake', msg, re.IGNORECASE):
                sendWhatsAppMsg('I am awake for ' + own_util.getUptime())
            elif re.search('joke', msg, re.IGNORECASE):
                sendWhatsAppMsg('\'What does your robot do, Sam?\' .......... \'It collects data about the surrounding environment, then discards it and drives into walls\'')
            elif msg != '':
                sendWhatsAppMsg('no comprendo: ' + msg)

        except Exception,e:
            logging.getLogger("MyLog").info('whatsAppClient exception: ' + str(e))
            # Signal to restart this whatsAppClient thread.
            globRestartWhatsApp = True
    try:
        stack.broadcastEvent(YowLayerEvent(SendReceiveLayer.EVENT_DISCONNECT))
    except Exception,e:
        logging.getLogger("MyLog").info('whatsAppClient exception: ' + str(e))


def startWhatsAppClient():
    global globContinueWhatsApp, globRestartWhatsApp
    global globMsgIn, globMsgInAvailable, globMsgInAvailableLock
    global globMsgOut, globMsgOutAvailable, globMsgOutAvailableLock
    logging.getLogger("MyLog").info('going to start whatsAppClient')
    globMsgInAvailableLock = thread.allocate_lock()
    globMsgOutAvailableLock = thread.allocate_lock()
    globContinueWhatsApp = True
    globRestartWhatsApp = False
    globMsgInAvailable = globMsgOutAvailable = False
    thread.start_new_thread(whatsAppClient, ())
    # The delay below is to make sure we have connections.
    time.sleep(1.0)


def stopWhatsAppClient():
    global globContinueWhatsApp
    logging.getLogger("MyLog").info('going to stop whatsAppClient')
    globContinueWhatsApp = False
    # Delay to make sure whatsAppClient is stopped. This delay must be sufficient large to make sure
    # the 'while globContinueWhatsApp:' statement is reached in the whatsAppClient() thread.
    # Note that the whatsAppClient() thread contains a sleep of 1 sec.
    time.sleep(5.0)


def checkWhatsAppClient():
    global globRestartWhatsApp
    if globRestartWhatsApp == True:
        logging.getLogger("MyLog").info('going to restart whatsAppClient')
        stopWhatsAppClient()
        startWhatsAppClient()


def sendWhatsAppMsg(msg):
    global globMsgOut, globMsgOutType, globMsgOutAvailable, globMsgOutAvailableLock
    # Keep critical section as short as possible.
    logging.getLogger("MyLog").info('going to send WhatsApp message "' + msg + '"')
    globMsgOutAvailableLock.acquire()
    globMsgOut = msg
    globMsgOutType = 'Text'
    globMsgOutAvailable = True
    globMsgOutAvailableLock.release()


def sendWhatsAppImg(img, caption):
    global globMsgOut, globMsgOutType, globImgOut, globMsgOutAvailable, globMsgOutAvailableLock
    # Keep critical section as short as possible.
    globMsgOutAvailableLock.acquire()
    logging.getLogger("MyLog").info('going to send WhatsApp image ' + img + ' with caption "' + caption + '"')
    # Copy img to whatsapp_img.jpg so this thread can continue preparing the next img.
    # The whatsAppClient thread will copy whatsapp_img.jpg to whatsapp_client_img.jpg using the same
    # critical section lock. This way it is guaranteed that whatsapp_client_img.jpg will not be overwritten
    # by this thread while it is sent by the whatsAppClient thread.
    globImgOut = '/home/pi/DFRobotUploads/whatsapp_img.jpg'
    shutil.copy(img, globImgOut)
    globMsgOut = caption
    globMsgOutType = 'Image'
    globMsgOutAvailable = True
    globMsgOutAvailableLock.release()


def receiveWhatsAppMsg():
    global globMsgIn, globMsgInAvailable, globMsgInAvailableLock
    msg = ''
    # Keep critical section as short as possible.
    globMsgInAvailableLock.acquire()
    if globMsgInAvailable:
        msg = globMsgIn
        globMsgInAvailable = False
        logging.getLogger("MyLog").info('WhatsApp message received: "' + msg + '"')
        globMsgInAvailableLock.release()
    else:
        globMsgInAvailableLock.release()
    return msg
