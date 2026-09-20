#ifndef LED_H
#define LED_H

#include "bus.h"
#include "constants.h"
#include <Arduino.h>
#include <tinyNeoPixel.h>

extern tinyNeoPixel pixels;
extern bool stateError;
extern uint32_t lastPacketTime;
extern uint32_t lastMasterPacketTime;
extern uint8_t lastSeenTargetId;
extern uint32_t dataLedOffTime;

void setupLED();
void updateLED();

#endif // LED_H
