#include <Wire.h>
#include <Servo.h>
#define SLAVE_ADDRESS 0x04

//This motor shield use Pin 6,5,7,4 to control the motor
// Simply connect your motors to M1+,M1-,M2+,M2-
// Upload the code to Arduino/Roboduino.
// Through serial monitor, type 'a','s', 'w','d','x' to control the motor.
// www.dfrobot.com
// Last modified on 24/12/2009

int DIR1 = 7; // left motor
int PWM1 = 6; // left motor
int DIR2 = 4; // right motor
int PWM2 = 5; // right motor
int EXT_POWER_SENSE_PIN = A0;
int INT_POWER_SENSE_PIN = A1;
int EXT_POWER_SWITCH_PIN = 2;
int LIGHT_PIN = 3;
int SERVO_CAMERA_PIN = 8;

int i2cCommand = 0;         // global variable for receiving command from I2C
int i2cParameters[10];      // global array for receiving parameters from I2C
int i2cParameterCount = 0;  // global variable for keeping I2C parameter count
int i2cDataByteToSend = 0;  // global variable to send back over I2C in receiveData() callback fucntion.

Servo myServo;  // create servo camera object to control a servo
int servoCameraPos;   // variable to store the servo camera position

// callback for received data
void receiveData(int byteCount)
{
  int i2cData;
  while (Wire.available()) {
    i2cData = Wire.read();
  }
  // All values below 128 are commands, else it is a parameter.
  if (i2cData < 128) {
    // New command so reset parameter count.
    i2cParameterCount = 0;
    i2cCommand = i2cData;
  }
  else {
    i2cParameters[i2cParameterCount++] = i2cData;
  }
}

// callback for sending data
void sendData()
{
  Wire.write(i2cDataByteToSend); // Send data back over I2C.
}

// Left motor.
void Motor1(int pwm, boolean reverse)
{
  analogWrite(PWM1, pwm); // Set pwm control, 0 for stop, and 255 for maximum speed.
  if (reverse)
  {
    digitalWrite(DIR1, HIGH);
  }
  else
  {
    digitalWrite(DIR1, LOW);
  }
}

// Right motor.
void Motor2(int pwm, boolean reverse)
{
  analogWrite(PWM2, pwm);
  if (reverse)
  {
    digitalWrite(DIR2, HIGH);
  }
  else
  {
    digitalWrite(DIR2, LOW);
  }
}

void setup()
{
  pinMode(DIR1, OUTPUT);
  pinMode(DIR2, OUTPUT);
  pinMode(EXT_POWER_SWITCH_PIN, OUTPUT);
  pinMode(LIGHT_PIN, OUTPUT);

  // initialize i2c as slave
  Wire.begin(SLAVE_ADDRESS);

  // define callbacks for i2c communication
  Wire.onReceive(receiveData);
  Wire.onRequest(sendData);

  Serial.begin(9600);
  servoCameraPos = 0;
  myServo.attach(SERVO_CAMERA_PIN);   // Attaches the servocamera pin to the servo object.
  myServo.write(servoCameraPos);      // Put servocamera in start position.
}

