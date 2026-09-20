#include "motor.h"
#include "LADRC.h"
#include "bus.h"
#include "constants.h"
#include <Arduino.h>
#include <Servo.h>

Servo servo;
SecondOrderLADRC jointController;

const uint32_t LOOP_PERIOD_US = 1000;
static uint32_t lastLoopTimeUs = 0;

enum HomePhase {
  HOME_PHASE_IDLE,
  HOME_PHASE_JOG_FIND, // Find the initial magnet position
  HOME_PHASE_JOG_FWD,  // Forward jog to clear magnet
  HOME_PHASE_JOG_REV   // Backward jog latch precise home edge
};

static HomePhase homePhase = HOME_PHASE_IDLE;

float readEncoderDegrees() {
  int32_t cpr = (countsPerRev != 0) ? countsPerRev : FIXED_CPR;
  return (float)totalAngleRaw * 360.0f / (float)cpr;
}

void driveServo(int16_t pwm) {
  // 90 is servo hold position
  if (pwm == 90) {
    servo.write(90);
    return;
  }

  // Each servo has a different setting, load that now
  bool flipDir = false;
  float mult = 1.0f;

  // Look up settings based on hardware ID
  if (hardwareID < NUM_SERVO_PROFILES) {
    flipDir = SERVO_PROFILES[hardwareID].flipDirection;
    mult = SERVO_PROFILES[hardwareID].speedMultiplier;
  }

  int16_t offset = pwm - 90;
  if (flipDir) {
    offset = -offset;
  }

  float finalPWM = 90.0f + (float)offset * mult;

  // Constrain the pwm between 0 and 180
  int16_t constrainedPWM = finalPWM;
  if (constrainedPWM < 0) {
    constrainedPWM = 0;
  }
  if (constrainedPWM > 180) {
    constrainedPWM = 180;
  }

  servo.write((uint8_t)constrainedPWM);
}

// Scales the "effort" from the LADRC controller to a PWM value
void setMotorEffort(float u) {
  if (fabsf(u) < 0.02f) {
    driveServo(90);
    return;
  }

  float dir = (u > 0.0f) ? 1.0f : -1.0f;
  float mag = fabsf(u);
  if (mag > 1.0f) {
    mag = 1.0f;
  }

  float speed =
      (float)POS_MIN_SPEED + mag * (float)(POS_MAX_SPEED - POS_MIN_SPEED);
  driveServo(90 - (int16_t)roundf(dir * speed));
}

void setupMotor() {
  servo.attach(PIN_PB0);

  // Controller configuration
  SecondOrderLADRC::Params p;
  p.b0 = 4000.0f;    // Initial rough estimate
  p.wc = 15.0f;      // Controller bandwidth
  p.wo = 60.0f;      // Observer bandwidth
  p.ts = 0.001f;     // 1 ms (1 kHz)
  p.out_min = -1.0f; // Normalized full reverse
  p.out_max = 1.0f;  // Normalized full forward

  jointController.init(p, readEncoderDegrees());
  lastLoopTimeUs = micros();
}

void doHoming() {
  // Homing, so ignore the angle input for now aoidaijdaijdawoijda
  homed = false;
  calibrated = false;
  ctrlMode = MODE_HOMING;

  switch (homePhase) {
  case HOME_PHASE_JOG_FIND:
    // We want to find the magnet initially
    if (magnetPresent) {
      homePhase = HOME_PHASE_JOG_FWD;
      break;
    }

    driveServo(HOMING_REV_SPEED);
    break;

  case HOME_PHASE_JOG_FWD:
    if (!magnetPresent) {
      homePhase = HOME_PHASE_JOG_REV;
      break;
    }

    driveServo(HOMING_JOG_FWD_SPEED);
    break;

  case HOME_PHASE_JOG_REV:
    if (magnetPresent) {
      homePhase = HOME_PHASE_IDLE;
      homed = true;
      calibrated = true;
      countsPerRev = FIXED_CPR;
      totalAngleRaw = 0; // Reset the count to zero as it's homed :)
      targetRaw =
          (int32_t)((int64_t)servoCommand.targetAngle * countsPerRev / 3600LL);
      ctrlMode = MODE_POSITION;
      jointController.reset(0.0f);
      driveServo(90); // Stop the motor
      break;
    }

    driveServo(HOMING_JOG_REV_SPEED);
    break;
  }
}

void doNormal() {
  uint32_t now = micros();
  if (now - lastLoopTimeUs < LOOP_PERIOD_US) {
    return;
  }
  if (now - lastLoopTimeUs > 10000) {
    lastLoopTimeUs = now;
  } else {
    lastLoopTimeUs += LOOP_PERIOD_US;
  }

  // Read joint position
  float current_angle_deg = readEncoderDegrees();
  float target_angle_deg = (float)servoCommand.targetAngle / 10.0f;

  // Compute control effort
  float u = jointController.update(current_angle_deg, target_angle_deg, 0.0f);

  // Drive actuator
  setMotorEffort(u);
}

void updateMotor() {
  // PWM jog mode from bus
  if (servoCommand.jog) {
    driveServo(servoCommand.targetAngle > 180
                   ? 180
                   : (uint8_t)servoCommand.targetAngle);
    jointController.reset(readEncoderDegrees());
    return;
  }

  // STEP button manual jog forward
  if (digitalRead(BUTTON_STEP) == LOW) {
    driveServo(60);
    jointController.reset(readEncoderDegrees());
    return;
  }

  // Check if we need to start homing
  if ((servoCommand.performHome || digitalRead(BUTTON_HOME) == LOW) &&
      homePhase == HOME_PHASE_IDLE) {
    homePhase = HOME_PHASE_JOG_FIND;
  }

  if (homePhase != HOME_PHASE_IDLE) {
    doHoming();
  } else {
    // ONLY DO NORMAL IF WE ARE CALIBRATED!!! OR ELSE IT WILL JUST GO SOMEWHERE
    // RANDOM AND BREAK EVERYTHING :(((
    if (!calibrated) {
      return;
    }

    doNormal();
  }
}