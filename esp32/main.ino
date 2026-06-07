/*
 * CoreXY motor control firmware - predictive tracking workspace version.
 * ESP32-based controller for a CoreXY robotic platform with a Z-axis servo.
 * Limit switches are debounced and used for XY homing and safety.
 * The Z-limit is intentionally ignored in the default workspace logic.
 * Virtual software endstops are configured to 28 cm on X and 24 cm on Y from the origin.
 */

#include <ESP32Servo.h>
#include <ESP32Encoder.h>

// ============================================================================
// Non-blocking debounce state.
// Keep this near the top of the .ino file. Arduino generates function
// prototypes automatically, and custom types must already be known.
// ============================================================================

struct DebouncedInputState {
  bool stablePressed;
  bool lastRawPressed;
  unsigned long lastChangeMs;
};

DebouncedInputState limitXDebounce = {false, false, 0};
DebouncedInputState limitYDebounce = {false, false, 0};


// ============================================================================
// Pin definitions.
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
// Serial command buffer for emergency stop.
// ============================================================================

const int MAX_BUFFER_SIZE = 64;
char serialBuffer[MAX_BUFFER_SIZE];
int bufferIndex = 0;
bool isCommandReady = false;
int targetDetected = 0;

// Statistics tracking
float totalDistanceCm = 0.0;
float lastPosX = 0.0;
float lastPosY = 0.0;
unsigned long lastStatsSentMs = 0;
const unsigned long STATS_SEND_INTERVAL_MS = 5000;

// LMB/RMB click tracking
unsigned long totalLmbClicks = 0;
unsigned long totalRmbClicks = 0;
bool lastFireOutputState = false;
bool lastScopeOutputState = false;

// ============================================================================
// Configurable parameters and state variables.
// ============================================================================

int delayCoreXY = 600;
const int delayZ = 50;
int homingDelay = 600;

bool motor1Running = false;
bool motor2Running = false;
bool motorZRunning = false;

// Tracks active movement for continuous endstop monitoring.
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
float skewAngleX = 0.0;
float skewAngleY = 0.0;

long currentZSteps = 0;
long stepsForZDrop = 5800;
bool wasLimitZPressed = false;
bool isZUp = false;

// ============================================================================
// Encoder axis sign calibration.
// ============================================================================
//
// Actual motion mapping in this setup:
// - Moving left increases X.
// - Moving right decreases X.
// - Moving down increases Y.
// - Moving up decreases Y.
//
// If the axes move in reverse, change SIGN_X or SIGN_Y from 1 to -1.

const int SIGN_X = 1;
const int SIGN_Y = -1;

// ============================================================================
// Servo settings.
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
// Virtual workspace limits.
// ============================================================================
//
// After homing and back-off:
// X ranges from 0.00 cm to 24.50 cm.
// Y ranges from 0.00 cm to 28.50 cm.

const float LIMIT_MIN_X = 0.00;
const float LIMIT_MAX_X = 24.50;
const float LIMIT_MIN_Y = 0.00;
const float LIMIT_MAX_Y = 28.50;
const float LIMIT_MARGIN_CM = 0.30;

// ============================================================================
// Auto-recovery settings.
// ============================================================================
//
// When XY reaches a software limit:
// 1. Save the current Z position.
// 2. Raise Z quickly.
// 3. Move XY toward the center at the same time.
// 4. After half of the XY path is complete, lower Z back to the saved position.

bool isAutoRecovering = false;

const float CENTER_TOLERANCE_CM = 0.20;

const int RECOVERY_XY_DELAY = 350;
const int RECOVERY_Z_DELAY = 220;

const long MAX_Z_RECOVERY_STEPS = 9000;
const unsigned long MAX_RECOVERY_TIME_MS = 12000;

int posX = 0;
int posY = 0;
String pressedKeys = "";
bool isManualJogging = false;
float jogVM1 = 0.0;
float jogVM2 = 0.0;
int jogDirM1 = LOW;
int jogDirM2 = LOW;
float manualAccumM1 = 0.0;
float manualAccumM2 = 0.0;

// ============================================================================
// Vision PD control settings.
// ============================================================================

int targetOffsetPxX = 0;
int targetOffsetPxY = 0;
int isHoldingSniper = 0;
int maxSpeedValue = 100;

bool visionControlActive = false;

float visionTargetX = 0.0;
float visionTargetY = 0.0;

float pxToCmX = 0.0021167; // to be calibrated based on eDPI (current 1200)
float pxToCmY = 0.0021167; // ... = 1px * 2.54 / eDPI

float kpVision = 55.0;
float kiVision = 0.0;  // Start with PD for moving targets. Add I only for slow static bias.
float kdVision = 6.0;

float prevVisionErrorX = 0.0;
float prevVisionErrorY = 0.0;

float integralErrorX = 0.0; // Accumulated integral error X
float integralErrorY = 0.0; // Accumulated integral error Y
const float maxIntegral = 50.0; // Anti-windup limit for integral term

unsigned long lastVisionPidMicros = 0;

float filteredOffsetX = 0.0;
float filteredOffsetY = 0.0;
const float VISION_FILTER_ALPHA = 0.70; // higher = less lag; lower = smoother

