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
#define RELAY1_PIN 27
#define RELAY2_PIN 26

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
int targetDetected = 0;

// ============================================================================
// CONFIGURATION & STATE VARIABLES
// ============================================================================

int delayCoreXY = 700;
const int delayZ = 50;
int homingDelay = 600;

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

long currentZSteps = 0;
long stepsForZDrop = 5800;
bool wasLimitZPressed = false;
bool isZUp = false;

// ============================================================================
// ENCODER AXIS SIGN CALIBRATION
// ============================================================================
//
// Real behavior in this setup:
// - moving left increases X
// - moving right decreases X
// - moving down increases Y
// - moving up decreases Y
//
// If it behaves inversely, change SIGN_X or SIGN_Y from 1 to -1.

const int SIGN_X = 1;
const int SIGN_Y = -1;

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
// After homing and back-off:
// X: from 0.00 cm to 24.50 cm
// Y: from 0.00 cm to 28.50 cm

const float LIMIT_MIN_X = 0.00;
const float LIMIT_MAX_X = 24.50;
const float LIMIT_MIN_Y = 0.00;
const float LIMIT_MAX_Y = 28.50;
const float LIMIT_MARGIN_CM = 0.30;

// ============================================================================
// AUTO RECOVERY SETTINGS
// ============================================================================
//
// When XY hits a software limit:
// 1. Save current Z position.
// 2. Lift Z quickly.
// 3. Move XY to center at the same time.
// 4. After half of XY path is completed, lower Z back to saved position.

bool isAutoRecovering = false;

const float CENTER_TOLERANCE_CM = 0.20;

const int RECOVERY_XY_DELAY = 350;
const int RECOVERY_Z_DELAY = 220;

const long MAX_Z_RECOVERY_STEPS = 9000;
const unsigned long MAX_RECOVERY_TIME_MS = 12000;

int posX = 0;
int posY = 0;
String pressedKeys = "";

// ============================================================================
// VISION PID / P CONTROL SETTINGS
// ============================================================================

int targetOffsetPxX = 0;
int targetOffsetPxY = 0;
int isHoldingSniper = 0;
int maxSpeedValue = 75;

bool visionControlActive = false;

float visionTargetX = 0.0;
float visionTargetY = 0.0;

// Kalibracja: ile cm ruchu myszy odpowiada 1 pikselowi błędu na ekranie.
// To trzeba dobrać testowo.
float pxToCmX = 0.0021167;
float pxToCmY = 0.0021167;

// Na start robimy P, bez I i bez D.
// Jak będzie stabilne, można dodać delikatne D.
float kpVision = 80.0;
float kdVision = 3.0;

float prevVisionErrorX = 0.0;
float prevVisionErrorY = 0.0;
unsigned long lastVisionPidMicros = 0;

float filteredOffsetX = 0.0;
float filteredOffsetY = 0.0;
const float VISION_FILTER_ALPHA = 0.35;

// Martwa strefa w pikselach — jak cel jest blisko środka, robot stoi.
const int VISION_DEADZONE_PX_X = 7;
const int VISION_DEADZONE_PX_Y = 7;

// Martwa strefa pozycji w cm dla enkoderów.
const float VISION_TARGET_TOLERANCE_CM = 0.01;



// ============================================================================
// VISION CENTERED EVENT SETTINGS
// ============================================================================

bool wasVisionCentered = false;
unsigned long lastVisionCenteredEventMs = 0;
const unsigned long VISION_CENTERED_COOLDOWN_MS = 250;

// ============================================================================
// FIRE / RELAY1 RATE LIMIT
// ============================================================================

const unsigned long FIRE_HOLD_MS = 70;       // ile ms trzymać solenoid
const unsigned long FIRE_GAP_MS = 300;       // minimalna przerwa między strzałami

bool fireRequestActive = false;              // czy aktualnie chcemy strzelać
bool fireOutputActive = false;               // czy RELAY1 jest teraz HIGH

unsigned long fireStartMs = 0;
unsigned long lastFireEndMs = 0;

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================

bool checkEmergencyStop();

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

  float ticksX = (e1Count + e2Count) / 2.0;
  float ticksY = (e1Count - e2Count) / 2.0;

  currentPosX = (SIGN_X * ticksX / stepsPerCM) + 1.0;
  currentPosY = (SIGN_Y * ticksY / stepsPerCM) + 1.0;
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

// ============================================================================
// DEBUG PRINT
// ============================================================================

