#include <ESP32Servo.h>

// --- Motor Pin Definitions ---
#define PUL1_PIN 4
#define DIR1_PIN 5
#define PUL2_PIN 6
#define DIR2_PIN 7
#define PULZ_PIN 8
#define DIRZ_PIN 9

// --- Limit Switch Pin Definitions ---
#define LIMIT_X_PIN 10
#define LIMIT_Y_PIN 11
#define LIMIT_Z_PIN 12

// --- Encoder Pin Definitions ---
#define ENCO1_PHASE_A 13
#define ENCO1_PHASE_B 14
#define ENCO2_PHASE_A 15
#define ENCO2_PHASE_B 16

// --- Hardware Pin Definitions ---
#define SERVO_PIN 17
#define RELAY1_PIN 18
#define RELAY2_PIN 21

// --- Configuration Variables ---
int delayCoreXY = 800;
const int delayZ = 1200;
int homingDelay = 1500;

bool motor1Running = false;
bool motor2Running = false;
bool motorZRunning = false;

volatile long encoder1Count = 0;
volatile long encoder2Count = 0;
unsigned long lastPrintTime = 0;
unsigned long lastServoToggle = 0;

Servo mainServo;
bool servoState = false;

int posX = 0;
int posY = 0;
String pressedKeys = "";

// --- Encoder Interrupt Handlers ---
void IRAM_ATTR readEncoder1() {
  if (digitalRead(ENCO1_PHASE_A) == digitalRead(ENCO1_PHASE_B)) encoder1Count++;
  else encoder1Count--;
}

void IRAM_ATTR readEncoder2() {
  if (digitalRead(ENCO2_PHASE_A) == digitalRead(ENCO2_PHASE_B)) encoder2Count++;
  else encoder2Count--;
}

// --- Movement Functions ---
void stopAllMotors() {
  motor1Running = false;
  motor2Running = false;
  motorZRunning = false;
  digitalWrite(PUL1_PIN, LOW);
  digitalWrite(PUL2_PIN, LOW);
  digitalWrite(PULZ_PIN, LOW);
}

void setMotorsXY(bool run1, int dir1, bool run2, int dir2) {
  motorZRunning = false;
  if (run1) digitalWrite(DIR1_PIN, dir1);
  if (run2) digitalWrite(DIR2_PIN, dir2);
  delayMicroseconds(5);
  motor1Running = run1;
  motor2Running = run2;
}

void moveZ(int dirZ) {
  motor1Running = false;
  motor2Running = false;
  digitalWrite(DIRZ_PIN, dirZ);
  delayMicroseconds(5);
  motorZRunning = true;
}

// --- Homing Function ---
void performHoming() {
  Serial.println("Homing start...");
  stopAllMotors();

  // 1. Z-Axis (Up/Down)
  digitalWrite(DIRZ_PIN, LOW);
  while(digitalRead(LIMIT_Z_PIN) == HIGH) {
    digitalWrite(PULZ_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PULZ_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1); // Replaced yield() to prevent WDT reset
  }
  digitalWrite(DIRZ_PIN, HIGH);
  for(int i = 0; i < 300; i++) {
    digitalWrite(PULZ_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PULZ_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }

  // 2. X-Axis
  digitalWrite(DIR1_PIN, LOW); digitalWrite(DIR2_PIN, HIGH);
  while(digitalRead(LIMIT_X_PIN) == HIGH) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }
  digitalWrite(DIR1_PIN, HIGH); digitalWrite(DIR2_PIN, LOW);
  for(int i = 0; i < 200; i++) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }

  // 3. Y-Axis
  digitalWrite(DIR1_PIN, LOW); digitalWrite(DIR2_PIN, LOW);
  while(digitalRead(LIMIT_Y_PIN) == HIGH) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }
  digitalWrite(DIR1_PIN, HIGH); digitalWrite(DIR2_PIN, HIGH);
  for(int i = 0; i < 200; i++) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }

  posX = 0; posY = 0;
  Serial.println("Homing OK!");
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(30);

  pinMode(PUL1_PIN, OUTPUT); pinMode(DIR1_PIN, OUTPUT);
  pinMode(PUL2_PIN, OUTPUT); pinMode(DIR2_PIN, OUTPUT);
  pinMode(PULZ_PIN, OUTPUT); pinMode(DIRZ_PIN, OUTPUT);
  pinMode(RELAY1_PIN, OUTPUT); pinMode(RELAY2_PIN, OUTPUT);

  pinMode(ENCO1_PHASE_A, INPUT); pinMode(ENCO1_PHASE_B, INPUT);
  pinMode(ENCO2_PHASE_A, INPUT_PULLUP); pinMode(ENCO2_PHASE_B, INPUT_PULLUP);

  pinMode(LIMIT_X_PIN, INPUT_PULLUP);
  pinMode(LIMIT_Y_PIN, INPUT_PULLUP);
  pinMode(LIMIT_Z_PIN, INPUT_PULLUP);

  stopAllMotors();
  digitalWrite(RELAY1_PIN, LOW);
  digitalWrite(RELAY2_PIN, LOW);

  mainServo.attach(SERVO_PIN);
  mainServo.write(0);

  attachInterrupt(digitalPinToInterrupt(ENCO1_PHASE_A), readEncoder1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCO2_PHASE_A), readEncoder2, CHANGE);

  Serial.println("System Ready");
}

