#include <AccelStepper.h>

//do not change
#define STEP_PIN_A 25
#define DIR_PIN_A 26
#define STEP_PIN_B 27
#define DIR_PIN_B 14

// Piny muszę jeszcze poprawić bo zapomniałem, że 34 i 35 to tylko wejscia 
#define ENC_A_CLK 35
#define ENC_A_DT  34

#define ENC_B_CLK 33
#define ENC_B_DT  32

// volatile bo bedzie uzywana w przerwaniach
volatile long encoderCountA = 0;
volatile long encoderCountB = 0;

AccelStepper stepperA(AccelStepper::DRIVER, STEP_PIN_A, DIR_PIN_A);
AccelStepper stepperB(AccelStepper::DRIVER, STEP_PIN_B, DIR_PIN_B);

//needs to be calibrated on tests
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
    
    pinMode(ENC_A_CLK, INPUT);
    pinMode(ENC_A_DT, INPUT);

    pinMode(ENC_B_CLK, INPUT);
    pinMode(ENC_B_DT, INPUT);

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
            
            bool usePID = false;
            
          
            float correctedX = targetX;
            float correctedY = targetY;
            
            
            
            if (usePID) 
            {
                // do testow uwazam ze najpierw trzeba zobaczyc jak to sie bedzie zachowywalo i dopiero w tedy dostarajac Pid Imo
                // no i musimy przekazywac blad a nie pozycje zadana
                // te dwa float tylko do testu trzeba je bedzie oczywiscie jakos odczytac z enkoderow


                float actualX;
                float actualY;

                float errorx = targetX - actualX;
                float errory = targetY - actualY;

                correctedX = computePID(errorx, pidX);
                correctedY = computePID(errory, pidY);
            }
            
            float stepsA = (correctedX + correctedY) * PIXEL_TO_STEP_RATIO;
            float stepsB = (correctedX - correctedY) * PIXEL_TO_STEP_RATIO;
            
            stepperA.move(round(stepsA));
            stepperB.move(round(stepsB));
        }
    }
}