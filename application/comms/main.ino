/*
 * CSAimBot Motor Control Firmware
 * ESP32-based controller for CoreXY robotic platform with Z-axis servo
 * 
 * Handles stepper motor control, limit switches, encoders, servo actuation,
 * and serial communication protocol.
 */

#include <ESP32Servo.h>

// ============================================================================
// PIN DEFINITIONS
// ============================================================================

// Motor stepping and direction pins (stepper motor drivers)
#define PUL1_PIN 4    // Motor 1 pulse (X-axis primary)
#define DIR1_PIN 5    // Motor 1 direction
#define PUL2_PIN 6    // Motor 2 pulse (Y-axis primary)
#define DIR2_PIN 7    // Motor 2 direction
#define PULZ_PIN 8    // Motor Z pulse (vertical axis)
#define DIRZ_PIN 9    // Motor Z direction

// Limit switch inputs (normally open, triggered on home position)
#define LIMIT_X_PIN 10
#define LIMIT_Y_PIN 11
#define LIMIT_Z_PIN 12

// Rotary encoder feedback pins
#define ENCO1_PHASE_A 13
#define ENCO1_PHASE_B 14
#define ENCO2_PHASE_A 15
#define ENCO2_PHASE_B 16

// Servo and relay control pins
#define SERVO_PIN 17
#define RELAY1_PIN 18
#define RELAY2_PIN 21

// ============================================================================
// CONFIGURATION & STATE VARIABLES
// ============================================================================

int delayCoreXY = 800;           // Pulse delay for CoreXY motors (microseconds)
const int delayZ = 1200;         // Pulse delay for Z-axis motor (microseconds)
int homingDelay = 1500;          // Homing sequence pulse delay

bool motor1Running = false;
bool motor2Running = false;
bool motorZRunning = false;

volatile long encoder1Count = 0; // Interrupt-driven encoder position tracking
volatile long encoder2Count = 0;
unsigned long lastPrintTime = 0;
unsigned long lastServoToggle = 0;

Servo mainServo;
bool servoState = false;

int posX = 0;
int posY = 0;
String pressedKeys = "";

// ============================================================================
// ENCODER INTERRUPT HANDLERS
// ============================================================================

/**
 * @brief Interrupt handler for encoder 1 (quadrature decoding)
 * Increments or decrements position count based on phase relationship
 */
void IRAM_ATTR readEncoder1() {
  if (digitalRead(ENCO1_PHASE_A) == digitalRead(ENCO1_PHASE_B)) encoder1Count++;
  else encoder1Count--;
}

/**
 * @brief Interrupt handler for encoder 2 (quadrature decoding)
 * Increments or decrements position count based on phase relationship
 */
void IRAM_ATTR readEncoder2() {
  if (digitalRead(ENCO2_PHASE_A) == digitalRead(ENCO2_PHASE_B)) encoder2Count++;
  else encoder2Count--;
}

// ============================================================================
// MOTOR CONTROL FUNCTIONS
// ============================================================================

/**
 * @brief Halts all motor movement immediately
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
 * @brief Configures CoreXY axis motors with specified directions
 * @param run1  Enable motor 1
 * @param dir1  Direction for motor 1 (HIGH/LOW)
 * @param run2  Enable motor 2
 * @param dir2  Direction for motor 2 (HIGH/LOW)
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
 * @brief Initiates Z-axis (vertical) motor movement
 * @param dirZ Direction of motion (HIGH=up, LOW=down)
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
 * @brief Homes all axes to reference position using limit switches
 * Sequence: Z-axis home → X-axis home → Y-axis home
 * Applies backlash compensation (300, 200, 200 steps respectively)
 */