void printSoftLimitDebug(const char* limitName, const char* reason) {
  long e1Count = encoder1.getCount();
  long e2Count = encoder2.getCount();

  Serial.println();
  Serial.println("==================================================");
  Serial.print("SOFT LIMIT STOP: ");
  Serial.println(limitName);

  Serial.print("Reason: ");
  Serial.println(reason);

  Serial.print("currentPosX = ");
  Serial.println(currentPosX, 4);

  Serial.print("currentPosY = ");
  Serial.println(currentPosY, 4);

  Serial.print("LIMIT_MIN_X = ");
  Serial.println(LIMIT_MIN_X, 4);

  Serial.print("LIMIT_MAX_X = ");
  Serial.println(LIMIT_MAX_X, 4);

  Serial.print("LIMIT_MIN_Y = ");
  Serial.println(LIMIT_MIN_Y, 4);

  Serial.print("LIMIT_MAX_Y = ");
  Serial.println(LIMIT_MAX_Y, 4);

  Serial.print("LIMIT_MARGIN_CM = ");
  Serial.println(LIMIT_MARGIN_CM, 4);

  Serial.print("X MIN trigger value = ");
  Serial.println(LIMIT_MIN_X + LIMIT_MARGIN_CM, 4);

  Serial.print("X MAX trigger value = ");
  Serial.println(LIMIT_MAX_X - LIMIT_MARGIN_CM, 4);

  Serial.print("Y MIN trigger value = ");
  Serial.println(LIMIT_MIN_Y + LIMIT_MARGIN_CM, 4);

  Serial.print("Y MAX trigger value = ");
  Serial.println(LIMIT_MAX_Y - LIMIT_MARGIN_CM, 4);

  Serial.print("E1 = ");
  Serial.println(e1Count);

  Serial.print("E2 = ");
  Serial.println(e2Count);

  Serial.print("Moving flags | L=");
  Serial.print(isMovingLeft);
  Serial.print(" R=");
  Serial.print(isMovingRight);
  Serial.print(" U=");
  Serial.print(isMovingUp);
  Serial.print(" D=");
  Serial.println(isMovingDown);

  Serial.print("Motor flags | M1=");
  Serial.print(motor1Running);
  Serial.print(" M2=");
  Serial.print(motor2Running);
  Serial.print(" MZ=");
  Serial.println(motorZRunning);

  Serial.println("Motors stopped by software workspace limit.");
  Serial.println("==================================================");
  Serial.println();
}

// ============================================================================
// AUTO RECOVERY: LIFT Z + CENTER XY + RESTORE Z FROM HALF PATH
// ============================================================================

void setXYDirectionToCenter(bool moveU, bool moveD, bool moveL, bool moveR) {
  if (moveU && moveR) {
    setMotorsXY(true, HIGH, false, LOW);
  } else if (moveU && moveL) {
    setMotorsXY(false, LOW, true, LOW);
  } else if (moveD && moveR) {
    setMotorsXY(false, LOW, true, HIGH);
  } else if (moveD && moveL) {
    setMotorsXY(true, LOW, false, LOW);
  } else if (moveU) {
    setMotorsXY(true, HIGH, true, LOW);
  } else if (moveD) {
    setMotorsXY(true, LOW, true, HIGH);
  } else if (moveR) {
    setMotorsXY(true, HIGH, true, HIGH);
  } else if (moveL) {
    setMotorsXY(true, LOW, true, LOW);
  } else {
    motor1Running = false;
    motor2Running = false;
    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);
  }
}

float distanceToPoint(float x1, float y1, float x2, float y2) {
  float dx = x2 - x1;
  float dy = y2 - y1;
  return sqrt((dx * dx) + (dy * dy));
}

void stepXYRecovery() {
  if (motor1Running) digitalWrite(PUL1_PIN, HIGH);
  if (motor2Running) digitalWrite(PUL2_PIN, HIGH);

  delayMicroseconds(4);

  if (motor1Running) digitalWrite(PUL1_PIN, LOW);
  if (motor2Running) digitalWrite(PUL2_PIN, LOW);
}

void stepZRecovery(bool zUpDirection) {
  digitalWrite(PULZ_PIN, HIGH);
  delayMicroseconds(4);
  digitalWrite(PULZ_PIN, LOW);

  if (zUpDirection) {
    currentZSteps++;
  } else {
    currentZSteps--;
  }
}

// ============================================================================
// AUTO RECOVERY: LIFT Z -> CENTER XY -> DROP Z (SEQUENTIAL)
// ============================================================================

