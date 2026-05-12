/*
 * CSAimBot Motor Control Firmware - MODIFIED SAFE WORKSPACE VERSION
 * ESP32-based controller for CoreXY robotic platform with Z-axis servo
 * Limit switches: Debounced, used for XY Homing and Safety. Z-limit ignored.
 * Workspace: Virtual software endstops set to 28cm X and 24cm Y from origin.
 */

#include <ESP32Servo.h>
#include <ESP32Encoder.h>

// ============================================================================
// PIN DEFINITIONS
// ============================================================================

#define PUL1_PIN 23
#define DIR1_PIN 22
#define PUL2_PIN 21
#define DIR2_PIN 19
#define PULZ_PIN 12
#define DIRZ_PIN 17

#define SERVO_PIN 25
#define RELAY1_PIN 26
#define RELAY2_PIN 27

#define ENCO1_PHASE_A 18
#define ENCO1_PHASE_B 5
#define ENCO2_PHASE_A 32
#define ENCO2_PHASE_B 33

#define LIMIT_X_PIN 4
#define LIMIT_Y_PIN 13
#define LIMIT_Z_PIN 14

// ============================================================================
// NON-BLOCKING SERIAL BUFFER
// ============================================================================

const int MAX_BUFFER_SIZE = 64;
char serialBuffer[MAX_BUFFER_SIZE];
int bufferIndex = 0;
bool isCommandReady = false;

// ============================================================================
// CONFIGURATION & STATE VARIABLES
// ============================================================================

int delayCoreXY = 800;
const int delayZ = 300;
int homingDelay = 1500;

bool motor1Running = false;
bool motor2Running = false;
bool motorZRunning = false;

// Active movement tracking for continuous endstop monitoring
bool isMovingUp = false;
bool isMovingDown = false;
bool isMovingLeft = false;
bool isMovingRight = false;

ESP32Encoder encoder1;
ESP32Encoder encoder2;

float currentPosX = 0.0;
float currentPosY = 0.0;
unsigned long lastEncoderPrint = 0;

float stepsPerCM = 296.30;

// ============================================================================
// ENCODER AXIS SIGN CALIBRATION
// ============================================================================
//
// Po homingu:
// - ruch w lewo powinien zmniejszać X, czyli X idzie w minus
// - ruch w prawo powinien zwiększać X, czyli X idzie do 0
// - ruch w dół powinien zwiększać Y, czyli Y idzie do 24
// - ruch w górę powinien zmniejszać Y, czyli Y idzie do 0
//
// Jeśli jest odwrotnie, zmień SIGN_X albo SIGN_Y z 1 na -1.

const int SIGN_X = 1;
const int SIGN_Y = 1;

// ============================================================================
// SERVO
// ============================================================================

Servo mainServo;
bool servoState = false;
unsigned long lastServoToggle = 0;

const int angleUp = 0;
const int angleDown = 180;

unsigned long servoMoveStartTime = 0;
bool isServoTimerActive = false;
unsigned long lastLimitNotify = 0;

// ============================================================================
// VIRTUAL WORKSPACE LIMITS
// ============================================================================
//
// Po homingu i backoff:
// X: od -28 cm do 0 cm
// Y: od 0 cm do 24 cm

const float LIMIT_MIN_X = -28.50;
const float LIMIT_MAX_X = 0.00;
const float LIMIT_MIN_Y = 0.00;
const float LIMIT_MAX_Y = 24.50;

// Margines bezpieczeństwa, żeby nie dobijać idealnie do końca
const float LIMIT_MARGIN_CM = 0.30;

int posX = 0;
int posY = 0;
String pressedKeys = "";

// ============================================================================
// MOTOR CONTROL FUNCTIONS
// ============================================================================