void performHoming() {
  Serial.println("Homing start...");
  stopAllMotors();

  // 1. Z-Axis (Up/Down) - Home at upper position
  digitalWrite(DIRZ_PIN, LOW);
  while(digitalRead(LIMIT_Z_PIN) == HIGH) {
    digitalWrite(PULZ_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PULZ_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1); // Replaced yield() to prevent WDT reset
  }
  // Backlash compensation: move away from limit
  digitalWrite(DIRZ_PIN, HIGH);
  for(int i = 0; i < 300; i++) {
    digitalWrite(PULZ_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PULZ_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }

  // 2. X-Axis home
  digitalWrite(DIR1_PIN, LOW); digitalWrite(DIR2_PIN, HIGH);
  while(digitalRead(LIMIT_X_PIN) == HIGH) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }
  // Backlash compensation
  digitalWrite(DIR1_PIN, HIGH); digitalWrite(DIR2_PIN, LOW);
  for(int i = 0; i < 200; i++) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }

  // 3. Y-Axis home
  digitalWrite(DIR1_PIN, LOW); digitalWrite(DIR2_PIN, LOW);
  while(digitalRead(LIMIT_Y_PIN) == HIGH) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }
  // Backlash compensation
  digitalWrite(DIR1_PIN, HIGH); digitalWrite(DIR2_PIN, HIGH);
  for(int i = 0; i < 200; i++) {
    digitalWrite(PUL1_PIN, HIGH); digitalWrite(PUL2_PIN, HIGH); delayMicroseconds(homingDelay);
    digitalWrite(PUL1_PIN, LOW); digitalWrite(PUL2_PIN, LOW); delayMicroseconds(homingDelay);
    delay(1);
  }

  // Reset position counters
  posX = 0; posY = 0;
  Serial.println("Homing OK!");
}

// ============================================================================
// SETUP & INITIALIZATION
// ============================================================================

/**
 * @brief Initializes hardware pins, serial communication, and interrupt handlers
 */
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(30);

  // Configure stepper motor output pins
  pinMode(PUL1_PIN, OUTPUT); pinMode(DIR1_PIN, OUTPUT);
  pinMode(PUL2_PIN, OUTPUT); pinMode(DIR2_PIN, OUTPUT);
  pinMode(PULZ_PIN, OUTPUT); pinMode(DIRZ_PIN, OUTPUT);
  pinMode(RELAY1_PIN, OUTPUT); pinMode(RELAY2_PIN, OUTPUT);

  // Configure encoder input pins
  pinMode(ENCO1_PHASE_A, INPUT); pinMode(ENCO1_PHASE_B, INPUT);
  pinMode(ENCO2_PHASE_A, INPUT_PULLUP); pinMode(ENCO2_PHASE_B, INPUT_PULLUP);

  // Configure limit switch inputs (active LOW)
  pinMode(LIMIT_X_PIN, INPUT_PULLUP);
  pinMode(LIMIT_Y_PIN, INPUT_PULLUP);
  pinMode(LIMIT_Z_PIN, INPUT_PULLUP);

  // Initialize all outputs to safe state
  stopAllMotors();
  digitalWrite(RELAY1_PIN, LOW);
  digitalWrite(RELAY2_PIN, LOW);

  // Initialize servo
  mainServo.attach(SERVO_PIN);
  mainServo.write(0);

  // Attach encoder interrupt handlers for quadrature decoding
  attachInterrupt(digitalPinToInterrupt(ENCO1_PHASE_A), readEncoder1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCO2_PHASE_A), readEncoder2, CHANGE);

  Serial.println("System Ready");
}

// ============================================================================
// MAIN CONTROL LOOP
// ============================================================================

/**
 * @brief Main execution loop
 * 
 * Protocol: "dX,dY,speed,keys\r"
 * - dX, dY: Target position deltas
 * - speed: 1-100 (maps to motor delay)
 * - keys: Command characters (ijkl:move, z/x:z-axis, v:servo, 1/2:relays, h:home, p:pause)
 */