void loop()
{
  static boolean extPowerAvailable = false;
  static unsigned long lastTimeWithoutExternalPowerMillis = 0; // Last time without external power in millis.
  int extPowerLevel;  // External power level.
  int intPowerLevel;  // Internal power level.

  //  Read analog sense values
  extPowerLevel = analogRead(EXT_POWER_SENSE_PIN);  // range [0..1023]
  intPowerLevel = analogRead(INT_POWER_SENSE_PIN);  // range [0..1023]

  // If external power is available, switch to external power.
  // First check if external power is connected reliably for an amount of time.
  if (extPowerLevel > 100) {
    if (millis() - lastTimeWithoutExternalPowerMillis > 5000) {
      // At least 5 seconds external power available, so switch to external power.
      digitalWrite(EXT_POWER_SWITCH_PIN, HIGH);
      extPowerAvailable = true;
    }
  }
  else {
    // No external power, update lastTimeWithoutExternalPowerMillis;.
    lastTimeWithoutExternalPowerMillis = millis();
    digitalWrite(EXT_POWER_SWITCH_PIN, LOW);
    extPowerAvailable = false;
  }

  switch (i2cCommand)
  {
    case 1: // Drive and turn, make a temporary turn while driving, used for autonomous control
      if (i2cParameterCount == 4) {
        // i2cParameters[0]: driving spead [128..255], where [128..191] means backward, 192 means zero speed and [193..255] means forward.
        // i2cParameters[1]: turning speed [128..255], where [128..191] means left, 192 means straight forward and [193..255] means right.
        // i2cParameters[2]: time to drive [128..255], where 128 means infinite, 129 means 50 ms and 255 means 1000 ms.
        // i2cParameters[3]: time to turn  [128..255], where 128 means infinite, 129 means 50 ms and 255 means 1000 ms.
        boolean directionBackward;
        int speedStraight;
        // For speedTurn we do not use the map function to keep it symmetric around 0 as it originated from 192+[-63..63] = [129..255].
        int speedTurn = (i2cParameters[1] - 192) * 4; // map speedTurn back to 4*[-63..63] = [-252..252]
        int delayDrive = i2cParameters[2] > 128 ? map(i2cParameters[2], 129, 255, 50, 1000): 0; // For value 128 make delay zero to indicate infinite.
        int delayTurn = i2cParameters[3] > 128 ? map(i2cParameters[3], 129, 255, 50, 1000): 0;  // For value 128 make delay zero to indicate infinite.

        if (i2cParameters[0] < 192) {
          // Backward.
          directionBackward = true; // backward left wheels
          speedStraight = map(i2cParameters[0], 191, 128, 0, 255);
        }
        else {
          // Forward.
          directionBackward = false; // forward left wheels
          speedStraight = map(i2cParameters[0], 192, 255, 0, 255);
        }

        // If robot is on external power, first switch to batteries.
        // Because switching from external power to batteries is done by a relay, the robot only gets power from a capacitor during the switch.
        // Therefore it is important to do this switching before the robot starts to drive, otherwise the capacitor will not have enough charge.
        // When both speeds are zero (stop command), do not switch off external power. The stop command is sent when losing connection in FPV mode.
        if (extPowerAvailable == true && (i2cParameters[0] != 192 || i2cParameters[1] != 192)) {
          digitalWrite(EXT_POWER_SWITCH_PIN, LOW);
          extPowerAvailable = false;
          // Delay to make sure switch to battery power is done before the robot starts to drive.
          // Make sure that after this delay the i2cParameters[...] are not used anymore because during the delay they can be overwritten by the receiveData() callback fuction.
          delay(500);
          lastTimeWithoutExternalPowerMillis = millis();  // To make sure external power is not reconnected if robot drives away slowly.
        }

        if (speedTurn != 0) {
          // If we have to turn we do this first for turnDelay ms.
          int speed1 = speedStraight + speedTurn;
          int speed2 = speedStraight - speedTurn;
          // Because of speedTurn it can now be that one of the speeds is above 255 or below 0.
          // In this case we shift both speeds back into the [0..255] range such that we do not have to clip the speeds and the difference is still speedTurn.
          // This way the steering behavior will be the same for all speeds.
          if (speed1 > 255 || speed2 > 255) {
            int shift = max(speed1, speed2) - 255;
            speed1 = speed1 - shift;
            speed2 = speed2 - shift;
          }
          // If speed is negative, we have to inverse the direction.
          bool dir1 = speed1 >= 0 ? directionBackward : !directionBackward;
          bool dir2 = speed2 >= 0 ? directionBackward : !directionBackward;
          Motor1(abs(speed1), dir1);
          Motor2(abs(speed2), dir2);
          if (delayTurn != 0) {
            delay(delayTurn);
          }
        }
        if (speedTurn == 0 || delayTurn != 0) {
          // If we do not have to turn or only turn temporary we have to change to driving straight.
          Motor1(speedStraight, directionBackward);
          Motor2(speedStraight, directionBackward);
          if (delayDrive != 0 && speedStraight != 0) {
            // If we have to drive temporary at nonzero speed we have to stop after the drive.
            delay(delayDrive);
            // Continue driving straight
            Motor1(0, false);
            Motor2(0, false);
          }
        }
        i2cCommand = 0;
      }
      break;
    case 10: // servo for camera up, relative movement
      if (i2cParameterCount == 1) {
        // i2cParameters[0] - 128 is number of degrees
        servoCameraPos = min(servoCameraPos + (i2cParameters[0] - 128), 90);
        myServo.write(servoCameraPos);
        i2cCommand = 0;
      }
      break;
    case 11: // servo for camera down, relative movement
      if (i2cParameterCount == 1) {
        // i2cParameters[0] - 128 is number of degrees
        servoCameraPos = max(servoCameraPos - (i2cParameters[0] - 128), 0);
        myServo.write(servoCameraPos);
        i2cCommand = 0;
      }
      break;
    case 12: // servo for camera, absolute movement
      if (i2cParameterCount == 1) {
        // i2cParameters[0] - 128 is number of degrees
        servoCameraPos = min(i2cParameters[0] - 128, 90);
        myServo.write(servoCameraPos);
        i2cCommand = 0;
      }
      break;
    case 20: // light on
      digitalWrite(LIGHT_PIN, HIGH);
      i2cCommand = 0;
      break;
    case 21: // light off
      digitalWrite(LIGHT_PIN, LOW);
      i2cCommand = 0;
      break;
    case 100: // Command to indicate a read is going to follow.
      if (i2cParameterCount == 1) {
        if (i2cParameters[0] == 128) {            // 128 means read external power level.
          i2cDataByteToSend = extPowerLevel / 4;  // Map level [0..1023] to [0..255] so it fits in one byte.
        }
        else if (i2cParameters[0] == 129) {       // 129 means read internal power level. This power level can be from external power or the batteries.
          i2cDataByteToSend = intPowerLevel / 4;  // Map level [0..1023] to [0..255] so it fits in one byte.
        }
        i2cCommand = 0;
      }
      break;

    default:
      break;
  }

  // No delay here as it will degrade I2C performance.
}
