/*
 * CSAimBot Motor Control Firmware
 * ESP32-based controller for CoreXY robotic platform with Z-axis servo
 * 
 * Handles stepper motor control, limit switches, hardware encoders,
 * servo actuation, relay control, and serial communication protocol.
 */

#include <ESP32Servo.h>
#include <ESP32Encoder.h>

// ============================================================================
// PIN DEFINITIONS
// ============================================================================

// Stepper motor driver pins
#define PUL1_PIN 23
#define DIR1_PIN 22
#define PUL2_PIN 21
#define DIR2_PIN 19
#define PULZ_PIN 12
#define DIRZ_PIN 17

// Servo and relay control pins
#define SERVO_PIN 25
#define RELAY1_PIN 26
#define RELAY2_PIN 27

// Hardware encoder input pins
#define ENCO1_PHASE_A 18
#define ENCO1_PHASE_B 5
#define ENCO2_PHASE_A 32
#define ENCO2_PHASE_B 33

// Limit switch inputs (active LOW)
#define LIMIT_X_PIN 4
#define LIMIT_Y_PIN 13
#define LIMIT_Z_PIN 14

// ============================================================================
// CONFIGURATION & STATE VARIABLES
// ============================================================================

// Motor timing configuration
int delayCoreXY = 800;
const int delayZ = 300;
int homingDelay = 1500;

// Motor running states
bool motor1Running = false;
bool motor2Running = false;
bool motorZRunning = false;

// Hardware encoder objects
ESP32Encoder encoder1;
ESP32Encoder encoder2;

// Physical position tracking (centimeters)
float currentPosX = 0.0;
float currentPosY = 0.0;
unsigned long lastEncoderPrint = 0;

// Encoder calibration factor
// Defines how many encoder ticks correspond to 1 cm of travel
float stepsPerCM = 296.30;

// Servo control variables
Servo mainServo;
bool servoState = false;
unsigned long lastServoToggle = 0;

// Safe servo positions
const int angleUp = 0;
const int angleDown = 180;

// Servo auto-detach timer
unsigned long servoMoveStartTime = 0;
bool isServoTimerActive = false;

// Software movement boundaries (workspace limits in cm)
const float LIMIT_MIN_X = -28.50;
const float LIMIT_MAX_X = 0.00;
const float LIMIT_MIN_Y = 0.00;
const float LIMIT_MAX_Y = 24.50;

// Serial protocol variables
int posX = 0;
int posY = 0;
String pressedKeys = "";

// ============================================================================
// MOTOR CONTROL FUNCTIONS
// ============================================================================

/**
 * @brief Immediately stops all motors and clears pulse outputs
 */
void stopAllMotors() {
  motor1Running = false;
  motor2Running = false;
  motorZRunning = false;

  digitalWrite(PUL1_PIN, LOW);
  digitalWrite(PUL2_PIN, LOW);
  digitalWrite(PULZ_PIN, LOW);
}

/**
 * @brief Configures CoreXY motor directions and enables movement
 * 
 * @param run1 Enable state for motor 1
 * @param dir1 Direction for motor 1
 * @param run2 Enable state for motor 2
 * @param dir2 Direction for motor 2
 */
void setMotorsXY(bool run1, int dir1, bool run2, int dir2) {
  motorZRunning = false;

  if (run1) digitalWrite(DIR1_PIN, dir1);
  if (run2) digitalWrite(DIR2_PIN, dir2);

  delayMicroseconds(5);

  motor1Running = run1;
  motor2Running = run2;
}

/**
 * @brief Starts Z-axis movement
 * 
 * @param dirZ Direction of vertical motion
 */
void moveZ(int dirZ) {
  motor1Running = false;
  motor2Running = false;

  digitalWrite(DIRZ_PIN, dirZ);

  delayMicroseconds(5);

  motorZRunning = true;
}

// ============================================================================
// HOMING SEQUENCE
// ============================================================================

/**
 * @brief Homes all machine axes using limit switches
 * 
 * Sequence:
 * 1. Z-axis
 * 2. X-axis
 * 3. Y-axis
 * 
 * Applies backlash compensation after each axis is homed.
 * Hardware encoder counts are reset after homing completion.
 */