void loop() {
  // Limit switch monitoring for safety (active LOW)
  bool limitX = (digitalRead(LIMIT_X_PIN) == LOW);
  bool limitY = (digitalRead(LIMIT_Y_PIN) == LOW);
  bool limitZ = (digitalRead(LIMIT_Z_PIN) == LOW);

  // Emergency stop if limit switches triggered during motion
  if ((limitX || limitY || limitZ) && (motor1Running || motor2Running || motorZRunning)) {
      stopAllMotors();
      Serial.println("ALARM_LIMIT");
  }

  // Serial command parsing
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\r');
    data.trim();

    if (data.length() > 0) {
      // Parse comma-delimited format
      int commaIndexOne = data.indexOf(',');
      int commaIndexTwo = data.indexOf(',', commaIndexOne + 1);
      int commaIndexThree = data.indexOf(',', commaIndexTwo + 1);

      if (commaIndexOne > 0 && commaIndexTwo > 0 && commaIndexThree > 0) {
        posX = data.substring(0, commaIndexOne).toInt();
        posY = data.substring(commaIndexOne + 1, commaIndexTwo).toInt();
        int speedValue = data.substring(commaIndexTwo + 1, commaIndexThree).toInt();

        // Map speed value (1-100) to motor delay
        if(speedValue >= 1 && speedValue <= 100) {
          delayCoreXY = (int)(1000000.0 / (100.0 + ((speedValue - 1.0) / 99.0) * 9900.0));
        }
        pressedKeys = data.substring(commaIndexThree + 1);

        // Diagnostic feedback
        Serial.print("Understood dX: ");
        Serial.print(posX);
        Serial.print(" dY: ");
        Serial.print(posY);
        Serial.print(" Speed: ");
        Serial.print(speedValue);
        Serial.print(" Keys: ");
        Serial.println(pressedKeys);

        // Command execution
        if (pressedKeys.length() > 0) {
          if (pressedKeys.indexOf('p') >= 0) {
            // Pause command
            stopAllMotors();
          } else if (pressedKeys.indexOf('h') >= 0) {
            // Home command
            performHoming();
          } else {
            // CoreXY movement logic (i/k/j/l keys)
            bool moveUp = pressedKeys.indexOf('i') >= 0;
            bool moveDown = pressedKeys.indexOf('k') >= 0;
            bool moveLeft = pressedKeys.indexOf('j') >= 0;
            bool moveRight = pressedKeys.indexOf('l') >= 0;

            // Determine motor configuration based on direction keys
            if (moveUp && moveLeft) setMotorsXY(false, LOW, true, HIGH);
            else if (moveUp && moveRight) setMotorsXY(true, HIGH, false, LOW);
            else if (moveDown && moveLeft) setMotorsXY(true, LOW, false, LOW);
            else if (moveDown && moveRight) setMotorsXY(false, LOW, true, LOW);
            else if (moveUp) setMotorsXY(true, HIGH, true, HIGH);
            else if (moveDown) setMotorsXY(true, LOW, true, LOW);
            else if (moveLeft) setMotorsXY(true, LOW, true, HIGH);
            else if (moveRight) setMotorsXY(true, HIGH, true, LOW);
            else { motor1Running = false; motor2Running = false; }

            // Z-axis movement (z=up, x=down)
            if (pressedKeys.indexOf('z') >= 0) moveZ(HIGH);
            else if (pressedKeys.indexOf('x') >= 0) moveZ(LOW);
            else motorZRunning = false;

            // Servo toggle with debouncing (v key)
            if (pressedKeys.indexOf('v') >= 0) {
              if (millis() - lastServoToggle > 500) {
                servoState = !servoState;
                mainServo.write(servoState ? 180 : 0);
                lastServoToggle = millis();
              }
            }

            // Solenoid/relay control (1 and 2 keys)
            digitalWrite(RELAY1_PIN, (pressedKeys.indexOf('1') >= 0) ? HIGH : LOW);
            digitalWrite(RELAY2_PIN, (pressedKeys.indexOf('2') >= 0) ? HIGH : LOW);
          }
        } else {
          // No keys pressed: idle state
          stopAllMotors();
          digitalWrite(RELAY1_PIN, LOW);
          digitalWrite(RELAY2_PIN, LOW);
        }
      }
    }
  }

  // Allow FreeRTOS background task handling when motors idle
  if (!motor1Running && !motor2Running && !motorZRunning) {
    delay(1);
    return;
  }

  // Step pulse generation for motor control
  int currentDelay = (motorZRunning) ? delayZ : delayCoreXY;

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