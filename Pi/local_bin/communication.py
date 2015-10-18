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
globInteractive = False
globDoHomeRun = False
globCmd = ''
globDoMotionDetection = False
globWhatsAppSendPicture = False


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
        global globWhatsAppMsgIn, globWhatsAppMsgInAvailable, globWhatsAppMsgInAvailableLock
        #send receipt otherwise we keep receiving the same message over and over
        
        # Use 'hasattr' to protect against video and audio messages, which do not have a 'getBody' attribute.
        if hasattr(messageProtocolEntity, 'getBody'):
            # Keep critical section as short as possible.
            globWhatsAppMsgInAvailableLock.acquire()
            globWhatsAppMsgIn = messageProtocolEntity.getBody()
            globWhatsAppMsgInAvailable = True
            globWhatsAppMsgInAvailableLock.release()

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
    global globWhatsAppContinue, globWhatsAppRestart
    global globWhatsAppMsgIn, globWhatsAppMsgInAvailable, globWhatsAppMsgInAvailableLock
    global globWhatsAppMsgOut, globWhatsAppMsgOutType, globIWhatsAppImgOut, globWhatsAppMsgOutAvailable, globWhatsAppMsgOutAvailableLock
    global globDoMotionDetection, globWhatsAppSendPicture

    # YowAxolotlLayer added to prevent 'Unimplemented notification type "encrypt"' crash.
    layers=(SendReceiveLayer,)+(YOWSUP_PROTOCOL_LAYERS_FULL,YowAxolotlLayer)+YOWSUP_CORE_LAYERS
    
    stack = YowStack(layers)
    stack.setProp(YowAuthenticationProtocolLayer.PROP_CREDENTIALS, credentials())         #setting credentials
    stack.setProp(YowNetworkLayer.PROP_ENDPOINT, YowConstants.ENDPOINTS[0])    #whatsapp server address
    stack.setProp(YowCoderLayer.PROP_DOMAIN, YowConstants.DOMAIN)
    stack.setProp(YowCoderLayer.PROP_RESOURCE, env.CURRENT_ENV.getResource())          #info about us as WhatsApp client
    stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))   #sending the connect signal
    while globWhatsAppContinue:
        try:
            globWhatsAppMsgOutAvailableLock.acquire()
            if globWhatsAppMsgOutAvailable:
                # Copy to keep critical section as short as possible.
                msgOutType = globWhatsAppMsgOutType
                if msgOutType == 'Image':
                    # Copy image to whatsapp_client_img.jpg so this image can be sent without another thread
                    # overwriting the image.
                    imgOut = '/home/pi/DFRobotUploads/whatsapp_client_img.jpg'
                    shutil.copy(globIWhatsAppImgOut, imgOut)
                msgOut = globWhatsAppMsgOut
                globWhatsAppMsgOutAvailable = False
                globWhatsAppMsgOutAvailableLock.release()
                if msgOutType == 'Image':
                    messages = [(["31613484264", imgOut, msgOut])]
                else:
                    messages = [(["31613484264", '', msgOut])]
                stack.setProp(SendReceiveLayer.PROP_MESSAGES,messages)
                stack.broadcastEvent(YowLayerEvent(SendReceiveLayer.EVENT_SEND_MESSAGE))
            else:
                globWhatsAppMsgOutAvailableLock.release()
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
                globWhatsAppSendPicture = True;
            elif re.search('hi', msg, re.IGNORECASE):
                sendWhatsAppMsg('hi there!')
            elif re.search('.*feel.*', msg, re.IGNORECASE):
                level = own_util.getBatteryLevel()
                if level > 190:
                    sendWhatsAppMsg('I feel great, my energy level is ' + str(level))
                elif level > 170:
                    sendWhatsAppMsg('I feel ok, my energy level is ' + str(level))
                else:
                    sendWhatsAppMsg('I feel a bit weak, my energy level is ' + str(level))
            elif re.search('how are you', msg, re.IGNORECASE):
                sendWhatsAppMsg('I am fine, thx for asking!')
            elif re.search('battery', msg, re.IGNORECASE):
                charging = own_util.checkCharging()
                if charging == True:
                    sendWhatsAppMsg('I am charging, my battery level is ' + str(own_util.getBatteryLevel()))
                else:
                    sendWhatsAppMsg('I am not charging, my battery level is ' + str(own_util.getBatteryLevel()))
            elif re.search('awake', msg, re.IGNORECASE):
                sendWhatsAppMsg('I am awake for ' + own_util.getUptime())
            elif re.search('joke', msg, re.IGNORECASE):
                sendWhatsAppMsg('\'What does your robot do, Sam?\' .......... \'It collects data about the surrounding environment, then discards it and drives into walls\'')
            elif msg != '':
                sendWhatsAppMsg('no comprendo: ' + msg)

        except Exception,e:
            logging.getLogger("MyLog").info('whatsAppClient exception: ' + str(e))
            # Signal to restart this whatsAppClient thread.
            globWhatsAppRestart = True
    try:
        stack.broadcastEvent(YowLayerEvent(SendReceiveLayer.EVENT_DISCONNECT))
    except Exception,e:
        logging.getLogger("MyLog").info('whatsAppClient exception: ' + str(e))


