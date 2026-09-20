#include "led.h"

void setupLED() {
  pixels.begin();
  pixels.setPixelColor(0, pixels.Color(0, 0, 0));
  pixels.show();

  pinMode(DATA_LED, OUTPUT);
  digitalWrite(DATA_LED, LOW);
}

void updateLED() {
  unsigned long currentMillis = millis();

  // Pulse DATA_LED off after bus activity
  if (currentMillis / 500 % 2 == 0) {
    digitalWrite(DATA_LED, LOW);
  } else {
    digitalWrite(DATA_LED, HIGH);
  }

  // Limit neopixel updates
  static unsigned long lastPixelUpdate = 0;
  if (currentMillis - lastPixelUpdate >= 40) {
    lastPixelUpdate = currentMillis;

    // Track corruption errors with a visible 400ms strobe
    static unsigned long lastErrorTime = 0;
    if (stateError) {
      stateError = false; // reset flag
      lastErrorTime = currentMillis;
    }

    // Packet corruption error
    if (currentMillis - lastErrorTime < 400) {
      if ((currentMillis / 80) % 2) {
        pixels.setPixelColor(0, pixels.Color(255, 0, 0));
      } else {
        pixels.setPixelColor(0, pixels.Color(0, 0, 0));
      }
    }

    // Power on blink routine ( 2.5 seconds ) (ima be honest this is just to
    // make it look cool)
    else if (currentMillis < 2500) {
      uint32_t phase = currentMillis % 2500;
      uint8_t blinks = hardwareID + 1;
      if (phase < (uint32_t)blinks * 350) {
        if ((phase % 350) < 200) {
          pixels.setPixelColor(0, pixels.Color(0, 200, 200)); // Bright Cyan
        } else {
          pixels.setPixelColor(0, pixels.Color(0, 0, 0));
        }
      } else {
        pixels.setPixelColor(0, pixels.Color(0, 0, 0));
      }
    }
    // Actively Homing or Calibrating
    else if (ctrlMode == MODE_HOMING || ctrlMode == MODE_CALIBRATING) {
      if ((currentMillis / 150) % 2) {
        pixels.setPixelColor(0, pixels.Color(180, 140, 0));
      } else {
        pixels.setPixelColor(0, pixels.Color(0, 0, 0));
      }
    }

    // Offline because no packets received for this servo within 1500ms
    else if (currentMillis - lastPacketTime > 1500) {
      // Are master packets actively arriving on the bus for OTHER servos?
      if (lastMasterPacketTime > 0 &&
          (currentMillis - lastMasterPacketTime < 1500)) {
        // Bus active, but ID Mismatch (not the correct ID)
        // Amber/Orange: Master is talking, but this PCB's address doesn't
        // match! Periodically flashes (hardwareID + 1) times so you can read
        // this board's ID
        uint32_t cycle = currentMillis % 3000;
        uint8_t blinks = hardwareID + 1;
        if (cycle < (uint32_t)blinks * 300) {
          if ((cycle % 300) < 180) {
            pixels.setPixelColor(
                0, pixels.Color(255, 120, 0)); // Bright Amber blink
          } else {
            pixels.setPixelColor(0, pixels.Color(15, 6, 0)); // Dim Amber floor
          }
        } else {
          pixels.setPixelColor(0, pixels.Color(15, 6, 0)); // Dim Amber floor
        }
      } else {
        // BUS SILENT (No master packets seen at all)
        // Slow blinking Red (500ms ON, 500ms OFF)
        if ((currentMillis / 500) % 2) {
          pixels.setPixelColor(0, pixels.Color(120, 0, 0)); // Red
        } else {
          pixels.setPixelColor(0, pixels.Color(0, 0, 0));
        }
      }
    }
    // Online and Connected
    else {
      if (calibrated) {
        pixels.setPixelColor(0, pixels.Color(0, 120, 0)); // Solid Green
      } else {
        pixels.setPixelColor(0, pixels.Color(0, 0, 120)); // Solid Blue
      }
    }

    pixels.show();
  }
}