#include <ESP32Encoder.h>

// ============================================================================
// CoreXY pin definitions matching your hardware
// ============================================================================
#define PUL1_PIN 23
#define DIR1_PIN 22
#define PUL2_PIN 21
#define DIR2_PIN 19

#define ENCO1_PHASE_A 18
#define ENCO1_PHASE_B 5
#define ENCO2_PHASE_A 32
#define ENCO2_PHASE_B 33

ESP32Encoder encoder1;
ESP32Encoder encoder2;

void setup() {
  Serial.begin(115200);

  // Setup motor control pins for both motors
  pinMode(PUL1_PIN, OUTPUT);
  pinMode(DIR1_PIN, OUTPUT);
  pinMode(PUL2_PIN, OUTPUT);
  pinMode(DIR2_PIN, OUTPUT);
  
  digitalWrite(PUL1_PIN, LOW);
  digitalWrite(PUL2_PIN, LOW);
  digitalWrite(DIR1_PIN, LOW);
  digitalWrite(DIR2_PIN, LOW);

  // Setup both encoders with internal pull-ups
  ESP32Encoder::useInternalWeakPullResistors = puType::up;
  encoder1.attachHalfQuad(ENCO1_PHASE_A, ENCO1_PHASE_B);
  encoder2.attachHalfQuad(ENCO2_PHASE_A, ENCO2_PHASE_B);
  
  encoder1.clearCount();
  encoder2.clearCount();

  Serial.println("CoreXY Reaction Time Tester Ready.");
  Serial.println("Send '1' to move one way. Send '2' to move the other.");
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    // Ignore newlines and invalid chars
    if (cmd != '1' && cmd != '2') return;

    // Set direction based on command for both motors
    bool dirState = (cmd == '1') ? HIGH : LOW;
    digitalWrite(DIR1_PIN, dirState);
    digitalWrite(DIR2_PIN, dirState);

    // Record starting positions for BOTH encoders
    long startEnc1 = encoder1.getCount();
    long startEnc2 = encoder2.getCount();
    bool movementDetected = false;
    
    // Clear any remaining bytes in buffer
    while (Serial.available() > 0) Serial.read();

    // Record the exact time the command processing starts
    unsigned long cmdReceiveTime = micros();

    // Safe delay to prevent motor stalling on sudden startup
    const int stepDelayMicros = 700; 

    // Fire continuous steps until ANY encoder registers a change or timeout hits
    while (micros() - cmdReceiveTime < 500000) { 
      
      // Generate one step for both motors simultaneously
      digitalWrite(PUL1_PIN, HIGH);
      digitalWrite(PUL2_PIN, HIGH);
      delayMicroseconds(10); 

      // Pull the signal LOW and wait. 
      // This delay defines the speed and MUST be long enough for a cold start.
      digitalWrite(PUL1_PIN, LOW);
      digitalWrite(PUL2_PIN, LOW);
      delayMicroseconds(700);

      // Read current positions
      long currEnc1 = encoder1.getCount();
      long currEnc2 = encoder2.getCount();

      // Check if EITHER encoder noticed the movement
      if (currEnc1 != startEnc1 || currEnc2 != startEnc2) {
        unsigned long reactionTime = micros() - cmdReceiveTime;

        Serial.print("REACTION TIME: ");
        Serial.print(reactionTime / 1000.0, 2); 
        Serial.print(" ms | Triggered by: ");
        
        // Identify which encoder moved first
        if (currEnc1 != startEnc1 && currEnc2 != startEnc2) {
          Serial.println("BOTH (E1 & E2)");
        } else if (currEnc1 != startEnc1) {
          Serial.println("E1");
        } else {
          Serial.println("E2");
        }
        
        movementDetected = true;
        break; // Stop stepping immediately
      }
    }

    if (!movementDetected) {
      Serial.println("TIMEOUT: No encoder change detected.");
      Serial.print("Current counts -> E1: ");
      Serial.print(encoder1.getCount());
      Serial.print(" | E2: ");
      Serial.println(encoder2.getCount());
    }
  }
}