def startWhatsAppClient():
    global globWhatsAppContinue, globWhatsAppRestart
    global globWhatsAppMsgIn, globWhatsAppMsgInAvailable, globWhatsAppMsgInAvailableLock
    global globWhatsAppMsgOut, globWhatsAppMsgOutAvailable, globWhatsAppMsgOutAvailableLock
    logging.getLogger("MyLog").info('going to start whatsAppClient')
    globWhatsAppMsgInAvailableLock = thread.allocate_lock()
    globWhatsAppMsgOutAvailableLock = thread.allocate_lock()
    globWhatsAppContinue = True
    globWhatsAppRestart = False
    globWhatsAppMsgInAvailable = globWhatsAppMsgOutAvailable = False
    thread.start_new_thread(whatsAppClient, ())
    # The delay below is to make sure we have connections.
    time.sleep(1.0)


def stopWhatsAppClient():
    global globWhatsAppContinue
    logging.getLogger("MyLog").info('going to stop whatsAppClient')
    globWhatsAppContinue = False
    # Delay to make sure whatsAppClient is stopped. This delay must be sufficient large to make sure
    # the 'while globWhatsAppContinue:' statement is reached in the whatsAppClient() thread.
    # Note that the whatsAppClient() thread contains a sleep of 1 sec.
    time.sleep(5.0)


def checkWhatsAppClient():
    global globWhatsAppRestart
    if globWhatsAppRestart == True:
        logging.getLogger("MyLog").info('going to restart whatsAppClient')
        stopWhatsAppClient()
        startWhatsAppClient()


def sendWhatsAppMsg(msg):
    global globWhatsAppMsgOut, globWhatsAppMsgOutType, globWhatsAppMsgOutAvailable, globWhatsAppMsgOutAvailableLock
    # Keep critical section as short as possible.
    logging.getLogger("MyLog").info('going to send WhatsApp message "' + msg + '"')
    globWhatsAppMsgOutAvailableLock.acquire()
    globWhatsAppMsgOut = msg
    globWhatsAppMsgOutType = 'Text'
    globWhatsAppMsgOutAvailable = True
    globWhatsAppMsgOutAvailableLock.release()


def sendWhatsAppImg(img, caption):
    global globWhatsAppMsgOut, globWhatsAppMsgOutType, globIWhatsAppImgOut, globWhatsAppMsgOutAvailable, globWhatsAppMsgOutAvailableLock
    # Keep critical section as short as possible.
    globWhatsAppMsgOutAvailableLock.acquire()
    logging.getLogger("MyLog").info('going to send WhatsApp image ' + img + ' with caption "' + caption + '"')
    # Copy img to whatsapp_img.jpg so this thread can continue preparing the next img.
    # The whatsAppClient thread will copy whatsapp_img.jpg to whatsapp_client_img.jpg using the same
    # critical section lock. This way it is guaranteed that whatsapp_client_img.jpg will not be overwritten
    # by this thread while it is sent by the whatsAppClient thread.
    globIWhatsAppImgOut = '/home/pi/DFRobotUploads/whatsapp_img.jpg'
    shutil.copy(img, globIWhatsAppImgOut)
    globWhatsAppMsgOut = caption
    globWhatsAppMsgOutType = 'Image'
    globWhatsAppMsgOutAvailable = True
    globWhatsAppMsgOutAvailableLock.release()


