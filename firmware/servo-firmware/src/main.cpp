#include "bus.h"
#include "constants.h"
#include "led.h"
#include "motor.h"
#include <Arduino.h>

tinyNeoPixel pixels(1, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

bool stateError = false;
uint32_t lastPacketTime = 0;
uint32_t lastMasterPacketTime = 0;
uint8_t lastSeenTargetId = 255;
uint32_t dataLedOffTime = 0;

void setup() {
  pinMode(MAGNET_PIN, INPUT_PULLUP);
  pinMode(BUTTON_STEP, INPUT_PULLUP);
  pinMode(BUTTON_HOME, INPUT_PULLUP);

  setupLED();
  setupBus();
  setupMotor();
}

void loop() {
  magnetPresent = (digitalRead(MAGNET_PIN) == LOW);
  updateEncoder();
  updateBus();
  updateMotor();
  updateLED();
}
