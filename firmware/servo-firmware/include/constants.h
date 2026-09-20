#ifndef CONSTANTS_H
#define CONSTANTS_H

#include <Arduino.h>

#define DATA_LED PIN_PA3
#define RS485_DE PIN_PA4
#define NEOPIXEL_PIN PIN_PA6
#define MAGNET_PIN PIN_PA7 // DRV5032 Hall Effect Sensor on PA7
#define NTC_PIN PIN_PA5    // NTC Thermistor on PA5
#define VOLTAGE_PIN                                                            \
  PIN_PB1 // Voltage divider on PB1 (nominal 6V, 20k top, 10k bot)

#define BUTTON_STEP PIN_PB4 // STEP push button (active LOW)
#define BUTTON_HOME PIN_PB5 // HOME push button (active LOW)

#define ADDR_A1 PIN_PC2 // Address Pin Bit 0 (LSB)
#define ADDR_A2 PIN_PC1 // Address Pin Bit 1
#define ADDR_A3 PIN_PC0 // Address Pin Bit 2 (MSB)

#define FIXED_CPR 54000LL // Fixed counts per revolution (360 deg)
#define TICKS_OFFSET -200

// Continuous servo: 90=stop. < 90 is forward, > 90 is backward/reverse.
#define HOMING_SPEED 70         // Forward reference speed (90 - 20)
#define HOMING_REV_SPEED 110    // Backward seek speed towards magnet (90 + 20)
#define HOMING_JOG_FWD_SPEED 70 // Slow forward jog to clear magnet (90 - 10)
#define HOMING_JOG_REV_SPEED                                                   \
  105 // Slow backward jog to latch magnet edge (90 + 10)
#define HOMING_MAX_COUNTS                                                      \
  54000LL // Max reverse rotation before safety abort (~360 deg)
#define POS_DEADBAND                                                           \
  30 // raw counts: within this of target we consider "arrived"
#define POS_SLOWDOWN                                                           \
  600 // raw counts error at which duty-cycle pulsing / deceleration begins
#define POS_MIN_SPEED                                                          \
  7 // min speed offset to overcome servo deadband (97 fwd / 83 rev)
#define POS_MAX_SPEED 45 // 50% max speed/torque offset (45..135 PWM)
#define POS_CYCLE_MS                                                           \
  60 // PWM flickering period in ms (e.g. 60ms = 3 servo refresh frames)
#define POS_MIN_ON_MS 20 // minimum pulse ON time in ms for micro-stepping taps
#define PACKET_TIMEOUT_MS                                                      \
  1500 // No valid packet within this window -> "no connection"
#define PACKET_MAGIC                                                           \
  0xA5 // Sync byte: detects wrong/junk firmware or garbage on the bus

// --- Per-PCB Servo Hardware Profiles (Direction flip & PWM speed multiplier)
// ---
struct ServoHardwareProfile {
  bool flipDirection;    // Invert direction around 90 (true if servo spins
                         // opposite)
  float speedMultiplier; // Multiplier on (PWM - 90) offset (e.g. 0.5 for fast
                         // servos)
};

#define NUM_SERVO_PROFILES 8

// Configuration indexed by PCB Hardware ID (0 to 7)
const ServoHardwareProfile SERVO_PROFILES[NUM_SERVO_PROFILES] = {
    {false, 1.0f}, // ID 0: Standard
    {true, 0.5f},  // ID 1: Flipped direction & 0.5x speed
    {false, 1.0f}, // ID 2: Standard
    {false, 1.0f}, // ID 3: Standard
    {false, 1.0f}, // ID 4: Standard
    {false, 1.0f}, // ID 5: Standard
    {false, 1.0f}, // ID 6: Standard
    {false, 1.0f}, // ID 7: Standard
};

#endif // CONSTANTS_H
