#!/usr/bin/python
import time
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import own_util

Broker = "broker.hivemq.com"

sub_topic = "ArduinoIoT/Eindhoven/Light/Set"        # receive messages on this topic
pub_topic = "ArduinoIoT/Eindhoven/Light/Heartbeat"  # send messages to this topic


############### MQTT section ##################

# when connecting to mqtt do this;

def on_connect(client, userdata, flags, rc):
    #print("Connected with result code "+str(rc))
    client.subscribe(sub_topic)

# when receiving a mqtt message do this;

def on_message(client, userdata, msg):
    try:
        message = str(msg.payload)
        #print(msg.topic+" "+message)
        hue, brightness = str(msg.payload).split(" ")
        if brightness == "0":
            onoff = "false"
        else:
            onoff = "true"
        stdOutAndErr = own_util.runShellCommandWait('curl -H "Accept: application/json" -X PUT --data \'{"on":' + onoff + ',"hue":' + hue + ',"sat":255,"bri":' + brightness + '}\' http://192.168.1.228/api/fKNuWZjURUSJKJxHSqI03SoF1ekvGX1GnyZdbsJd/lights/1/state')
    except Exception as e:  # It will arrive here when there are no two values to unpack (hue, brightness).
        #print "exception: " + str(e)
        pass  # As this is a demo, never quit.


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(Broker, 1883, 60)
client.loop_start()

count = 0;
while True:
    count = count + 1
    client.publish(pub_topic, str(count))
    time.sleep(1)