void stopAllMotors() {
  motor1Running = false;
  motor2Running = false;
  motorZRunning = false;

  isMovingUp = false;
  isMovingDown = false;
  isMovingLeft = false;
  isMovingRight = false;

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

// ============================================================================
// DEBOUNCE HELPER FUNCTION
// ============================================================================

bool isSwitchStablyPressed(int pin, unsigned long debounceTimeMs) {
  if (digitalRead(pin) == HIGH) {
    return false;
  }

  unsigned long startMillis = millis();

  while (millis() - startMillis < debounceTimeMs) {
    if (digitalRead(pin) == HIGH) {
      return false;
    }
  }

  return true;
}

// ============================================================================
// POSITION UPDATE
// ============================================================================

void updateEncoderPosition() {
  long e1Count = encoder1.getCount();
  long e2Count = encoder2.getCount();

  float ticksX = (e1Count - e2Count) / 2.0;
  float ticksY = (e1Count + e2Count) / 2.0;

  currentPosX = SIGN_X * ticksX / stepsPerCM;
  currentPosY = SIGN_Y * ticksY / stepsPerCM;
}

// ============================================================================
// SOFTWARE LIMIT CHECKS
// ============================================================================

bool isOutsideWorkspace() {
  if (currentPosX <= LIMIT_MIN_X + LIMIT_MARGIN_CM) return true;
  if (currentPosX >= LIMIT_MAX_X - LIMIT_MARGIN_CM) return true;
  if (currentPosY <= LIMIT_MIN_Y + LIMIT_MARGIN_CM) return true;
  if (currentPosY >= LIMIT_MAX_Y - LIMIT_MARGIN_CM) return true;

  return false;
}

void applyContinuousWorkspaceLimit() {
  if (isMovingLeft && currentPosX <= LIMIT_MIN_X + LIMIT_MARGIN_CM) {
    stopAllMotors();
    Serial.println("SOFT LIMIT: X MIN reached. Motors stopped.");
  }

  if (isMovingRight && currentPosX >= LIMIT_MAX_X - LIMIT_MARGIN_CM) {
    stopAllMotors();
    Serial.println("SOFT LIMIT: X MAX reached. Motors stopped.");
  }

  if (isMovingDown && currentPosY >= LIMIT_MAX_Y - LIMIT_MARGIN_CM) {
    stopAllMotors();
    Serial.println("SOFT LIMIT: Y MAX reached. Motors stopped.");
  }

  if (isMovingUp && currentPosY <= LIMIT_MIN_Y + LIMIT_MARGIN_CM) {
    stopAllMotors();
    Serial.println("SOFT LIMIT: Y MIN reached. Motors stopped.");
  }
}

void blockMoveIfWouldExceedLimit(bool &moveUp, bool &moveDown, bool &moveLeft, bool &moveRight) {
  if (moveLeft && currentPosX <= LIMIT_MIN_X + LIMIT_MARGIN_CM) {
    moveLeft = false;
    Serial.println("BLOCKED: moveLeft - X MIN");
  }

  if (moveRight && currentPosX >= LIMIT_MAX_X - LIMIT_MARGIN_CM) {
    moveRight = false;
    Serial.println("BLOCKED: moveRight - X MAX");
  }

  if (moveDown && currentPosY >= LIMIT_MAX_Y - LIMIT_MARGIN_CM) {
    moveDown = false;
    Serial.println("BLOCKED: moveDown - Y MAX");
  }

  if (moveUp && currentPosY <= LIMIT_MIN_Y + LIMIT_MARGIN_CM) {
    moveUp = false;
    Serial.println("BLOCKED: moveUp - Y MIN");
  }
}

// ============================================================================
// HOMING SEQUENCE
// ============================================================================

void performHoming() {
  Serial.println("Homing start...");
  stopAllMotors();

  int backoffSteps = (int)stepsPerCM;
  int debounceLimitMs = 30;

  // ==========================================================================
  // 1. X-AXIS HOMING
  // ==========================================================================

  Serial.println("Homing X...");

  digitalWrite(DIR1_PIN, HIGH);
  digitalWrite(DIR2_PIN, LOW);

  while (!isSwitchStablyPressed(LIMIT_X_PIN, debounceLimitMs)) {
    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);
    delayMicroseconds(homingDelay);
  }

  Serial.println("X limit hit. Backing off...");

  // Back-off X by around 1 cm
  digitalWrite(DIR1_PIN, LOW);
  digitalWrite(DIR2_PIN, HIGH);

  for (int i = 0; i < backoffSteps; i++) {
    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);
    delayMicroseconds(homingDelay);
  }

  delay(200);

  // ==========================================================================
  // 2. Y-AXIS HOMING
  // ==========================================================================

  Serial.println("Homing Y...");

  digitalWrite(DIR1_PIN, HIGH);
  digitalWrite(DIR2_PIN, HIGH);

  while (!isSwitchStablyPressed(LIMIT_Y_PIN, debounceLimitMs)) {
    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);
    delayMicroseconds(homingDelay);
  }

  Serial.println("Y limit hit. Backing off...");

  // Back-off Y by around 1 cm
  digitalWrite(DIR1_PIN, LOW);
  digitalWrite(DIR2_PIN, LOW);

  for (int i = 0; i < backoffSteps; i++) {
    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);
    delayMicroseconds(homingDelay);
  }

  delay(200);

  // ==========================================================================
  // RESET POSITION
  // ==========================================================================

  posX = 0;
  posY = 0;

  encoder1.clearCount();
  encoder2.clearCount();

  currentPosX = 0.0;
  currentPosY = 0.0;

  stopAllMotors();

  Serial.println("Homing OK! Position set to 0,0.");
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  Serial.begin(115200);

  pinMode(PUL1_PIN, OUTPUT);
  pinMode(DIR1_PIN, OUTPUT);
  pinMode(PUL2_PIN, OUTPUT);
  pinMode(DIR2_PIN, OUTPUT);
  pinMode(PULZ_PIN, OUTPUT);
  pinMode(DIRZ_PIN, OUTPUT);

  pinMode(RELAY1_PIN, OUTPUT);
  pinMode(RELAY2_PIN, OUTPUT);

  pinMode(LIMIT_X_PIN, INPUT_PULLUP);
  pinMode(LIMIT_Y_PIN, INPUT_PULLUP);
  pinMode(LIMIT_Z_PIN, INPUT_PULLUP);

  stopAllMotors();

  digitalWrite(RELAY1_PIN, LOW);
  digitalWrite(RELAY2_PIN, LOW);

  mainServo.attach(SERVO_PIN);
  mainServo.write(angleUp);
  delay(1000);
  mainServo.detach();

  ESP32Encoder::useInternalWeakPullResistors = puType::up;

  encoder1.attachHalfQuad(ENCO1_PHASE_A, ENCO1_PHASE_B);
  encoder2.attachHalfQuad(ENCO2_PHASE_A, ENCO2_PHASE_B);

  encoder1.clearCount();
  encoder2.clearCount();

  Serial.println("Controller ready.");
  Serial.println("Send h command to perform homing.");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {

  // ==========================================================================
  // 1. HARDWARE ENCODER POSITION CALCULATION
  // ==========================================================================

  updateEncoderPosition();

  if (millis() - lastEncoderPrint > 500) {
    long e1Count = encoder1.getCount();
    long e2Count = encoder2.getCount();

    Serial.print("E1: ");
    Serial.print(e1Count);

    Serial.print(" | E2: ");
    Serial.print(e2Count);

    Serial.print(" | X: ");
    Serial.print(currentPosX);

    Serial.print(" | Y: ");
    Serial.print(currentPosY);

    Serial.print(" | L:");
    Serial.print(isMovingLeft);

    Serial.print(" R:");
    Serial.print(isMovingRight);

    Serial.print(" U:");
    Serial.print(isMovingUp);

    Serial.print(" D:");
    Serial.println(isMovingDown);

    lastEncoderPrint = millis();
}

  // ==========================================================================
  // 2. CONTINUOUS SOFTWARE WORKSPACE LIMIT MONITOR
  // ==========================================================================

  applyContinuousWorkspaceLimit();

  // ==========================================================================
  // 3. LIMIT SWITCH SAFETY & BOUNCE BACK
  // ==========================================================================

  bool limitX = isSwitchStablyPressed(LIMIT_X_PIN, 30);
  bool limitY = isSwitchStablyPressed(LIMIT_Y_PIN, 30);
  bool limitZ = false;

  if (limitX || limitY || limitZ) {
    stopAllMotors();

    Serial.println("WARNING: Limit switch hit! Bouncing back...");

    int bounceSteps = (int)stepsPerCM;
    int bounceDelay = 800;

    if (limitX) {
      digitalWrite(DIR1_PIN, LOW);
      digitalWrite(DIR2_PIN, HIGH);

      for (int i = 0; i < bounceSteps; i++) {
        digitalWrite(PUL1_PIN, HIGH);
        digitalWrite(PUL2_PIN, HIGH);
        delayMicroseconds(bounceDelay);

        digitalWrite(PUL1_PIN, LOW);
        digitalWrite(PUL2_PIN, LOW);
        delayMicroseconds(bounceDelay);
      }
    }

    if (limitY) {
      digitalWrite(DIR1_PIN, LOW);
      digitalWrite(DIR2_PIN, LOW);

      for (int i = 0; i < bounceSteps; i++) {
        digitalWrite(PUL1_PIN, HIGH);
        digitalWrite(PUL2_PIN, HIGH);
        delayMicroseconds(bounceDelay);

        digitalWrite(PUL1_PIN, LOW);
        digitalWrite(PUL2_PIN, LOW);
        delayMicroseconds(bounceDelay);
      }
    }

    stopAllMotors();

    isCommandReady = false;
    bufferIndex = 0;

    delay(200);
  }

  // ==========================================================================
  // 4. SERVO AUTO-DETACH
  // ==========================================================================

  if (isServoTimerActive && (millis() - servoMoveStartTime >= 2000)) {
    mainServo.detach();
    isServoTimerActive = false;
  }

  // ==========================================================================
  // 5. SERIAL COMMAND RECEIVING
  // ==========================================================================

  while (Serial.available() > 0 && !isCommandReady) {
    char incomingChar = Serial.read();

    if (incomingChar == '\r' || incomingChar == '\n') {
      serialBuffer[bufferIndex] = '\0';
      isCommandReady = true;
    } else {
      if (bufferIndex < MAX_BUFFER_SIZE - 1) {
        serialBuffer[bufferIndex] = incomingChar;
        bufferIndex++;
      }
    }
  }

  // ==========================================================================
  // 6. COMMAND PARSING & EXECUTION
  // ==========================================================================

  if (isCommandReady) {
    String data = String(serialBuffer);
    data.trim();

    if (data == "ESP32-CHECK") {
      Serial.println("ESP32-READY");
    }
    else if (data.length() > 0) {
      int commaIndexOne = data.indexOf(',');
      int commaIndexTwo = data.indexOf(',', commaIndexOne + 1);
      int commaIndexThree = data.indexOf(',', commaIndexTwo + 1);

      if (commaIndexOne > 0 && commaIndexTwo > 0 && commaIndexThree > 0) {
        posX = data.substring(0, commaIndexOne).toInt();
        posY = data.substring(commaIndexOne + 1, commaIndexTwo).toInt();

        int speedValue = data.substring(commaIndexTwo + 1, commaIndexThree).toInt();

        pressedKeys = data.substring(commaIndexThree + 1);

        if (speedValue >= 1 && speedValue <= 100) {
          delayCoreXY = (int)(1000000.0 / (100.0 + ((speedValue - 1.0) / 99.0) * 9900.0));
        }

        if (pressedKeys.indexOf('p') >= 0) {
          stopAllMotors();
        }

        else if (pressedKeys.indexOf('h') >= 0) {
          performHoming();
        }

        else {
          bool moveUp = (pressedKeys.indexOf('i') >= 0);
          bool moveDown = (pressedKeys.indexOf('k') >= 0);
          bool moveLeft = (pressedKeys.indexOf('j') >= 0);
          bool moveRight = (pressedKeys.indexOf('l') >= 0);

          // If no keyboard movement, use posX and posY joystick/mouse values
          if (!moveUp && !moveDown && !moveLeft && !moveRight) {
            int deadzoneX = 15;
            int deadzoneY = 15;

            if (posX > deadzoneX) {
              moveRight = true;
            } else if (posX < -deadzoneX) {
              moveLeft = true;
            }

            if (posY > deadzoneY) {
              moveUp = true;
            } else if (posY < -deadzoneY) {
              moveDown = true;
            }
          }

          // Update position right before checking limits
          updateEncoderPosition();

          // SOFTWARE ENDSTOPS - INITIAL CHECK
          blockMoveIfWouldExceedLimit(moveUp, moveDown, moveLeft, moveRight);

          // Reset continuous tracking flags before setting new ones
          isMovingUp = false;
          isMovingDown = false;
          isMovingLeft = false;
          isMovingRight = false;

          // ==================================================================
          // APPLY COREXY MOVEMENT
          // ==================================================================

          if (moveUp && moveLeft) {
            setMotorsXY(false, LOW, true, HIGH);
            isMovingUp = true;
            isMovingLeft = true;
          }

          else if (moveUp && moveRight) {
            setMotorsXY(true, HIGH, false, LOW);
            isMovingUp = true;
            isMovingRight = true;
          }

          else if (moveDown && moveLeft) {
            setMotorsXY(true, LOW, false, LOW);
            isMovingDown = true;
            isMovingLeft = true;
          }

          else if (moveDown && moveRight) {
            setMotorsXY(false, LOW, true, LOW);
            isMovingDown = true;
            isMovingRight = true;
          }

          else if (moveUp) {
            setMotorsXY(true, HIGH, true, HIGH);
            isMovingUp = true;
          }

          else if (moveDown) {
            setMotorsXY(true, LOW, true, LOW);
            isMovingDown = true;
          }

          else if (moveLeft) {
            setMotorsXY(true, LOW, true, HIGH);
            isMovingLeft = true;
          }

          else if (moveRight) {
            setMotorsXY(true, HIGH, true, LOW);
            isMovingRight = true;
          }

          else {
            stopAllMotors();
          }

          // ==================================================================
          // Z AXIS
          // ==================================================================

          if (pressedKeys.indexOf('z') >= 0) {
            moveZ(HIGH);
          }

          else if (pressedKeys.indexOf('x') >= 0) {
            moveZ(LOW);
          }

          else {
            motorZRunning = false;
          }

          // ==================================================================
          // SERVO
          // ==================================================================

          if (pressedKeys.indexOf('v') >= 0 && (millis() - lastServoToggle > 500)) {
            servoState = !servoState;

            mainServo.attach(SERVO_PIN);
            mainServo.write(servoState ? angleDown : angleUp);

            servoMoveStartTime = millis();
            isServoTimerActive = true;
            lastServoToggle = millis();
          }

          // ==================================================================
          // RELAYS
          // ==================================================================

          digitalWrite(RELAY1_PIN, (pressedKeys.indexOf('1') >= 0) ? HIGH : LOW);
          digitalWrite(RELAY2_PIN, (pressedKeys.indexOf('2') >= 0) ? HIGH : LOW);
        }
      }
    }

    bufferIndex = 0;
    isCommandReady = false;
  }

  // ==========================================================================
  // 7. STEP GENERATION
  // ==========================================================================

  if (!motor1Running && !motor2Running && !motorZRunning) {
    delay(1);
    return;
  }

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