void performHoming() {
  Serial.println("Homing start...");

  stopAllMotors();

  // ------------------------------------------------------------------------
  // 1. Z-Axis Homing
  // ------------------------------------------------------------------------

  digitalWrite(DIRZ_PIN, LOW);

  while(digitalRead(LIMIT_Z_PIN) == HIGH) {
    digitalWrite(PULZ_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PULZ_PIN, LOW);
    delayMicroseconds(homingDelay);

    delay(1);
  }

  // Backlash compensation
  digitalWrite(DIRZ_PIN, HIGH);

  for(int i = 0; i < 500; i++) {
    digitalWrite(PULZ_PIN, HIGH);
    delayMicroseconds(homingDelay);

    digitalWrite(PULZ_PIN, LOW);
    delayMicroseconds(homingDelay);

    delay(1);
  }

  // ------------------------------------------------------------------------
  // 2. X-Axis Homing
  // ------------------------------------------------------------------------

  digitalWrite(DIR1_PIN, HIGH);
  digitalWrite(DIR2_PIN, LOW);

  while(digitalRead(LIMIT_X_PIN) == HIGH) {
    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);

    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);

    delayMicroseconds(homingDelay);

    delay(1);
  }

  // Backlash compensation
  digitalWrite(DIR1_PIN, LOW);
  digitalWrite(DIR2_PIN, HIGH);

  for(int i = 0; i < 200; i++) {
    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);

    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);

    delayMicroseconds(homingDelay);

    delay(1);
  }

  // ------------------------------------------------------------------------
  // 3. Y-Axis Homing
  // ------------------------------------------------------------------------

  digitalWrite(DIR1_PIN, HIGH);
  digitalWrite(DIR2_PIN, HIGH);

  while(digitalRead(LIMIT_Y_PIN) == HIGH) {
    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);

    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);

    delayMicroseconds(homingDelay);

    delay(1);
  }

  // Backlash compensation
  digitalWrite(DIR1_PIN, LOW);
  digitalWrite(DIR2_PIN, LOW);

  for(int i = 0; i < 200; i++) {
    digitalWrite(PUL1_PIN, HIGH);
    digitalWrite(PUL2_PIN, HIGH);

    delayMicroseconds(homingDelay);

    digitalWrite(PUL1_PIN, LOW);
    digitalWrite(PUL2_PIN, LOW);

    delayMicroseconds(homingDelay);

    delay(1);
  }

  // Reset logical and encoder positions
  posX = 0;
  posY = 0;

  encoder1.clearCount();
  encoder2.clearCount();

  Serial.println("Homing OK! Encoder positions reset.");
}

// ============================================================================
// SETUP & INITIALIZATION
// ============================================================================

/**
 * @brief Initializes serial communication, GPIO pins,
 * hardware encoders, relays, and servo state.
 */
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(30);

  // Configure motor output pins
  pinMode(PUL1_PIN, OUTPUT);
  pinMode(DIR1_PIN, OUTPUT);

  pinMode(PUL2_PIN, OUTPUT);
  pinMode(DIR2_PIN, OUTPUT);

  pinMode(PULZ_PIN, OUTPUT);
  pinMode(DIRZ_PIN, OUTPUT);

  // Configure relay outputs
  pinMode(RELAY1_PIN, OUTPUT);
  pinMode(RELAY2_PIN, OUTPUT);

  // Configure limit switch inputs
  pinMode(LIMIT_X_PIN, INPUT_PULLUP);
  pinMode(LIMIT_Y_PIN, INPUT_PULLUP);
  pinMode(LIMIT_Z_PIN, INPUT_PULLUP);

  // Initialize outputs to safe state
  stopAllMotors();

  digitalWrite(RELAY1_PIN, LOW);
  digitalWrite(RELAY2_PIN, LOW);

  // ------------------------------------------------------------------------
  // Servo initialization
  // ------------------------------------------------------------------------

  mainServo.attach(SERVO_PIN);
  mainServo.write(angleUp);

  delay(1000);

  // Reduce servo heating/noise by detaching after startup
  mainServo.detach();

  Serial.println("Servo detached after startup.");

  // ------------------------------------------------------------------------
  // Hardware encoder initialization
  // ------------------------------------------------------------------------

  ESP32Encoder::useInternalWeakPullResistors = puType::up;

  encoder1.attachHalfQuad(ENCO1_PHASE_A, ENCO1_PHASE_B);
  encoder2.attachHalfQuad(ENCO2_PHASE_A, ENCO2_PHASE_B);

  encoder1.clearCount();
  encoder2.clearCount();

  Serial.println("System Ready (Hardware PCNT Mode)");
}

