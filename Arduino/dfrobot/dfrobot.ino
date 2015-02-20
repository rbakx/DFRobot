#include <Wire.h>
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

int i2cNumber = 0; // global variable for receiving number from I2C
int ana0Value = 0; // global variable for sending number to I2C
unsigned long count = 0; // global variable counting the total number of loops

// callback for received data
void receiveData(int byteCount)
{
  while(Wire.available()) {
    i2cNumber = Wire.read();

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
} 

void loop() 
{ 
  switch (i2cNumber)
  {
  case 1: // forward
    Motor1(255, false);
    Motor2(255, false);
    delay(1000);
    Motor1(0, true);
    Motor2(0, true);
    i2cNumber = 0;
    break;
  case 2: // backward
    Motor1(255, true);
    Motor2(255, true);
    delay(1000);
    Motor1(0, false);
    Motor2(0, false);
    i2cNumber = 0;
    break;
  case 3: // turn left
    Motor1(255, false);
    Motor2(255, true);
    delay(500);
    Motor1(0, true);
    Motor2(0, true);
    i2cNumber = 0;
    break;
  case 4: // turn right
    Motor1(255, true);
    Motor2(255, false);
    delay(500);
    Motor1(0, true);
    Motor2(0, true);
    i2cNumber = 0;
    break;
  case 10: // light on
    digitalWrite(LIGHT,HIGH);
    break;
  case 11: // light off
    digitalWrite(LIGHT,LOW);
    break;
  default:
    i2cNumber = 0;
    break;
  }

  ana0Value = analogRead(ANA0); 

  delay(100);
  count = count + 1;
  if (count == 216000)
  {
    // reset charge cycle every 6 hours
    digitalWrite(RESETCHARGE,HIGH);
    delay(2000);
    digitalWrite(RESETCHARGE,LOW);
    count = 0;
  }
}