void loop() {
  // 1. LIMIT SWITCH ALARM
  bool limitX = (digitalRead(LIMIT_X_PIN) == LOW);
  bool limitY = (digitalRead(LIMIT_Y_PIN) == LOW);
  bool limitZ = (digitalRead(LIMIT_Z_PIN) == LOW);

  if ((limitX || limitY || limitZ) && (motor1Running || motor2Running || motorZRunning)) {
      stopAllMotors();
      Serial.println("ALARM_LIMIT");
  }

  // 2. SERIAL COMMUNICATION
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\r');
    data.trim();

    if (data.length() > 0) {
      int commaIndexOne = data.indexOf(',');
      int commaIndexTwo = data.indexOf(',', commaIndexOne + 1);
      int commaIndexThree = data.indexOf(',', commaIndexTwo + 1);

      if (commaIndexOne > 0 && commaIndexTwo > 0 && commaIndexThree > 0) {
        posX = data.substring(0, commaIndexOne).toInt();
        posY = data.substring(commaIndexOne + 1, commaIndexTwo).toInt();
        int speedValue = data.substring(commaIndexTwo + 1, commaIndexThree).toInt();

        // Speed Mapping
        if(speedValue >= 1 && speedValue <= 100) {
          delayCoreXY = (int)(1000000.0 / (100.0 + ((speedValue - 1.0) / 99.0) * 9900.0));
        }
        pressedKeys = data.substring(commaIndexThree + 1);

        // --- TWÓJ PRINT DIAGNOSTYCZNY ---
        Serial.print("Zrozumialem dX: ");
        Serial.print(posX);
        Serial.print(" dY: ");
        Serial.print(posY);
        Serial.print(" Speed: ");
        Serial.print(speedValue);
        Serial.print(" Keys: ");
        Serial.println(pressedKeys);
        // --------------------------------

        if (pressedKeys.length() > 0) {
          if (pressedKeys.indexOf('p') >= 0) {
            stopAllMotors();
          } else if (pressedKeys.indexOf('h') >= 0) {
            performHoming();
          } else {
            // CoreXY Movement Logic
            bool moveUp = pressedKeys.indexOf('i') >= 0;
            bool moveDown = pressedKeys.indexOf('k') >= 0;
            bool moveLeft = pressedKeys.indexOf('j') >= 0;
            bool moveRight = pressedKeys.indexOf('l') >= 0;

            if (moveUp && moveLeft) setMotorsXY(false, LOW, true, HIGH);
            else if (moveUp && moveRight) setMotorsXY(true, HIGH, false, LOW);
            else if (moveDown && moveLeft) setMotorsXY(true, LOW, false, LOW);
            else if (moveDown && moveRight) setMotorsXY(false, LOW, true, LOW);
            else if (moveUp) setMotorsXY(true, HIGH, true, HIGH);
            else if (moveDown) setMotorsXY(true, LOW, true, LOW);
            else if (moveLeft) setMotorsXY(true, LOW, true, HIGH);
            else if (moveRight) setMotorsXY(true, HIGH, true, LOW);
            else { motor1Running = false; motor2Running = false; }

            // Z-Axis
            if (pressedKeys.indexOf('z') >= 0) moveZ(HIGH);
            else if (pressedKeys.indexOf('x') >= 0) moveZ(LOW);
            else motorZRunning = false;

            // Servo Toggle (V)
            if (pressedKeys.indexOf('v') >= 0) {
              if (millis() - lastServoToggle > 500) {
                servoState = !servoState;
                mainServo.write(servoState ? 180 : 0);
                lastServoToggle = millis();
              }
            }
            // Solenoid Hold (1 and 2)
            digitalWrite(RELAY1_PIN, (pressedKeys.indexOf('1') >= 0) ? HIGH : LOW);
            digitalWrite(RELAY2_PIN, (pressedKeys.indexOf('2') >= 0) ? HIGH : LOW);
          }
        } else {
          stopAllMotors();
          digitalWrite(RELAY1_PIN, LOW);
          digitalWrite(RELAY2_PIN, LOW);
        }
      }
    }
  }

  // Allow FreeRTOS to handle background tasks when motors are idle
  if (!motor1Running && !motor2Running && !motorZRunning) {
    delay(1);
    return;
  }

  // 3. STEP GENERATION
  int currentDelay = (motorZRunning) ? delayZ : delayCoreXY;

  if (motor1Running) digitalWrite(PUL1_PIN, HIGH);
  if (motor2Running) digitalWrite(PUL2_PIN, HIGH);
  if (motorZRunning) digitalWrite(PULZ_PIN, HIGH);

  delayMicroseconds(currentDelay);

  if (motor1Running) digitalWrite(PUL1_PIN, LOW);
  if (motor2Running) digitalWrite(PUL2_PIN, LOW);
  if (motorZRunning) digitalWrite(PULZ_PIN, LOW);

  delayMicroseconds(currentDelay);
}