void autoLiftCenterAndRestoreZ(const char* reason) {
  if (isAutoRecovering) {
    return;
  }

  isAutoRecovering = true;

  Serial.println();
  Serial.println("==================================================");
  Serial.println("AUTO RECOVERY START");
  Serial.print("Reason: ");
  Serial.println(reason);
  Serial.println("Mode: Sequential (Lift Z -> Move to Center -> Drop Z)");
  Serial.println("==================================================");
  Serial.println();

  stopAllMotors();
  delay(30);

  // 1. Lift the mouse safely before any horizontal movement
  zLift();

  // 2. Move XY to the center workspace position safely
  moveToCenter(100);

  // 3. Drop the mouse back down to its working position
  zDrop();

  Serial.println();
  Serial.println("==================================================");
  Serial.println("AUTO RECOVERY END");
  Serial.println("==================================================");
  Serial.println();

  isAutoRecovering = false;
}

// ============================================================================
// CONTINUOUS SOFTWARE WORKSPACE LIMIT MONITOR
// ============================================================================

void applyContinuousWorkspaceLimit() {
  if (isAutoRecovering) {
    return;
  }

  if (isMovingLeft && currentPosX >= LIMIT_MAX_X - LIMIT_MARGIN_CM) {
    printSoftLimitDebug(
      "X MAX",
      "isMovingLeft == true AND currentPosX >= LIMIT_MAX_X - LIMIT_MARGIN_CM"
    );
    autoLiftCenterAndRestoreZ("SOFT LIMIT X MAX");
  }

  if (isMovingRight && currentPosX <= LIMIT_MIN_X + LIMIT_MARGIN_CM) {
    printSoftLimitDebug(
      "X MIN",
      "isMovingRight == true AND currentPosX <= LIMIT_MIN_X + LIMIT_MARGIN_CM"
    );
    autoLiftCenterAndRestoreZ("SOFT LIMIT X MIN");
  }

  if (isMovingDown && currentPosY >= LIMIT_MAX_Y - LIMIT_MARGIN_CM) {
    printSoftLimitDebug(
      "Y MAX",
      "isMovingDown == true AND currentPosY >= LIMIT_MAX_Y - LIMIT_MARGIN_CM"
    );
    autoLiftCenterAndRestoreZ("SOFT LIMIT Y MAX");
  }

  if (isMovingUp && currentPosY <= LIMIT_MIN_Y + LIMIT_MARGIN_CM) {
    printSoftLimitDebug(
      "Y MIN",
      "isMovingUp == true AND currentPosY <= LIMIT_MIN_Y + LIMIT_MARGIN_CM"
    );
    autoLiftCenterAndRestoreZ("SOFT LIMIT Y MIN");
  }
}

void blockMoveIfWouldExceedLimit(bool &moveUp, bool &moveDown, bool &moveLeft, bool &moveRight) {
  if (moveLeft && currentPosX >= LIMIT_MAX_X - LIMIT_MARGIN_CM) {
    Serial.println();
    Serial.println("BLOCKED BEFORE MOVE: moveLeft - X MAX");
    Serial.print("currentPosX = ");
    Serial.println(currentPosX, 4);
    Serial.print("currentPosY = ");
    Serial.println(currentPosY, 4);
    Serial.print("E1 = ");
    Serial.println(encoder1.getCount());
    Serial.print("E2 = ");
    Serial.println(encoder2.getCount());
    Serial.println();

    moveLeft = false;
  }

  if (moveRight && currentPosX <= LIMIT_MIN_X + LIMIT_MARGIN_CM) {
    Serial.println();
    Serial.println("BLOCKED BEFORE MOVE: moveRight - X MIN");
    Serial.print("currentPosX = ");
    Serial.println(currentPosX, 4);
    Serial.print("currentPosY = ");
    Serial.println(currentPosY, 4);
    Serial.print("E1 = ");
    Serial.println(encoder1.getCount());
    Serial.print("E2 = ");
    Serial.println(encoder2.getCount());
    Serial.println();

    moveRight = false;
  }

  if (moveDown && currentPosY >= LIMIT_MAX_Y - LIMIT_MARGIN_CM) {
    Serial.println();
    Serial.println("BLOCKED BEFORE MOVE: moveDown - Y MAX");
    Serial.print("currentPosX = ");
    Serial.println(currentPosX, 4);
    Serial.print("currentPosY = ");
    Serial.println(currentPosY, 4);
    Serial.print("E1 = ");
    Serial.println(encoder1.getCount());
    Serial.print("E2 = ");
    Serial.println(encoder2.getCount());
    Serial.println();

    moveDown = false;
  }

  if (moveUp && currentPosY <= LIMIT_MIN_Y + LIMIT_MARGIN_CM) {
    Serial.println();
    Serial.println("BLOCKED BEFORE MOVE: moveUp - Y MIN");
    Serial.print("currentPosX = ");
    Serial.println(currentPosX, 4);
    Serial.print("currentPosY = ");
    Serial.println(currentPosY, 4);
    Serial.print("E1 = ");
    Serial.println(encoder1.getCount());
    Serial.print("E2 = ");
    Serial.println(encoder2.getCount());
    Serial.println();

    moveUp = false;
  }
}

