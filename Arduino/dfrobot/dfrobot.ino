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
int ANA0 = A0;
// LIGHT and RESETCHARGE control the same relay
int LIGHT = 2;
int RESETCHARGE = 2;
int SERVOCAMERA = 3;

int i2cCommand = 0; // global variable for receiving command from I2C
int i2cParameters[10]; // global array for receiving parameters from I2C
int i2cParameterCount = 0; // global variable for keeping I2C parameter count
int ana0Value = 0; // global variable for sending number to I2C
unsigned long count = 0; // global variable counting the total number of loops

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
  Wire.write(ana0Value / 4); // I2C only receives bytes, so map 0..1023 to 0..255.
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
  pinMode(RESETCHARGE, OUTPUT);

  // initialize i2c as slave
  Wire.begin(SLAVE_ADDRESS);

  // define callbacks for i2c communication
  Wire.onReceive(receiveData);
  Wire.onRequest(sendData);

  Serial.begin(9600);
  servoCameraPos = 0;
  myServo.attach(SERVOCAMERA);   // Attaches the servocamera pin to the servo object.
  myServo.write(servoCameraPos); // Put servocamera in start position.
}

void loop()
{
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
        // For speedTurn we do not use the map function to keep it symmetric around 0 as it originated from 192+[-64..63] = [128..255].
        int speedTurn = (i2cParameters[1] - 192) * 4; // map speedTurn back to 4*[-64..63] = [-256..252]
        int delayDrive = i2cParameters[2] > 128 ? map(i2cParameters[2], 129, 255, 50, 1000): 0; // For value 128 make delay zero to indicate infinite.
        int delayTurn = i2cParameters[3] > 128 ? map(i2cParameters[2], 129, 255, 50, 1000): 0;  // For value 128 make delay zero to indicate infinite.
        
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
        if (speedTurn != 0) {
          // If we have to turn we do this first for turnDelay ms.
          // Keep motor speed values between 0 and 255.
          int speed1 = max(min(speedStraight + speedTurn,255),-255);
          int speed2 = max(min(speedStraight - speedTurn,255),-255);
          // If speed is negative, we have to inverse the direction.
          bool dir1 = speed1 >= 0 ? directionBackward : !directionBackward;
          bool dir2 = speed2 >= 0 ? directionBackward : !directionBackward;
          Motor1(speed1, dir1);
          Motor2(speed2, dir2);
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
      digitalWrite(LIGHT, HIGH);
      i2cCommand = 0;
      break;
    case 21: // light off
      digitalWrite(LIGHT, LOW);
      i2cCommand = 0;
      break;
    default:
      break;
  }

  ana0Value = analogRead(ANA0);

  delay(100);
  count = count + 1;
  if (count == 72000)
  {
    // reset charge cycle every 2 hours
    digitalWrite(RESETCHARGE, HIGH);
    delay(2000);
    digitalWrite(RESETCHARGE, LOW);
    count = 0;
  }
}