def receiveWhatsAppMsg():
    global globWhatsAppMsgIn, globWhatsAppMsgInAvailable, globWhatsAppMsgInAvailableLock
    msg = ''
    # Keep critical section as short as possible.
    globWhatsAppMsgInAvailableLock.acquire()
    if globWhatsAppMsgInAvailable:
        msg = globWhatsAppMsgIn
        globWhatsAppMsgInAvailable = False
        logging.getLogger("MyLog").info('WhatsApp message received: "' + msg + '"')
        globWhatsAppMsgInAvailableLock.release()
    else:
        globWhatsAppMsgInAvailableLock.release()
    return msg


def socketClient():
    global globSocketMsgIn, globSocketMsgInAvailable, globSocketMsgInAvailableLock
    global globSocketMsgOut, globSocketMsgOutAvailable, globSocketMsgOutAvailableLock
    global globInteractive, globDoHomeRun
    global globCmd
    s = socket.socket()         # Create a socket object.
    port = 12345                # Reserve a port for your service.
    s.bind(('localhost', port)) # Bind to localhost and port.
    # Set socket timeout to prevent the s.accept() call from blocking.
    # Instead it will generate a 'timed out' exception.
    s.settimeout(1.0)
    s.listen(5)                 # Now wait for client connection.
    interactiveInactivityCount = 0
    while True:
        try:
            # Establish connection.
            # We have set s.settimeout(...) which means s.accept() will generate a 'timed out' exception
            # when there is no connection within the timeout time.
            # This way we can still do some processing.
            c = None
            try:
                c, addr = s.accept()    # Establish connection with client.
            except Exception,e:
                pass
            
            # Increase interactive inactivity count.
            interactiveInactivityCount = interactiveInactivityCount + 1
            if interactiveInactivityCount > 60:
                # Interactive is inactive, set globInteractive to False so the server can take appropriate action,
                # for example continue motion detection.
                globInteractive = False
            
            if c is None:
                # No connection, continue with next iteration.
                continue
        
            # Connection is made, so interactive mode is active,
            # set globInteractive to True so the server can take appropriate action, for example stop motion detection.
            globInteractive = True
            # Reset interactive inacivity count because there is activity.
            interactiveInactivityCount = 0

            # Receive message.
            msg = c.recv(1024)      # Will receive any message with a maximum length of 1024 characters.
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
            if re.search('home-start', msg, re.IGNORECASE):
                globCmd = 'home-start'
                globDoHomeRun = True
            elif re.search('home-stop', msg, re.IGNORECASE):
                globCmd = 'home-stop'
                globDoHomeRun = False
            elif re.search('status', msg, re.IGNORECASE):
                # Get status for webpage.
                statusForWebPage = '<br>' + own_util.getWifiStatus() + '<br>' + 'uptime: ' + own_util.getUptime() + '<br>' + 'battery: ' + str(own_util.getBatteryLevel()) + ' (154 = 6V)'
                sendSocketMsg(statusForWebPage)
            else:
                # Handle the interactive commands which take at most a few seconds and do not change the mode.
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
                c.send(msg + '\n')
            else:
                globSocketMsgOutAvailableLock.release()
    
        except Exception,e:
            logging.getLogger("MyLog").info('socketClient exception: ' + str(e))


def startSocketClient():
    global globSocketMsgIn, globSocketMsgInAvailable, globSocketMsgInAvailableLock
    global globSocketMsgOut, globSocketMsgOutAvailable, globSocketMsgOutAvailableLock
    logging.getLogger("MyLog").info('going to start socketClient')
    globSocketMsgInAvailableLock = thread.allocate_lock()
    globSocketMsgOutAvailableLock = thread.allocate_lock()
    globSocketMsgInAvailable = False
    globSocketMsgOutAvailable = False
    thread.start_new_thread(socketClient, ())


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