int visionDeadzonePxX = 5;
int visionDeadzonePxY = 5;

const float VISION_TARGET_TOLERANCE_CM = 0.01;

// Predictive tracking and speed-shaping settings.
// lookahead compensates camera/inference/serial/mechanical latency.
float visionLookaheadSec = 0.000;       // stable default: no prediction; tune up slowly
float kvVisionPx = 0.00;                // stable default: no velocity feed-forward; tune up slowly
float filteredTargetVelPxX = 0.0;
float filteredTargetVelPxY = 0.0;
const float TARGET_VEL_FILTER_ALPHA = 0.35;
float prevRotatedOffsetX = 0.0;
float prevRotatedOffsetY = 0.0;
bool hasPrevRotatedOffset = false;

const float MAX_DERIVATIVE_CM_S = 5.0;  // derivative clamp in cm/s

// Runtime-tunable tracking parameters. These can be changed from the PC GUI
// with: TUNE,<outputDeadband>,<minTrackingSpeedPercent>,<visionAccelLimitPercent>
float outputDeadband = 0.9;             // larger deadband improves stability
int minTrackingSpeedPercent = 3;        // minimum speed while tracking
int visionAccelLimitPercent = 10;       // max speed-percent change per control update
int currentVisionSpeedPercent = 0;

unsigned long centeredSinceMs = 0;
const unsigned long CENTER_STABLE_STOP_MS = 80;


// ============================================================================
// Vision-centered event tracking.
// ============================================================================

bool wasVisionCentered = false;
unsigned long lastVisionCenteredEventMs = 0;
const unsigned long VISION_CENTERED_COOLDOWN_MS = 250;

// ============================================================================
// Fire control settings.
// ============================================================================

// Rifle settings
const unsigned long RIFLE_HOLD_MS = 70;
const unsigned long RIFLE_GAP_MS = 250;

// Sniper settings
const unsigned long SNIPER_SCOPE_DELAY_MS = 35; // Quickscope delay
const unsigned long SNIPER_HOLD_MS = 50;        // Click duration
const unsigned long SNIPER_COOLDOWN_MS = 1600;  // Strict lockout to ignore dead bodies

bool fireRequestActive = false;
bool manualScopeRequestActive = false;

// State trackers
bool fireOutputActive = false;
bool scopeOutputActive = false;
unsigned long fireSequenceStartMs = 0;
unsigned long lastFireEndMs = 0;

// ============================================================================
// Forward declarations of functions defined later in the code.
// ============================================================================

bool checkEmergencyStop();

// ============================================================================
// Motor control helpers.
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
// Debounce helper for limit switches.
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
// Position calculation from encoders.
// ============================================================================

void updateEncoderPosition() {
  long e1Count = encoder1.getCount();
  long e2Count = encoder2.getCount();

  float ticksX = (e1Count + e2Count) / 2.0;
  float ticksY = (e1Count - e2Count) / 2.0;

  currentPosX = (SIGN_X * ticksX / stepsPerCM) + 1.0;
  currentPosY = (SIGN_Y * ticksY / stepsPerCM) + 1.0;
}

void updateTraveledDistance() {
  float dx = currentPosX - lastPosX;
  float dy = currentPosY - lastPosY;
  float distance = sqrt((dx * dx) + (dy * dy));

  totalDistanceCm += distance;

  lastPosX = currentPosX;
  lastPosY = currentPosY;
}

// ============================================================================
// Software workspace limit check.
// ============================================================================

bool isOutsideWorkspace() {
  if (currentPosX <= LIMIT_MIN_X + LIMIT_MARGIN_CM) return true;
  if (currentPosX >= LIMIT_MAX_X - LIMIT_MARGIN_CM) return true;
  if (currentPosY <= LIMIT_MIN_Y + LIMIT_MARGIN_CM) return true;
  if (currentPosY >= LIMIT_MAX_Y - LIMIT_MARGIN_CM) return true;

  return false;
}

