#include <ESP32Servo.h>

// --- DEFINICJE PINÓW SILNIKÓW ---
#define PUL1_PIN 23
#define DIR1_PIN 22
#define PUL2_PIN 21
#define DIR2_PIN 19
#define PULZ_PIN 16
#define DIRZ_PIN 17

// --- DEFINICJE PINÓW OSZPRZĘTU ---
#define SERVO_PIN 25
#define RELAY1_PIN 26
#define RELAY2_PIN 27

// --- DEFINICJE PINÓW ENKODERÓW ---
#define ENCO1_PHASE_A 32
#define ENCO1_PHASE_B 33
#define ENCO2_PHASE_A 34
#define ENCO2_PHASE_B 35

// --- DEFINICJE PINÓW KRAŃCÓWEK (Bezpieczne dla startu ESP) ---
#define LIMIT_X_PIN 4
#define LIMIT_Y_PIN 13
#define LIMIT_Z_PIN 14

// --- ZMIENNE KONFIGURACYJNE ---
int delayCoreXY = 800;
const int delayZ = 1200;
int homingDelay = 1500;

bool motor1Running = false;
bool motor2Running = false;
bool motorZRunning = false;

volatile long encoder1Count = 0;
volatile long encoder2Count = 0;
unsigned long lastPrint = 0;
unsigned long lastServoToggle = 0;

Servo myServo;
bool servoState = false;

int posX = 0;
int posY = 0;
String pressedKeys = "";

// --- OBSŁUGA PRZERWAŃ ENKODERÓW ---
void IRAM_ATTR readEncoder1() {
  if (digitalRead(ENCO1_PHASE_A) == digitalRead(ENCO1_PHASE_B)) encoder1Count++;
  else encoder1Count--;
}

void IRAM_ATTR readEncoder2() {
  if (digitalRead(ENCO2_PHASE_A) == digitalRead(ENCO2_PHASE_B)) encoder2Count++;
  else encoder2Count--;
}

// --- FUNKCJE RUCHU ---
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

// --- FUNKCJA BAZOWANIA (HOMING) ---
void performHoming() {
  Serial.println("Homing start...");
  stopAllMotors();

  // 1. Oś Z (Góra/Dół)
  digitalWrite(DIRZ_PIN, LOW);
  while(digitalRead(LIMIT_Z_PIN) == HIGH) {
    digitalWrite(PULZ_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PULZ_PIN, LOW); delayMicroseconds(homingDelay); yield();
  }
  digitalWrite(DIRZ_PIN, HIGH);
  for(int i = 0; i < 300; i++) {
    digitalWrite(PULZ_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PULZ_PIN, LOW); delayMicroseconds(homingDelay); yield();
  }

  // 2. Oś X
  digitalWrite(DIR1_PIN, LOW); digitalWrite(DIR2_PIN, HIGH);
  while(digitalRead(LIMIT_X_PIN) == HIGH) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay); yield();
  }
  digitalWrite(DIR1_PIN, HIGH); digitalWrite(DIR2_PIN, LOW);
  for(int i = 0; i < 200; i++) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay); yield();
  }

  // 3. Oś Y
  digitalWrite(DIR1_PIN, LOW); digitalWrite(DIR2_PIN, LOW);
  while(digitalRead(LIMIT_Y_PIN) == HIGH) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay); yield();
  }
  digitalWrite(DIR1_PIN, HIGH); digitalWrite(DIR2_PIN, HIGH);
  for(int i = 0; i < 200; i++) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay); yield();
  }

  posX = 0; posY = 0;
  Serial.println("Homing OK!");
}

void setup() {
  // Wyłączenie detektora spadków napięcia (Brownout)


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

  myServo.attach(SERVO_PIN);
  myServo.write(0);

  attachInterrupt(digitalPinToInterrupt(ENCO1_PHASE_A), readEncoder1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCO2_PHASE_A), readEncoder2, CHANGE);

  Serial.println("System Ready");
}

void loop() {
  // 1. ALARM KRAŃCÓWEK
  bool limitX = (digitalRead(LIMIT_X_PIN) == LOW);
  bool limitY = (digitalRead(LIMIT_Y_PIN) == LOW);
  bool limitZ = (digitalRead(LIMIT_Z_PIN) == LOW);

  if ((limitX || limitY || limitZ) && (motor1Running || motor2Running || motorZRunning)) {
      stopAllMotors();
      Serial.println("ALARM_LIMIT");
  }

  // 2. KOMUNIKACJA SERIAL
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\r');
    data.trim();
    if (data.length() == 0) return;

    int c1 = data.indexOf(',');
    int c2 = data.indexOf(',', c1 + 1);
    int c3 = data.indexOf(',', c2 + 1);

    if (c1 > 0 && c2 > 0 && c3 > 0) {
      posX = data.substring(0, c1).toInt();
      posY = data.substring(c1 + 1, c2).toInt();
      int speedVal = data.substring(c2 + 1, c3).toInt();

      // Mapowanie prędkości
      if(speedVal >= 1 && speedVal <= 100) {
        delayCoreXY = (int)(1000000.0 / (100.0 + ((speedVal - 1.0) / 99.0) * 9900.0));
      }
      pressedKeys = data.substring(c3 + 1);

      if (pressedKeys.length() > 0) {
        if (pressedKeys.indexOf('p') >= 0) {
          stopAllMotors();
        } else if (pressedKeys.indexOf('h') >= 0) {
          performHoming();
        } else {
          // Ruchy CoreXY
          bool u = pressedKeys.indexOf('i') >= 0;
          bool d = pressedKeys.indexOf('k') >= 0;
          bool l = pressedKeys.indexOf('j') >= 0;
          bool r = pressedKeys.indexOf('l') >= 0;

          if (u && l) setMotorsXY(false, LOW, true, HIGH);
          else if (u && r) setMotorsXY(true, HIGH, false, LOW);
          else if (d && l) setMotorsXY(true, LOW, false, LOW);
          else if (d && r) setMotorsXY(false, LOW, true, LOW);
          else if (u) setMotorsXY(true, HIGH, true, HIGH);
          else if (d) setMotorsXY(true, LOW, true, LOW);
          else if (l) setMotorsXY(true, LOW, true, HIGH);
          else if (r) setMotorsXY(true, HIGH, true, LOW);
          else { motor1Running = false; motor2Running = false; }

          // Oś Z
          if (pressedKeys.indexOf('z') >= 0) moveZ(HIGH);
          else if (pressedKeys.indexOf('x') >= 0) moveZ(LOW);
          else motorZRunning = false;

          // Servo Toggle (V)
          if (pressedKeys.indexOf('v') >= 0) {
            if (millis() - lastServoToggle > 500) {
              servoState = !servoState;
              myServo.write(servoState ? 180 : 0);
              lastServoToggle = millis();
            }
          }
          // Solenoidy Hold (1 i 2)
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

  // 3. GENEROWANIE KROKÓW
  int currentDelay = (motorZRunning) ? delayZ : delayCoreXY;

  if (motor1Running) digitalWrite(PUL1_PIN, HIGH);
  if (motor2Running) digitalWrite(PUL2_PIN, HIGH);
  if (motorZRunning) digitalWrite(PULZ_PIN, HIGH);

  delayMicroseconds(currentDelay);
  yield();

  if (motor1Running) digitalWrite(PUL1_PIN, LOW);
  if (motor2Running) digitalWrite(PUL2_PIN, LOW);
  if (motorZRunning) digitalWrite(PULZ_PIN, LOW);

  delayMicroseconds(currentDelay);
  yield();
}