// ============================================================================
// MAIN CONTROL LOOP
// ============================================================================

/**
 * @brief Main firmware execution loop
 * 
 * Serial Protocol:
 * "dX,dY,speed,keys\r"
 * 
 * dX, dY  -> target movement offsets
 * speed   -> movement speed (1-100)
 * keys    -> command characters
 * 
 * Controls:
 * i/j/k/l -> XY movement
 * z/x     -> Z-axis movement
 * v       -> servo toggle
 * 1/2     -> relay outputs
 * h       -> homing sequence
 * p       -> emergency stop
 */
void loop() {

  // ------------------------------------------------------------------------
  // LIMIT SWITCH SAFETY MONITORING
  // ------------------------------------------------------------------------

  bool limitX = (digitalRead(LIMIT_X_PIN) == LOW);
  bool limitY = (digitalRead(LIMIT_Y_PIN) == LOW);
  bool limitZ = (digitalRead(LIMIT_Z_PIN) == LOW);

  // Emergency stop if switch triggered during movement
  if ((limitX || limitY || limitZ) &&
      (motor1Running || motor2Running || motorZRunning)) {

      stopAllMotors();
      Serial.println("ALARM_LIMIT");
  }

  // ------------------------------------------------------------------------
  // HARDWARE ENCODER POSITION CALCULATION
  // ------------------------------------------------------------------------

  long e1Count = encoder1.getCount();
  long e2Count = encoder2.getCount();

  // CoreXY kinematics conversion
  float ticksX = (e1Count - e2Count) / 2.0;
  float ticksY = (e1Count + e2Count) / 2.0;

  // Convert encoder ticks into centimeters
  currentPosX = ticksX / stepsPerCM;
  currentPosY = ticksY / stepsPerCM;

  // Periodic position diagnostic output
  if (millis() - lastEncoderPrint > 500) {
      Serial.print("Pozycja X: ");
      Serial.print(currentPosX);

      Serial.print(" cm | Y: ");
      Serial.print(currentPosY);

      Serial.println(" cm");

      lastEncoderPrint = millis();
  }

  // ------------------------------------------------------------------------
  // NON-BLOCKING SERVO AUTO-DETACH TIMER
  // ------------------------------------------------------------------------

  if (isServoTimerActive &&
      (millis() - servoMoveStartTime >= 2000)) {

      mainServo.detach();
      isServoTimerActive = false;
  }

  // ------------------------------------------------------------------------
  // SERIAL COMMAND PROCESSING
  // ------------------------------------------------------------------------

  if (Serial.available() > 0) {

    String data = Serial.readStringUntil('\r');
    data.trim();

    if (data.length() > 0) {

      int commaIndexOne = data.indexOf(',');
      int commaIndexTwo = data.indexOf(',', commaIndexOne + 1);
      int commaIndexThree = data.indexOf(',', commaIndexTwo + 1);

      if (commaIndexOne > 0 &&
          commaIndexTwo > 0 &&
          commaIndexThree > 0) {

        posX = data.substring(0, commaIndexOne).toInt();
        posY = data.substring(commaIndexOne + 1, commaIndexTwo).toInt();

        int speedValue =
          data.substring(commaIndexTwo + 1, commaIndexThree).toInt();

        pressedKeys =
          data.substring(commaIndexThree + 1);

        // Convert speed range 1-100 into pulse delay
        if(speedValue >= 1 && speedValue <= 100) {

          delayCoreXY =
            (int)(1000000.0 /
            (100.0 + ((speedValue - 1.0) / 99.0) * 9900.0));
        }

        // ----------------------------------------------------------------
        // COMMAND EXECUTION
        // ----------------------------------------------------------------

        if (pressedKeys.indexOf('p') >= 0) {

          stopAllMotors();

        } else if (pressedKeys.indexOf('h') >= 0) {

          performHoming();

        } else {

          // --------------------------------------------------------------
          // MANUAL MOVEMENT INPUT
          // --------------------------------------------------------------

          bool moveUp =
            pressedKeys.indexOf('i') >= 0;

          bool moveDown =
            pressedKeys.indexOf('k') >= 0;

          bool moveLeft =
            pressedKeys.indexOf('j') >= 0;

          bool moveRight =
            pressedKeys.indexOf('l') >= 0;

          // --------------------------------------------------------------
          // AUTOMATIC YOLO TRACKING INPUT
          // --------------------------------------------------------------

          if (!moveUp &&
              !moveDown &&
              !moveLeft &&
              !moveRight) {

            int deadzoneX = 15;
            int deadzoneY = 15;

            if (posX > deadzoneX)
              moveRight = true;
            else if (posX < -deadzoneX)
              moveLeft = true;

            if (posY > deadzoneY)
              moveUp = true;
            else if (posY < -deadzoneY)
              moveDown = true;
          }

          // --------------------------------------------------------------
          // SOFTWARE ENDSTOPS
          // Prevent movement outside workspace boundaries
          // --------------------------------------------------------------

          if (moveLeft && currentPosX <= LIMIT_MIN_X)
            moveLeft = false;

          if (moveRight && currentPosX >= LIMIT_MAX_X)
            moveRight = false;

          if (moveDown && currentPosY >= LIMIT_MAX_Y)
            moveDown = false;

          if (moveUp && currentPosY <= LIMIT_MIN_Y)
            moveUp = false;

          // --------------------------------------------------------------
          // COREXY MOTOR MAPPING
          // --------------------------------------------------------------

          if (moveUp && moveLeft)
            setMotorsXY(false, LOW, true, HIGH);

          else if (moveUp && moveRight)
            setMotorsXY(true, HIGH, false, LOW);

          else if (moveDown && moveLeft)
            setMotorsXY(true, LOW, false, LOW);

          else if (moveDown && moveRight)
            setMotorsXY(false, LOW, true, LOW);

          else if (moveUp)
            setMotorsXY(true, HIGH, true, HIGH);

          else if (moveDown)
            setMotorsXY(true, LOW, true, LOW);

          else if (moveLeft)
            setMotorsXY(true, LOW, true, HIGH);

          else if (moveRight)
            setMotorsXY(true, HIGH, true, LOW);

          else {
            motor1Running = false;
            motor2Running = false;
          }

          // --------------------------------------------------------------
          // Z-AXIS CONTROL
          // --------------------------------------------------------------

          if (pressedKeys.indexOf('z') >= 0)
            moveZ(HIGH);

          else if (pressedKeys.indexOf('x') >= 0)
            moveZ(LOW);

          else
            motorZRunning = false;

          // --------------------------------------------------------------
          // SERVO TOGGLE CONTROL
          // --------------------------------------------------------------

          if (pressedKeys.indexOf('v') >= 0) {

            if (millis() - lastServoToggle > 500) {

              servoState = !servoState;

              mainServo.attach(SERVO_PIN);

              mainServo.write(
                servoState ? angleDown : angleUp
              );

              servoMoveStartTime = millis();
              isServoTimerActive = true;

              lastServoToggle = millis();
            }
          }

          // --------------------------------------------------------------
          // RELAY OUTPUT CONTROL
          // --------------------------------------------------------------

          digitalWrite(
            RELAY1_PIN,
            (pressedKeys.indexOf('1') >= 0) ? HIGH : LOW
          );

          digitalWrite(
            RELAY2_PIN,
            (pressedKeys.indexOf('2') >= 0) ? HIGH : LOW
          );
        }
      }
    }
  }

  // ------------------------------------------------------------------------
  // IDLE STATE HANDLING
  // ------------------------------------------------------------------------

  if (!motor1Running &&
      !motor2Running &&
      !motorZRunning) {

    delay(1);
    return;
  }

  // ------------------------------------------------------------------------
  // STEP PULSE GENERATION
  // ------------------------------------------------------------------------

  int currentDelay =
    (motorZRunning) ? delayZ : delayCoreXY;

  // Generate HIGH pulse
  if (motor1Running) digitalWrite(PUL1_PIN, HIGH);
  if (motor2Running) digitalWrite(PUL2_PIN, HIGH);
  if (motorZRunning) digitalWrite(PULZ_PIN, HIGH);

  delayMicroseconds(currentDelay);

  // Generate LOW pulse
  if (motor1Running) digitalWrite(PUL1_PIN, LOW);
  if (motor2Running) digitalWrite(PUL2_PIN, LOW);
  if (motorZRunning) digitalWrite(PULZ_PIN, LOW);

  delayMicroseconds(currentDelay);
}