// ============================================================================
// Debug output.
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
// Auto-recovery: lift Z, center XY, and restore Z from half path.
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
// Auto-recovery: lift Z, center XY, then drop Z sequentially.
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
  Serial.println("Mode: Full Z lift -> XY center + Z drop from half path");
  Serial.println("==================================================");
  Serial.println();

  stopAllMotors();
  delay(30);

  // ============================================================
  // 1. First, fully raise the mouse, as before.
  // ============================================================

  zLift();

  stopAllMotors();
  delay(10);

  updateEncoderPosition();


  const float targetX = LIMIT_MAX_X / 2.0;
  const float targetY = LIMIT_MAX_Y / 2.0;

  const float startX = currentPosX;
  const float startY = currentPosY;

  float startDistance = distanceToPoint(startX, startY, targetX, targetY);

  if (startDistance < 0.01) {
    startDistance = 0.01;
  }

  const float DROP_START_FRACTION = 0.50;

  const unsigned long XY_PULSE_INTERVAL_US = 200;
  const unsigned long Z_PULSE_INTERVAL_US = 100;

  bool xyFinished = false;
  bool zDropStarted = false;
  bool zFinished = false;

  long zDropStepsDone = 0;

  unsigned long recoveryStartMs = millis();
  unsigned long lastXYPulseUs = micros();
  unsigned long lastZPulseUs = micros();

  while (true) {
    if (checkEmergencyStop()) {
      stopAllMotors();
      isAutoRecovering = false;
      return;
    }

    if (millis() - recoveryStartMs > MAX_RECOVERY_TIME_MS) {
      stopAllMotors();

      Serial.println("AUTO RECOVERY ABORTED: timeout.");
      Serial.println("==================================================");
      Serial.println();

      isAutoRecovering = false;
      return;
    }

    updateEncoderPosition();

    float remainingDistance = distanceToPoint(
      currentPosX,
      currentPosY,
      targetX,
      targetY
    );

    float progress = 1.0 - (remainingDistance / startDistance);

    if (progress < 0.0) progress = 0.0;
    if (progress > 1.0) progress = 1.0;


    bool moveU = false;
    bool moveD = false;
    bool moveL = false;
    bool moveR = false;

    if (currentPosX < targetX - CENTER_TOLERANCE_CM) {
      moveL = true;
    } else if (currentPosX > targetX + CENTER_TOLERANCE_CM) {
      moveR = true;
    }

    if (currentPosY < targetY - CENTER_TOLERANCE_CM) {
      moveD = true;
    } else if (currentPosY > targetY + CENTER_TOLERANCE_CM) {
      moveU = true;
    }

    xyFinished = !moveU && !moveD && !moveL && !moveR;

    unsigned long nowUs = micros();

    if (!xyFinished) {
      if (nowUs - lastXYPulseUs >= XY_PULSE_INTERVAL_US) {
        setXYDirectionToCenter(moveU, moveD, moveL, moveR);
        stepXYRecovery();

        lastXYPulseUs = micros();
      }
    } else {
      motor1Running = false;
      motor2Running = false;

      digitalWrite(PUL1_PIN, LOW);
      digitalWrite(PUL2_PIN, LOW);
    }

    if (!zDropStarted && progress >= DROP_START_FRACTION) {
      zDropStarted = true;

      digitalWrite(DIRZ_PIN, HIGH); // Direction: lower Z

      Serial.print("AUTO RECOVERY: XY progress = ");
      Serial.print(progress * 100.0, 1);
      Serial.println("%. Starting Z drop.");
    }

    if (zDropStarted && !zFinished) {
      nowUs = micros();

      if (nowUs - lastZPulseUs >= Z_PULSE_INTERVAL_US) {
        stepZRecovery(false);
        zDropStepsDone++;

        lastZPulseUs = micros();

        if (zDropStepsDone >= stepsForZDrop) {
          currentZSteps = -stepsForZDrop;
          isZUp = false;
          zFinished = true;

          digitalWrite(PULZ_PIN, LOW);

          Serial.println("AUTO RECOVERY: Z is DOWN.");
        }
      }
    }

    if (xyFinished && zFinished) {
      break;
    }
  }

  stopAllMotors();

  Serial.println();
  Serial.println("==================================================");
  Serial.println("AUTO RECOVERY END");
  Serial.println("XY centered and Z restored.");
  Serial.println("==================================================");
  Serial.println();

  isAutoRecovering = false;
}
// ============================================================================
// Continuous software workspace limit monitor.
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
// Non-blocking debounce read function.
// State struct and variables are declared near the top of the file to avoid
// Arduino auto-prototype issues with custom types.
// ============================================================================

bool readDebouncedPressed(int pin, DebouncedInputState &state, unsigned long debounceTimeMs) {
  bool rawPressed = (digitalRead(pin) == LOW);
  unsigned long nowMs = millis();

  if (rawPressed != state.lastRawPressed) {
    state.lastRawPressed = rawPressed;
    state.lastChangeMs = nowMs;
  }

  if (nowMs - state.lastChangeMs >= debounceTimeMs) {
    state.stablePressed = rawPressed;
  }

  return state.stablePressed;
}

// ============================================================================
// Emergency stop helper.
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
// Z-axis control functions.
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
// Centering function.
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
// Homing sequence.
// ============================================================================

