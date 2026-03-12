#include <AccelStepper.h>

#define STEP_PIN_A 12
#define DIR_PIN_A 13
#define STEP_PIN_B 14
#define DIR_PIN_B 27

AccelStepper stepperA(AccelStepper::DRIVER, STEP_PIN_A, DIR_PIN_A);
AccelStepper stepperB(AccelStepper::DRIVER, STEP_PIN_B, DIR_PIN_B);

const float PIXEL_TO_STEP_RATIO = 1.0; 

struct PIDController {
    float Kp, Ki, Kd;
    float integral, prevError;
};

PIDController pidX = {1.0, 0.0, 0.0, 0.0, 0.0}; 
PIDController pidY = {1.0, 0.0, 0.0, 0.0, 0.0};

unsigned long lastLogTime = 0;
const int LOG_INTERVAL = 20;

float computePID(float error, PIDController &pid) {
    pid.integral += error;
    if(pid.integral > 500) pid.integral = 500;
    if(pid.integral < -500) pid.integral = -500;
    float derivative = error - pid.prevError;
    pid.prevError = error;
    return (pid.Kp * error) + (pid.Ki * pid.integral) + (pid.Kd * derivative);
}

void setup() {
    Serial.begin(115200);
    
    stepperA.setMaxSpeed(4000.0);
    stepperA.setAcceleration(2000.0);
    stepperB.setMaxSpeed(4000.0);
    stepperB.setAcceleration(2000.0);
    
    Serial.println("System CoreXY gotowy. Wpisz koordynaty (np. 92,-90)");
}

void loop() {
    stepperA.run();
    stepperB.run();

    if (millis() - lastLogTime >= LOG_INTERVAL) {
        lastLogTime = millis();
        
        if (stepperA.distanceToGo() != 0 || stepperB.distanceToGo() != 0) {
            Serial.printf("CelA:%ld,PozA:%ld,CelB:%ld,PozB:%ld\n", 
                          stepperA.targetPosition(), 
                          stepperA.currentPosition(),
                          stepperB.targetPosition(),
                          stepperB.currentPosition());
        }
    }

    if (Serial.available() > 0) {
        String input = Serial.readStringUntil('\n');
        input.trim();
        
        int commaIndex = input.indexOf(',');
        if (commaIndex > 0) {
            float targetX = input.substring(0, commaIndex).toFloat();
            float targetY = input.substring(commaIndex + 1).toFloat();
            
            bool usePID = true; 
            float correctedX = targetX;
            float correctedY = targetY;
            
            if (usePID) {
                correctedX = computePID(targetX, pidX);
                correctedY = computePID(targetY, pidY);
            }
            
            float stepsA = (correctedX + correctedY) * PIXEL_TO_STEP_RATIO;
            float stepsB = (correctedX - correctedY) * PIXEL_TO_STEP_RATIO;
            
            stepperA.move(round(stepsA));
            stepperB.move(round(stepsB));
        }
    }
}