// ============================================================================
// EMERGENCY STOP HELPER
// ============================================================================

bool checkEmergencyStop() {
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

  if (isCommandReady) {
    String data = String(serialBuffer);

    if (data.indexOf('p') >= 0) {
      stopAllMotors();
      Serial.println("EMERGENCY STOP during blocking operation!");

      bufferIndex = 0;
      isCommandReady = false;
      posX = 0;
      posY = 0;

      return true;
    }

    bufferIndex = 0;
    isCommandReady = false;
  }

  return false;
}

// ============================================================================
// Z-AXIS CONTROL FUNCTIONS
// ============================================================================

void zLift() {
  Serial.println("Lifting Z axis to endstop...");

  digitalWrite(DIRZ_PIN, LOW);

  while (!isSwitchStablyPressed(LIMIT_Z_PIN, 90)) {
    if (checkEmergencyStop()) return;

    digitalWrite(PULZ_PIN, HIGH);
    delayMicroseconds(delayZ);
    digitalWrite(PULZ_PIN, LOW);
    delayMicroseconds(delayZ);
  }

  Serial.println("Z limit hit. Backing off...");

  digitalWrite(DIRZ_PIN, HIGH);

  for (int i = 0; i < 200; i++) {
    if (checkEmergencyStop()) return;

    digitalWrite(PULZ_PIN, HIGH);
    delayMicroseconds(delayZ);
    digitalWrite(PULZ_PIN, LOW);
    delayMicroseconds(delayZ);
  }

  isZUp = true;
  currentZSteps = 0;

  Serial.println("Z axis is UP and homed (Z=0).");
}

void zDrop() {
  if (currentZSteps < -100) {
    Serial.println("Z DROP BLOCKED: Z axis is already lowered (currentZSteps < -100).");
    return;
  }
  Serial.println("Dropping Z axis...");

  digitalWrite(DIRZ_PIN, HIGH);

  for (long i = 0; i < stepsForZDrop; i++) {
    if (checkEmergencyStop()) return;

    digitalWrite(PULZ_PIN, HIGH);
    delayMicroseconds(delayZ);
    digitalWrite(PULZ_PIN, LOW);
    delayMicroseconds(delayZ);
  }

  isZUp = false;
  currentZSteps = -stepsForZDrop;

  Serial.println("Z axis is DOWN.");
}

// ============================================================================
// CENTERING FUNCTION
// ============================================================================

void moveToCenter(int speedDelay) {
  Serial.println("Moving to workspace center...");
  zLift();

  float targetX = LIMIT_MAX_X / 2.0;
  float targetY = LIMIT_MAX_Y / 2.0;

  while (true) {
    if (checkEmergencyStop()) return;

    updateEncoderPosition();

    bool moveU = false;
    bool moveD = false;
    bool moveL = false;
    bool moveR = false;

    if (currentPosX < targetX - 0.15) moveL = true;
    else if (currentPosX > targetX + 0.15) moveR = true;

    if (currentPosY < targetY - 0.15) moveD = true;
    else if (currentPosY > targetY + 0.15) moveU = true;

    if (!moveU && !moveD && !moveL && !moveR) {
      break;
    }

    if (moveU && moveR) {
      setMotorsXY(true, HIGH, false, LOW);
    } else if (moveU && moveL) {
      setMotorsXY(false, LOW, true, LOW);
    } else if (moveD && moveR) {
      setMotorsXY(false, LOW, true, HIGH);
    } else if (moveD && moveL) {
      setMotorsXY(true, LOW, false, LOW);
    } else if (moveU) {
      setMotorsXY(true, HIGH, true, LOW);
    } else if (moveD) {
      setMotorsXY(true, LOW, true, HIGH);
    } else if (moveR) {
      setMotorsXY(true, HIGH, true, HIGH);
    } else if (moveL) {
      setMotorsXY(true, LOW, true, LOW);
    }

    if (motor1Running) digitalWrite(PUL1_PIN, HIGH);
    if (motor2Running) digitalWrite(PUL2_PIN, HIGH);

    delayMicroseconds(speedDelay);

    if (motor1Running) digitalWrite(PUL1_PIN, LOW);
    if (motor2Running) digitalWrite(PUL2_PIN, LOW);

    delayMicroseconds(speedDelay);
  }

  stopAllMotors();

  Serial.println("Center reached.");

  zDrop();
}

