#include <Wire.h>
#include <Servo.h>
#define SLAVE_ADDRESS 0x04

//This motor shield use Pin 6,5,7,4 to control the motor
// Simply connect your motors to M1+,M1-,M2+,M2-
// Upload the code to Arduino/Roboduino
// Through serial monitor, type 'a','s', 'w','d','x' to control the motor
// www.dfrobot.com
// Last modified on 24/12/2009

int DIR1 = 4;
int PWM1 = 5;  
int DIR2 = 7;
int PWM2 = 6;
int ANA0 = A0;
// LIGHT and RESETCHARGE control the same relay
int LIGHT = 2;
int RESETCHARGE = 2;
int SERVOCAMERA = 3;

int i2cCommand = 0; // global variable for receiving command from I2C
int i2cParameter = 0; // global variable for receiving parameter from I2C
int ana0Value = 0; // global variable for sending number to I2C
unsigned long count = 0; // global variable counting the total number of loops

Servo myServo;  // create servo camera object to control a servo
int servoCameraPos;   // variable to store the servo camera position 

// callback for received data
void receiveData(int byteCount)
{
  int i2cData;
  while(Wire.available()) {
    i2cData = Wire.read();
  }
  // All values below 128 are commands, else it is a parameter.
  if (i2cData < 128) {
    i2cCommand = i2cData;
  }
  else {
    i2cParameter = i2cData;
  }
}

// callback for sending data
void sendData()
{
  Wire.write(ana0Value/4); // I2C only receives bytes, so map 0..1023 to 0..255
}

void Motor1(int pwm, boolean reverse)
{
  analogWrite(PWM1,pwm); //set pwm control, 0 for stop, and 255 for maximum speed
  if(reverse)
  { 
    digitalWrite(DIR1,HIGH);    
  }
  else
  {
    digitalWrite(DIR1,LOW);    
  }
}  

void Motor2(int pwm, boolean reverse)
{
  analogWrite(PWM2,pwm);
  if(reverse)
  { 
    digitalWrite(DIR2,HIGH);    
  }
  else
  {
    digitalWrite(DIR2,LOW);    
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
  myServo.attach(SERVOCAMERA);   // attaches the servocamera pin to the servo object
  myServo.write(servoCameraPos); // put servocamera in start position
} 

void loop() 
{ 
  switch (i2cCommand)
  {
  case 1: // forward
    if (i2cParameter >=128) {
      int ms = map(i2cParameter, 128, 255, 50, 1000);
      Motor1(255, false);
      Motor2(255, false);
      delay(ms);
      Motor1(0, true);
      Motor2(0, true);
      i2cCommand = 0;
      i2cParameter = 0;
    }
    break;
  case 2: // backward
    if (i2cParameter >=128) {
      int ms = map(i2cParameter, 128, 255, 50, 1000);
      Motor1(255, true);
      Motor2(255, true);
      delay(ms);
      Motor1(0, false);
      Motor2(0, false);
      i2cCommand = 0;
      i2cParameter = 0;
    }
    break;
  case 3: // turn left
    if (i2cParameter >=128) {
      int ms = map(i2cParameter, 128, 255, 50, 400);
      Motor1(255, false);
      Motor2(255, true);
      delay(ms);
      Motor1(0, true);
      Motor2(0, true);
      i2cCommand = 0;
      i2cParameter = 0;
    }
    break;
  case 4: // turn right
    if (i2cParameter >=128) {
      int ms = map(i2cParameter, 128, 255, 50, 400);
      Motor1(255, true);
      Motor2(255, false);
      delay(ms);
      Motor1(0, true);
      Motor2(0, true);
      i2cCommand = 0;
      i2cParameter = 0;
    }
    break;
  case 10: // servo for camera up
    servoCameraPos = min(servoCameraPos + 30, 90);
    myServo.write(servoCameraPos);
    i2cCommand = 0;
    break;
  case 11: // servo for camera down
    servoCameraPos = max(servoCameraPos - 30, 0);
    myServo.write(servoCameraPos);
    i2cCommand = 0;
    break;
  case 20: // light on
    digitalWrite(LIGHT,HIGH);
    i2cCommand = 0;
    break;
  case 21: // light off
    digitalWrite(LIGHT,LOW);
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
    digitalWrite(RESETCHARGE,HIGH);
    delay(2000);
    digitalWrite(RESETCHARGE,LOW);
    count = 0;
  }
}