void performHoming() {
  Serial.println("Homing start...");

  stopAllMotors();

  int backoffSteps = (int)stepsPerCM;
  int debounceLimitMs = 50;

  // Y-axis homing.

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

  // X-axis homing.

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

  // Reset position.

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
// Setup.
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

void applyVisionTrackingControl() {
  updateEncoderPosition();

  // No detected target: stop motion and reset only the tracking state that would
  // otherwise create stale prediction when the target appears again.
  if (targetDetected != 1) {
    stopAllMotors();
    isManualJogging = false;
    currentVisionSpeedPercent = 0;
    lastVisionPidMicros = 0;
    hasPrevRotatedOffset = false;
    centeredSinceMs = 0;
    return;
  }

  unsigned long nowMicros = micros();
  unsigned long nowMs = millis();
  float dt = 0.001;

  if (lastVisionPidMicros > 0) {
    dt = (nowMicros - lastVisionPidMicros) / 1000000.0;
    if (dt <= 0.0001) dt = 0.0001;
    if (dt > 0.1000) dt = 0.1000; // avoid a huge derivative after a pause
  }

  // Filter pixel offset. This should be light; heavy filtering adds latency.
  filteredOffsetX = filteredOffsetX + VISION_FILTER_ALPHA * ((float)targetOffsetPxX - filteredOffsetX);
  filteredOffsetY = filteredOffsetY + VISION_FILTER_ALPHA * ((float)targetOffsetPxY - filteredOffsetY);

  // Skew angles are already inverted in Python to counter the coordinate system mismatch
  float rotatedOffsetX = (filteredOffsetX * cos(skewAngleX)) - (filteredOffsetY * sin(skewAngleY));
  float rotatedOffsetY = (filteredOffsetX * sin(skewAngleX)) + (filteredOffsetY * cos(skewAngleY));

  // Estimate target motion in screen pixels/s and filter that velocity.
  float rawTargetVelPxX = 0.0;
  float rawTargetVelPxY = 0.0;

  if (hasPrevRotatedOffset) {
    rawTargetVelPxX = (rotatedOffsetX - prevRotatedOffsetX) / dt;
    rawTargetVelPxY = (rotatedOffsetY - prevRotatedOffsetY) / dt;
  } else {
    hasPrevRotatedOffset = true;
  }

  prevRotatedOffsetX = rotatedOffsetX;
  prevRotatedOffsetY = rotatedOffsetY;

  filteredTargetVelPxX = filteredTargetVelPxX + TARGET_VEL_FILTER_ALPHA * (rawTargetVelPxX - filteredTargetVelPxX);
  filteredTargetVelPxY = filteredTargetVelPxY + TARGET_VEL_FILTER_ALPHA * (rawTargetVelPxY - filteredTargetVelPxY);

  bool isVisionCenteredNow =
    abs(targetOffsetPxX) <= visionDeadzonePxX &&
    abs(targetOffsetPxY) <= visionDeadzonePxY;

  bool targetMoving =
    abs(filteredTargetVelPxX) > 25.0 ||
    abs(filteredTargetVelPxY) > 25.0;

  // For moving targets, do not immediately stop and reset inside the deadzone.
  // Stop only when it has stayed centered and almost static for a short time.
  if (isVisionCenteredNow && !targetMoving) {
    if (centeredSinceMs == 0) centeredSinceMs = nowMs;

    if (nowMs - centeredSinceMs >= CENTER_STABLE_STOP_MS) {
      stopAllMotors();
      isManualJogging = false;
      currentVisionSpeedPercent = 0;
      prevVisionErrorX = 0.0;
      prevVisionErrorY = 0.0;
      integralErrorX = 0.0;
      integralErrorY = 0.0;

      if (!wasVisionCentered &&
          nowMs - lastVisionCenteredEventMs >= VISION_CENTERED_COOLDOWN_MS) {
        Serial.println("VISION CENTERED EVENT");
        lastVisionCenteredEventMs = nowMs;
      }
      wasVisionCentered = true;
      lastVisionPidMicros = nowMicros;
      return;
    }
  } else {
    centeredSinceMs = 0;
  }

  wasVisionCentered = false;

  // Predict where the detected point will be after measured system latency.
  float predictedOffsetX = rotatedOffsetX + (filteredTargetVelPxX * visionLookaheadSec);
  float predictedOffsetY = rotatedOffsetY + (filteredTargetVelPxY * visionLookaheadSec);

  visionTargetX = currentPosX - (predictedOffsetX * pxToCmX);
  visionTargetY = currentPosY - (predictedOffsetY * pxToCmY);

  if (visionTargetX < LIMIT_MIN_X + LIMIT_MARGIN_CM) visionTargetX = LIMIT_MIN_X + LIMIT_MARGIN_CM;
  if (visionTargetX > LIMIT_MAX_X - LIMIT_MARGIN_CM) visionTargetX = LIMIT_MAX_X - LIMIT_MARGIN_CM;

  if (visionTargetY < LIMIT_MIN_Y + LIMIT_MARGIN_CM) visionTargetY = LIMIT_MIN_Y + LIMIT_MARGIN_CM;
  if (visionTargetY > LIMIT_MAX_Y - LIMIT_MARGIN_CM) visionTargetY = LIMIT_MAX_Y - LIMIT_MARGIN_CM;

  float errorX = visionTargetX - currentPosX;
  float errorY = visionTargetY - currentPosY;

  // Derivative of position error in cm/s.
  float derivativeX = (errorX - prevVisionErrorX) / dt;
  float derivativeY = (errorY - prevVisionErrorY) / dt;

  if (derivativeX > MAX_DERIVATIVE_CM_S) derivativeX = MAX_DERIVATIVE_CM_S;
  if (derivativeX < -MAX_DERIVATIVE_CM_S) derivativeX = -MAX_DERIVATIVE_CM_S;

  if (derivativeY > MAX_DERIVATIVE_CM_S) derivativeY = MAX_DERIVATIVE_CM_S;
  if (derivativeY < -MAX_DERIVATIVE_CM_S) derivativeY = -MAX_DERIVATIVE_CM_S;

  // Integrator is optional; keep Ki at 0 for fast moving targets unless you need
  // to remove slow static bias. Clamp remains here for safe tuning.
  integralErrorX += errorX * dt;
  integralErrorY += errorY * dt;

  if (integralErrorX > maxIntegral) integralErrorX = maxIntegral;
  if (integralErrorX < -maxIntegral) integralErrorX = -maxIntegral;

  if (integralErrorY > maxIntegral) integralErrorY = maxIntegral;
  if (integralErrorY < -maxIntegral) integralErrorY = -maxIntegral;

  // Feed-forward from measured target velocity. This is what keeps the robot from
  // slowing too much while it is following a moving point.
  float feedForwardX = -filteredTargetVelPxX * pxToCmX * kvVisionPx;
  float feedForwardY = -filteredTargetVelPxY * pxToCmY * kvVisionPx;

  float outputX = (kpVision * errorX) + (kiVision * integralErrorX) + (kdVision * derivativeX) + feedForwardX;
  float outputY = (kpVision * errorY) + (kiVision * integralErrorY) + (kdVision * derivativeY) + feedForwardY;

  prevVisionErrorX = errorX;
  prevVisionErrorY = errorY;
  lastVisionPidMicros = nowMicros;

  // Map output to movement direction.
  bool mLeft = outputX > outputDeadband;
  bool mRight = outputX < -outputDeadband;
  bool mDown = outputY > outputDeadband;
  bool mUp = outputY < -outputDeadband;

  blockMoveIfWouldExceedLimit(mUp, mDown, mLeft, mRight);

  // Stop if movement is blocked by a virtual wall.
  if ((!mUp && outputY < -outputDeadband) ||
      (!mDown && outputY > outputDeadband) ||
      (!mLeft && outputX > outputDeadband) ||
      (!mRight && outputX < -outputDeadband)) {

      isManualJogging = false;
      currentVisionSpeedPercent = 0;
      stopAllMotors();
      return;
  }

  // CoreXY kinematic transformation.
  float vM1 = -outputX - outputY;
  float vM2 = -outputX + outputY;

  // Direction vector normalization. PID magnitude is still used for speed below.
  float maxV = max(abs(vM1), abs(vM2));
  if (maxV > 0.0) {
      vM1 /= maxV;
      vM2 /= maxV;
  }

  jogVM1 = abs(vM1);
  jogVM2 = abs(vM2);
  jogDirM1 = (vM1 >= 0) ? HIGH : LOW;
  jogDirM2 = (vM2 >= 0) ? HIGH : LOW;

  isMovingRight = mRight;
  isMovingLeft  = mLeft;
  isMovingDown  = mDown;
  isMovingUp    = mUp;

  float magnitude = sqrt((outputX * outputX) + (outputY * outputY));
  int targetSpeedPercent = (int)magnitude;

  if (targetSpeedPercent > maxSpeedValue) targetSpeedPercent = maxSpeedValue;

  if (mUp || mDown || mLeft || mRight) {
    if (targetSpeedPercent < minTrackingSpeedPercent) {
      targetSpeedPercent = minTrackingSpeedPercent;
    }
  } else {
    targetSpeedPercent = 0;
  }

  if (maxSpeedValue <= 0 || targetSpeedPercent <= 0) {
    isManualJogging = false;
    currentVisionSpeedPercent = 0;
    stopAllMotors();
    return;
  }

  // Acceleration limiting: avoid abrupt frequency jumps and lost steps.
  if (targetSpeedPercent > currentVisionSpeedPercent + visionAccelLimitPercent) {
    currentVisionSpeedPercent += visionAccelLimitPercent;
  } else if (targetSpeedPercent < currentVisionSpeedPercent - visionAccelLimitPercent) {
    currentVisionSpeedPercent -= visionAccelLimitPercent;
  } else {
    currentVisionSpeedPercent = targetSpeedPercent;
  }

  isManualJogging = true;
  setDelayFromSpeedPercent(currentVisionSpeedPercent);
}


void updateFireControl() {
  unsigned long nowMs = millis();

  // Emergency fail-safe
  if (pressedKeys.indexOf('p') >= 0) {
    fireRequestActive = false;
    fireOutputActive = false;
    scopeOutputActive = false;

    digitalWrite(RELAY1_PIN, LOW);
    digitalWrite(RELAY2_PIN, LOW);
    return;
  }

    // --------------------------------------------------------
  // SNIPER LOGIC
  // --------------------------------------------------------
  if (isHoldingSniper == 1 || scopeOutputActive || (fireOutputActive && isHoldingSniper == 1)) {
    // 1. Cooldown block - strictly ignores YOLO to prevent spamming dead bodies
    if (lastFireEndMs != 0 && (nowMs - lastFireEndMs < SNIPER_COOLDOWN_MS)) {
      digitalWrite(RELAY1_PIN, LOW);
      digitalWrite(RELAY2_PIN, manualScopeRequestActive ? HIGH : LOW);
      fireOutputActive = false;
      scopeOutputActive = false;
      return;
    }

    // 2. Phase: Holding the shot (LMB)
    if (fireOutputActive) {
      if (nowMs - fireSequenceStartMs >= SNIPER_HOLD_MS) {
        digitalWrite(RELAY1_PIN, LOW);
        fireOutputActive = false;
        lastFireEndMs = nowMs;

        Serial.println("SNIPER: FIRE END");
      }
      return;
    }

    // 3. Phase: Quickscoping - wait for scope delay, then shoot
    if (scopeOutputActive) {
      if (nowMs - fireSequenceStartMs >= SNIPER_SCOPE_DELAY_MS) {
        digitalWrite(RELAY2_PIN, LOW);  // Release first RMB click
        digitalWrite(RELAY1_PIN, HIGH); // Shoot
        fireOutputActive = true;
        scopeOutputActive = false;
        fireSequenceStartMs = nowMs;
        Serial.println("SNIPER: FIRE START");
      }
      return;
    }

    // 4. Idle - waiting for target or manual scope
    if (!fireRequestActive) {
      digitalWrite(RELAY1_PIN, LOW);
      digitalWrite(RELAY2_PIN, manualScopeRequestActive ? HIGH : LOW);
      return;
    }

    // 5. Target found - first RMB click to scope
    digitalWrite(RELAY2_PIN, HIGH);
    scopeOutputActive = true;
    fireSequenceStartMs = nowMs;
    Serial.println("SNIPER: SCOPE START");
    return;
  }

  // --------------------------------------------------------
  // RIFLE LOGIC (Standard firing)
  // --------------------------------------------------------

  digitalWrite(RELAY2_PIN, manualScopeRequestActive ? HIGH : LOW);

  if (fireOutputActive) {
    if (nowMs - fireSequenceStartMs >= RIFLE_HOLD_MS) {
      digitalWrite(RELAY1_PIN, LOW);
      fireOutputActive = false;
      lastFireEndMs = nowMs;
    }
    return;
  }

  if (!fireRequestActive) {
    digitalWrite(RELAY1_PIN, LOW);
    return;
  }

  if (lastFireEndMs == 0 || (nowMs - lastFireEndMs >= RIFLE_GAP_MS)) {
    digitalWrite(RELAY1_PIN, HIGH);
    fireOutputActive = true;
    fireSequenceStartMs = nowMs;
  }

  // Track LMB/RMB clicks (rising edge detection)
  if (fireOutputActive && !lastFireOutputState) {
    totalLmbClicks++;
  }
  if ((scopeOutputActive || manualScopeRequestActive) && !lastScopeOutputState) {
    totalRmbClicks++;
  }

  lastFireOutputState = fireOutputActive;
  lastScopeOutputState = (scopeOutputActive || manualScopeRequestActive);
}

// ============================================================================
// Main loop.
// ============================================================================

void loop() {

  // Hardware encoder position calculation.

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

  // Continuous software workspace limit monitor.

  applyContinuousWorkspaceLimit();

  // The Z limit is intentionally not checked with debounce in the main loop.
  // This allows XY motion to continue normally when the Z endstop is physically pressed.
  // The Z limit is checked only while Z is moving up.

  // Limit switch safety and bounce-back.

  bool limitX = readDebouncedPressed(LIMIT_X_PIN, limitXDebounce, 20);
  bool limitY = readDebouncedPressed(LIMIT_Y_PIN, limitYDebounce, 20);
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

  // Servo auto-detach.

  if (isServoTimerActive && (millis() - servoMoveStartTime >= 2000)) {
    mainServo.detach();
    isServoTimerActive = false;
  }

  // Serial command receiving.
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

  // Command parsing and execution.

  if (isCommandReady) {
    String data = String(serialBuffer);
    data.trim();

    if (data == "ESP32-CHECK") {
      Serial.println("ESP32-READY");
      isCommandReady = false;
      bufferIndex = 0;
    }
    else if (data.substring(0, 12) == "CALIBRATION,") {
      int firstComma = data.indexOf(',', 0);
      int secondComma = data.indexOf(',', firstComma + 1);
      int thirdComma = data.indexOf(',', secondComma + 1);

      if (firstComma > 0 && secondComma > 0 && thirdComma > 0) {
        int calibrated_edpi = data.substring(firstComma + 1, secondComma).toInt();
        skewAngleX = data.substring(secondComma + 1, thirdComma).toFloat();
        skewAngleY = data.substring(thirdComma + 1).toFloat();

        pxToCmX = 1.0 * 2.54 / calibrated_edpi;
        pxToCmY = 1.0 * 2.54 / calibrated_edpi;

        Serial.print("Calibration saved! eDPI: ");
        Serial.print(calibrated_edpi);
        Serial.print(" | SkewX: ");
        Serial.print(skewAngleX, 4);
        Serial.print(" | SkewY: ");
        Serial.println(skewAngleY, 4);
      }
    }
    else if (data.substring(0, 4) == "PID,") {
      int firstComma = data.indexOf(',', 0);
      int secondComma = data.indexOf(',', firstComma + 1);
      int thirdComma = data.indexOf(',', secondComma + 1);

      if (firstComma > 0 && secondComma > 0 && thirdComma > 0) {
        kpVision = data.substring(firstComma + 1, secondComma).toFloat();
        kiVision = data.substring(secondComma + 1, thirdComma).toFloat();
        kdVision = data.substring(thirdComma + 1).toFloat();

        Serial.print("PID updated: Kp=");
        Serial.print(kpVision);
        Serial.print(" Ki=");
        Serial.print(kiVision);
        Serial.print(" Kd=");
        Serial.println(kdVision);
      }
    }
    else if (data.substring(0, 6) == "TRACK,") {
      int firstComma = data.indexOf(',', 0);
      int secondComma = data.indexOf(',', firstComma + 1);

      if (firstComma > 0 && secondComma > 0) {
        visionLookaheadSec = data.substring(firstComma + 1, secondComma).toFloat();
        kvVisionPx = data.substring(secondComma + 1).toFloat();

        if (visionLookaheadSec < 0.0) visionLookaheadSec = 0.0;
        if (visionLookaheadSec > 0.150) visionLookaheadSec = 0.150;
        if (kvVisionPx < 0.0) kvVisionPx = 0.0;
        if (kvVisionPx > 3.0) kvVisionPx = 3.0;

        Serial.print("Tracking updated: lookaheadSec=");
        Serial.print(visionLookaheadSec, 4);
        Serial.print(" KvPx=");
        Serial.println(kvVisionPx, 4);
      }
    }
    else if (data.substring(0, 5) == "TUNE,") {
      int firstComma = data.indexOf(',', 0);
      int secondComma = data.indexOf(',', firstComma + 1);
      int thirdComma = data.indexOf(',', secondComma + 1);

      if (firstComma > 0 && secondComma > 0 && thirdComma > 0) {
        outputDeadband = data.substring(firstComma + 1, secondComma).toFloat();
        minTrackingSpeedPercent = data.substring(secondComma + 1, thirdComma).toInt();
        visionAccelLimitPercent = data.substring(thirdComma + 1).toInt();

        // Safety clamps for stable runtime tuning.
        if (outputDeadband < 0.0) outputDeadband = 0.0;
        if (outputDeadband > 10.0) outputDeadband = 10.0;

        if (minTrackingSpeedPercent < 0) minTrackingSpeedPercent = 0;
        if (minTrackingSpeedPercent > 100) minTrackingSpeedPercent = 100;

        if (visionAccelLimitPercent < 1) visionAccelLimitPercent = 1;
        if (visionAccelLimitPercent > 100) visionAccelLimitPercent = 100;

        Serial.print("Tune updated: deadband=");
        Serial.print(outputDeadband, 3);
        Serial.print(" minSpeed=");
        Serial.print(minTrackingSpeedPercent);
        Serial.print(" accelLimit=");
        Serial.println(visionAccelLimitPercent);
      }
    }
    else if (data.length() > 0) {
      int commaIndexes[7] = {0, 0, 0, 0, 0, 0, 0};
      int commaIndex = 0;

      for (int index = 0; index < data.length(); index++) {
        if (data[index] == ',') {
          if (commaIndex < 7) {
            commaIndexes[commaIndex] = index;
            commaIndex++;
          }
        }
      }

      if (commaIndex == 7) {
        targetOffsetPxX = data.substring(0, commaIndexes[0]).toInt();
        targetOffsetPxY = data.substring(commaIndexes[0] + 1, commaIndexes[1]).toInt();
        isHoldingSniper = data.substring(commaIndexes[1] + 1, commaIndexes[2]).toInt();
        pressedKeys = data.substring(commaIndexes[2] + 1, commaIndexes[3]);
        maxSpeedValue = data.substring(commaIndexes[3] + 1, commaIndexes[4]).toInt();
        targetDetected = data.substring(commaIndexes[4] + 1, commaIndexes[5]).toInt();

        visionDeadzonePxX = data.substring(commaIndexes[5] + 1, commaIndexes[6]).toInt();
        visionDeadzonePxY = data.substring(commaIndexes[6] + 1).toInt();

        if (maxSpeedValue < 0) maxSpeedValue = 0;
        if (maxSpeedValue > 100) maxSpeedValue = 100;

        // Safeguards for deadzone received from YOLO.
        if (visionDeadzonePxX < 7) visionDeadzonePxX = 7;
        if (visionDeadzonePxY < 7) visionDeadzonePxY = 7;

        if (visionDeadzonePxX > 200) visionDeadzonePxX = 200;
        if (visionDeadzonePxY > 200) visionDeadzonePxY = 200;

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
          bool rawUp = (pressedKeys.indexOf('i') >= 0);
          bool rawDown = (pressedKeys.indexOf('k') >= 0);
          bool rawLeft = (pressedKeys.indexOf('j') >= 0);
          bool rawRight = (pressedKeys.indexOf('l') >= 0);

          if (!rawUp && !rawDown && !rawLeft && !rawRight) {
            visionControlActive = true;
            isManualJogging = false;
            applyVisionTrackingControl();

          } else {
            visionControlActive = false;
            isManualJogging = true;
            updateEncoderPosition();

            // 1. Define base vector (from keys)
            float manX = 0.0;
            float manY = 0.0;
            if (rawLeft) manX = -1.0;
            if (rawRight) manX = 1.0;
            if (rawUp) manY = -1.0;
            if (rawDown) manY = 1.0;

            // 2. Rotate vector by the calibrated separate axis skew angles
            float rotX = (manX * cos(skewAngleX)) - (manY * sin(skewAngleY));
            float rotY = (manX * sin(skewAngleX)) + (manY * cos(skewAngleY));

            // 3. CoreXY kinematic transformation
            float vM1 = rotX - rotY;
            float vM2 = rotX + rotY;

            // Normalize speed so the main motor runs at 100% of target maxSpeedValue
            float maxV = max(abs(vM1), abs(vM2));
            if (maxV > 0.0) {
                vM1 /= maxV;
                vM2 /= maxV;
            }

            jogVM1 = abs(vM1);
            jogVM2 = abs(vM2);
            jogDirM1 = (vM1 >= 0) ? HIGH : LOW;
            jogDirM2 = (vM2 >= 0) ? HIGH : LOW;

            isMovingRight = (rotX > 0);
            isMovingLeft  = (rotX < 0);
            isMovingDown  = (rotY > 0);
            isMovingUp    = (rotY < 0);

            bool mUp = isMovingUp, mDown = isMovingDown, mLeft = isMovingLeft, mRight = isMovingRight;
            blockMoveIfWouldExceedLimit(mUp, mDown, mLeft, mRight);

            // If movement hits a virtual wall - stop manual jogging
            if ((!mUp && isMovingUp) || (!mDown && isMovingDown) || (!mLeft && isMovingLeft) || (!mRight && isMovingRight)) {
                isManualJogging = false;
                stopAllMotors();
            } else {
                if (maxSpeedValue <= 0) {
                    isManualJogging = false;
                    stopAllMotors();
                } else {
                    setDelayFromSpeedPercent(maxSpeedValue);
                }
            }
          }

          // Z axis.

          if (pressedKeys.indexOf('z') >= 0) {
            moveZ(HIGH);
          }

          else if (pressedKeys.indexOf('x') >= 0) {
            if (digitalRead(LIMIT_Z_PIN) == LOW) {
              motorZRunning = false;
              digitalWrite(PULZ_PIN, LOW);
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

          // Servo.

          if (pressedKeys.indexOf('v') >= 0 && (millis() - lastServoToggle > 500)) {
            servoState = !servoState;

            mainServo.attach(SERVO_PIN);
            mainServo.write(servoState ? angleDown : angleUp);

            servoMoveStartTime = millis();
            isServoTimerActive = true;
            lastServoToggle = millis();
          }

          // Relays.

          bool manualFire = (pressedKeys.indexOf('1') >= 0);
          bool autoFire = false;

          if (visionControlActive && targetDetected == 1 &&
              abs(targetOffsetPxX) <= visionDeadzonePxX  &&
              abs(targetOffsetPxY) <= visionDeadzonePxY) {
            autoFire = true;
          }

          fireRequestActive = (manualFire || autoFire);
          manualScopeRequestActive = (pressedKeys.indexOf('2') >= 0);
        }
      }
    }

    bufferIndex = 0;
    isCommandReady = false;
  }

  updateTraveledDistance();
  if (millis() - lastStatsSentMs > STATS_SEND_INTERVAL_MS) {
    Serial.print("STATS,");
    Serial.print(totalLmbClicks);
    Serial.print(",");
    Serial.print(totalRmbClicks);
    Serial.print(",");
    Serial.println(totalDistanceCm, 2);
    lastStatsSentMs = millis();
  }

  updateFireControl();
  // Step generation.
  if (isManualJogging) {
    manualAccumM1 += jogVM1;
    manualAccumM2 += jogVM2;

    motor1Running = false;
    motor2Running = false;

    // If accumulator reaches 1.0 threshold, release a physical step for the motor
    if (manualAccumM1 >= 1.0) {
      motor1Running = true;
      manualAccumM1 -= 1.0;
      digitalWrite(DIR1_PIN, jogDirM1);
    }
    if (manualAccumM2 >= 1.0) {
      motor2Running = true;
      manualAccumM2 -= 1.0;
      digitalWrite(DIR2_PIN, jogDirM2);
    }
  }

  if (!motor1Running && !motor2Running && !motorZRunning) {
    delay(1);
    return;
  }

  if (motorZRunning && digitalRead(DIRZ_PIN) == LOW && digitalRead(LIMIT_Z_PIN) == LOW) {
    motorZRunning = false;
    digitalWrite(PULZ_PIN, LOW);
    currentZSteps = 0;
    isZUp = true;
    Serial.println("Z LIMIT: Z motor stopped. XY still allowed.");
  }

  int currentDelay = (motorZRunning) ? delayZ : delayCoreXY;

  if (!motorZRunning && (motor1Running != motor2Running) && !isManualJogging) {
    currentDelay = (int)(currentDelay * 0.707);
  }

  const int MIN_SAFE_DELAY = 50; //120

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