// ============================================================================
// HOMING SEQUENCE
// ============================================================================

void performHoming() {
  Serial.println("Homing start...");

  stopAllMotors();

  int backoffSteps = (int)stepsPerCM;
  int debounceLimitMs = 50;

  // ==========================================================================
  // 1. Y-AXIS HOMING
  // ==========================================================================

  Serial.println("Homing Y...");

  digitalWrite(DIR1_PIN, HIGH);
  digitalWrite(DIR2_PIN, LOW);

  while (!isSwitchStablyPressed(LIMIT_X_PIN, debounceLimitMs)) {
    if (checkEmergencyStop()) return;

    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);
    delayMicroseconds(homingDelay);
  }

  Serial.println("Y limit hit. Backing off...");

  digitalWrite(DIR1_PIN, LOW);
  digitalWrite(DIR2_PIN, HIGH);

  for (int i = 0; i < backoffSteps; i++) {
    if (checkEmergencyStop()) return;

    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);
    delayMicroseconds(homingDelay);
  }

  delay(200);

  // ==========================================================================
  // 2. X-AXIS HOMING
  // ==========================================================================

  Serial.println("Homing X...");

  digitalWrite(DIR1_PIN, HIGH);
  digitalWrite(DIR2_PIN, HIGH);

  while (!isSwitchStablyPressed(LIMIT_Y_PIN, debounceLimitMs)) {
    if (checkEmergencyStop()) return;

    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);
    delayMicroseconds(homingDelay);
  }

  Serial.println("X limit hit. Backing off...");

  digitalWrite(DIR1_PIN, LOW);
  digitalWrite(DIR2_PIN, LOW);

  for (int i = 0; i < backoffSteps; i++) {
    if (checkEmergencyStop()) return;

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

  currentPosX = 1.0;
  currentPosY = 1.0;

  stopAllMotors();

  Serial.println("Homing OK! Position set to 0,0.");

  delay(500);

  Serial.println("Centering.");

  moveToCenter(500);
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

void applyCoreXYMovement(bool moveUp, bool moveDown, bool moveLeft, bool moveRight) {
  isMovingUp = false;
  isMovingDown = false;
  isMovingLeft = false;
  isMovingRight = false;

  if (moveUp && moveLeft) {
    setMotorsXY(false, LOW, true, LOW);
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
    setMotorsXY(false, LOW, true, HIGH);
    isMovingDown = true;
    isMovingRight = true;
  }

  else if (moveUp) {
    setMotorsXY(true, HIGH, true, LOW);
    isMovingUp = true;
  }

  else if (moveDown) {
    setMotorsXY(true, LOW, true, HIGH);
    isMovingDown = true;
  }

  else if (moveLeft) {
    setMotorsXY(true, LOW, true, LOW);
    isMovingLeft = true;
  }

  else if (moveRight) {
    setMotorsXY(true, HIGH, true, HIGH);
    isMovingRight = true;
  }

  else {
    stopAllMotors();
  }
}

void setDelayFromSpeedPercent(int speedPercent) {
  if (maxSpeedValue <= 0 || speedPercent <= 0) {
    stopAllMotors();
    return;
  }

  if (speedPercent > maxSpeedValue) {
    speedPercent = maxSpeedValue;
  }

  if (speedPercent < 1) {
    speedPercent = 1;
  }

  if (speedPercent > 100) {
    speedPercent = 100;
  }

  delayCoreXY = (int)(1000000.0 / (100.0 + ((speedPercent - 1.0) / 99.0) * 9900.0));
}

void applyVisionPControl() {
  updateEncoderPosition();

  // Jeżeli cel jest już blisko środka ekranu, zatrzymaj XY.
  bool isVisionCenteredNow =
  abs(targetOffsetPxX) <= VISION_DEADZONE_PX_X &&
  abs(targetOffsetPxY) <= VISION_DEADZONE_PX_Y;

  if (isVisionCenteredNow) {
    stopAllMotors();
    prevVisionErrorX = 0.0;
    prevVisionErrorY = 0.0;
    lastVisionPidMicros = 0;
    filteredOffsetX = 0.0;
    filteredOffsetY = 0.0;

    unsigned long nowMs = millis();

    if (!wasVisionCentered &&
        nowMs - lastVisionCenteredEventMs >= VISION_CENTERED_COOLDOWN_MS) {

      Serial.println("VISION CENTERED EVENT");

      lastVisionCenteredEventMs = nowMs;
    }

    wasVisionCentered = true;
    return;
  }

  wasVisionCentered = false;

  // ========================================================================
  // PIXELS -> ROBOT TARGET POSITION
  // ========================================================================
  //
  // Założenie:
  // ekran X dodatni = cel po prawej -> mysz musi iść w prawo.
  // U Ciebie fizycznie ruch w prawo zmniejsza currentPosX,
  // więc target X = current X - offsetX * skala.
  //
  // ekran Y dodatni = cel niżej -> mysz musi iść w dół.
  // U Ciebie ruch w dół zwiększa currentPosY,
  // więc target Y = current Y + offsetY * skala.
  //
  // Jeśli GUI już odwraca Y, wtedy znak przy Y trzeba będzie zmienić.

  filteredOffsetX = filteredOffsetX + VISION_FILTER_ALPHA * ((float)targetOffsetPxX - filteredOffsetX);
  filteredOffsetY = filteredOffsetY + VISION_FILTER_ALPHA * ((float)targetOffsetPxY - filteredOffsetY);

  visionTargetX = currentPosX - (filteredOffsetX * pxToCmX);
  visionTargetY = currentPosY - (filteredOffsetY * pxToCmY);

  // Ogranicz target do obszaru roboczego, żeby PID nie próbował wyjechać poza ramę.
  if (visionTargetX < LIMIT_MIN_X + LIMIT_MARGIN_CM) visionTargetX = LIMIT_MIN_X + LIMIT_MARGIN_CM;
  if (visionTargetX > LIMIT_MAX_X - LIMIT_MARGIN_CM) visionTargetX = LIMIT_MAX_X - LIMIT_MARGIN_CM;

  if (visionTargetY < LIMIT_MIN_Y + LIMIT_MARGIN_CM) visionTargetY = LIMIT_MIN_Y + LIMIT_MARGIN_CM;
  if (visionTargetY > LIMIT_MAX_Y - LIMIT_MARGIN_CM) visionTargetY = LIMIT_MAX_Y - LIMIT_MARGIN_CM;

  float errorX = visionTargetX - currentPosX;
  float errorY = visionTargetY - currentPosY;

  // Jeżeli fizycznie jesteśmy blisko pozycji docelowej, zatrzymaj.
  if (abs(errorX) <= VISION_TARGET_TOLERANCE_CM &&
      abs(errorY) <= VISION_TARGET_TOLERANCE_CM) {
    stopAllMotors();
    return;
  }

  // ========================================================================
  // P / PD OUTPUT
  // ========================================================================

  unsigned long nowMicros = micros();
  float dt = 0.001;

  if (lastVisionPidMicros > 0) {
    dt = (nowMicros - lastVisionPidMicros) / 1000000.0;
    if (dt <= 0.0001) dt = 0.0001;
  }

  float derivativeX = (errorX - prevVisionErrorX) / dt;
  float derivativeY = (errorY - prevVisionErrorY) / dt;

  const float MAX_DERIVATIVE = 2.0;

  if (derivativeX > MAX_DERIVATIVE) derivativeX = MAX_DERIVATIVE;
  if (derivativeX < -MAX_DERIVATIVE) derivativeX = -MAX_DERIVATIVE;

  if (derivativeY > MAX_DERIVATIVE) derivativeY = MAX_DERIVATIVE;
  if (derivativeY < -MAX_DERIVATIVE) derivativeY = -MAX_DERIVATIVE;

  float outputX = kpVision * errorX + kdVision * derivativeX;
  float outputY = kpVision * errorY + kdVision * derivativeY;

  prevVisionErrorX = errorX;
  prevVisionErrorY = errorY;
  lastVisionPidMicros = nowMicros;

  // ========================================================================
  // OUTPUT -> DIRECTION
  // ========================================================================
  //
  // currentPosX większe = bardziej w lewo.
  // Jeśli outputX dodatni, target jest bardziej w lewo -> moveLeft.
  // Jeśli outputX ujemny, target jest bardziej w prawo -> moveRight.
  //
  // currentPosY większe = bardziej w dół.
  // Jeśli outputY dodatni -> moveDown.
  // Jeśli outputY ujemny -> moveUp.

  float outputDeadband = 1.0;

  bool moveLeft = outputX > outputDeadband;
  bool moveRight = outputX < -outputDeadband;

  bool moveDown = outputY > outputDeadband;
  bool moveUp = outputY < -outputDeadband;

  blockMoveIfWouldExceedLimit(moveUp, moveDown, moveLeft, moveRight);

  // ========================================================================
  // OUTPUT -> SPEED
  // ========================================================================

  float magnitude = sqrt((outputX * outputX) + (outputY * outputY));

  int pidSpeed = (int)magnitude;

  if (pidSpeed > maxSpeedValue) pidSpeed = maxSpeedValue;
  if (pidSpeed < 4) pidSpeed = 3;

  if (maxSpeedValue <= 0 || pidSpeed <= 0) {
    stopAllMotors();
    return;
  }

  setDelayFromSpeedPercent(pidSpeed);
  applyCoreXYMovement(moveUp, moveDown, moveLeft, moveRight);
}

void updateFireControl() {
  unsigned long nowMs = millis();

  // 1. Jeżeli RELAY1 jest aktywny, wyłącz go po FIRE_HOLD_MS
  if (fireOutputActive) {
    if (nowMs - fireStartMs >= FIRE_HOLD_MS) {
      digitalWrite(RELAY1_PIN, LOW);
      fireOutputActive = false;
      lastFireEndMs = nowMs;

      Serial.println("FIRE END");
    }

    return;
  }

  // 2. Jeżeli nie ma żądania strzału, trzymamy LOW
  if (!fireRequestActive) {
    digitalWrite(RELAY1_PIN, LOW);
    return;
  }

  // 3. Jeżeli jest żądanie strzału, ale cooldown jeszcze trwa, czekamy
  if (lastFireEndMs != 0 && (nowMs - lastFireEndMs < FIRE_GAP_MS)) {
    digitalWrite(RELAY1_PIN, LOW);
    return;
  }

  // 4. Można strzelić
  digitalWrite(RELAY1_PIN, HIGH);
  fireOutputActive = true;
  fireStartMs = nowMs;

  Serial.println("FIRE START");
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

    Serial.print(" | Z: ");
    Serial.print(currentZSteps);

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
  // Z-AXIS LIMIT NOTE
  // ==========================================================================
  //
  // Z limit is intentionally NOT checked with debounce in the main loop.
  // Reason: when the Z endstop is physically pressed, XY must still be able
  // to move normally. The Z limit is checked only when Z is moving UP.

  // ==========================================================================
  // 3. LIMIT SWITCH SAFETY & BOUNCE BACK
  // ==========================================================================

  bool limitX = isSwitchStablyPressed(LIMIT_X_PIN, 90);
  bool limitY = isSwitchStablyPressed(LIMIT_Y_PIN, 90);
  bool limitZ = false;

  if (limitX || limitY || limitZ) {
    stopAllMotors();

    Serial.println();
    Serial.println("==================================================");
    Serial.println("WARNING: Limit switch hit! Bouncing back...");
    Serial.print("limitX = ");
    Serial.println(limitX);
    Serial.print("limitY = ");
    Serial.println(limitY);
    Serial.print("currentPosX = ");
    Serial.println(currentPosX, 4);
    Serial.print("currentPosY = ");
    Serial.println(currentPosY, 4);
    Serial.print("E1 = ");
    Serial.println(encoder1.getCount());
    Serial.print("E2 = ");
    Serial.println(encoder2.getCount());
    Serial.println("==================================================");
    Serial.println();

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
      isCommandReady = false;
      bufferIndex = 0;
    }
    else if (data.length() > 0) {
      int commaIndexes[5] = {0, 0, 0, 0, 0};
      int commaIndex = 0;
      for (int index = 0; index < data.length(); index++) {
        if (data[index] == ',') {
          if (commaIndex < 5) {
            commaIndexes[commaIndex] = index;
            commaIndex++;
          }
        }
      }
      
      if (commaIndex == 5) {
        targetOffsetPxX = data.substring(0, commaIndexes[0]).toInt();
        targetOffsetPxY = data.substring(commaIndexes[0] + 1, commaIndexes[1]).toInt();
        isHoldingSniper = data.substring(commaIndexes[1] + 1, commaIndexes[2]).toInt();
        pressedKeys = data.substring(commaIndexes[2] + 1, commaIndexes[3]);
        maxSpeedValue = data.substring(commaIndexes[3] + 1, commaIndexes[4]).toInt();
        targetDetected = data.substring(commaIndexes[4] + 1).toInt();

        if (maxSpeedValue < 0) maxSpeedValue = 0;
        if (maxSpeedValue > 100) maxSpeedValue = 100;

        if (pressedKeys.indexOf('p') >= 0) {
          stopAllMotors();
          fireRequestActive = false;
          fireOutputActive = false;
          digitalWrite(RELAY1_PIN, LOW);
        }

        else if (pressedKeys.indexOf('h') >= 0) {
          performHoming();
        }

        else if (pressedKeys.indexOf('c') >= 0) {
          moveToCenter(350);
        }

        else if (pressedKeys.indexOf('u') >= 0) {
          zLift();
        }

        else if (pressedKeys.indexOf('o') >= 0) {
          zDrop();
        }

        else {
          bool moveUp = (pressedKeys.indexOf('i') >= 0);     // +Y command
          bool moveDown = (pressedKeys.indexOf('k') >= 0);   // -Y command
          bool moveLeft = (pressedKeys.indexOf('j') >= 0);   // -X command
          bool moveRight = (pressedKeys.indexOf('l') >= 0);  // +X command

          if (!moveUp && !moveDown && !moveLeft && !moveRight) {
            visionControlActive = true;
            applyVisionPControl();
            
          } else {
            visionControlActive = false;

            updateEncoderPosition();
            blockMoveIfWouldExceedLimit(moveUp, moveDown, moveLeft, moveRight);

            if (maxSpeedValue <= 0) {
              stopAllMotors();
            } else {
              setDelayFromSpeedPercent(maxSpeedValue);
              applyCoreXYMovement(moveUp, moveDown, moveLeft, moveRight);
            }
          }

          // ==================================================================
          // Z AXIS
          // ==================================================================

          if (pressedKeys.indexOf('z') >= 0) {
            // Z DOWN is always allowed.
            moveZ(HIGH);
          }

          else if (pressedKeys.indexOf('x') >= 0) {
            // Z UP is blocked only while the Z endstop is pressed.
            // XY movement is NOT stopped by this.
            if (digitalRead(LIMIT_Z_PIN) == LOW) {
              motorZRunning = false;
              digitalWrite(PULZ_PIN, LOW);
              
              // NEW: Reset Z position when limit is hit manually
              currentZSteps = 0;
              isZUp = true;
              
              Serial.println("Z LIMIT: UP blocked. Z position reset to 0. XY still allowed.");
            } else {
              moveZ(LOW);
            }
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

          bool manualFire = (pressedKeys.indexOf('1') >= 0);
          bool autoFire = false;

          if (visionControlActive && targetDetected == 1 &&
              abs(targetOffsetPxX) <= VISION_DEADZONE_PX_X &&
              abs(targetOffsetPxY) <= VISION_DEADZONE_PX_Y) {
            autoFire = true;
          }

          fireRequestActive = (manualFire || autoFire);
          digitalWrite(RELAY2_PIN, (pressedKeys.indexOf('2') >= 0) ? HIGH : LOW);
        }
      }
    }

    bufferIndex = 0;
    isCommandReady = false;
  }

  updateFireControl();
  // ==========================================================================
  // 7. STEP GENERATION
  // ==========================================================================

  if (!motor1Running && !motor2Running && !motorZRunning) {
    delay(1);
    return;
  }

  // If Z is moving UP and the Z endstop becomes pressed, stop ONLY Z.
  // Do not stop XY motors. This lets the robot keep moving left/right/up/down
  // even with the Z limit switch pressed.
  if (motorZRunning && digitalRead(DIRZ_PIN) == LOW && digitalRead(LIMIT_Z_PIN) == LOW) {
    motorZRunning = false;
    digitalWrite(PULZ_PIN, LOW);

    currentZSteps = 0;
    isZUp = true;
    
    Serial.println("Z LIMIT: Z motor stopped. XY still allowed.");
  }

  int currentDelay = (motorZRunning) ? delayZ : delayCoreXY;

  if (!motorZRunning && (motor1Running != motor2Running)) {
    currentDelay = (int)(currentDelay * 0.707);
  }

  const int MIN_SAFE_DELAY = 120;

  if (currentDelay < MIN_SAFE_DELAY) {
    currentDelay = MIN_SAFE_DELAY;
  }

  if (motor1Running) digitalWrite(PUL1_PIN, HIGH);
  if (motor2Running) digitalWrite(PUL2_PIN, HIGH);

  if (motorZRunning) {
    digitalWrite(PULZ_PIN, HIGH);

    if (digitalRead(DIRZ_PIN) == LOW) {
      currentZSteps++;
    } else {
      currentZSteps--;
    }
  }

  delayMicroseconds(currentDelay);

  if (motor1Running) digitalWrite(PUL1_PIN, LOW);
  if (motor2Running) digitalWrite(PUL2_PIN, LOW);
  if (motorZRunning) digitalWrite(PULZ_PIN, LOW);

  delayMicroseconds(currentDelay);
}