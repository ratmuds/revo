#ifndef BUS_H
#define BUS_H

#include "constants.h"
#include <Arduino.h>
#include <SerialTransfer.h>
#include <Wire.h>

// --- Control Modes ---
enum CtrlMode { MODE_IDLE, MODE_HOMING, MODE_CALIBRATING, MODE_POSITION };

// --- RS485 Binary Structs (packed, byte-aligned with the Pico master) ---
struct __attribute__((__packed__)) IncomingPacket {
  uint8_t magic; // PACKET_MAGIC sync byte
  uint8_t targetPcbId;
  uint16_t targetAngle;
  uint8_t performHome;
  uint8_t rgbColor[3];
  uint16_t maxCurrent;
  uint8_t jog;      // 0 = normal (position/calibration); !=0 = raw PWM jog
                    // (targetAngle is literal 0..180)
  uint8_t checksum; // XOR of every byte above (incl. magic)
};

struct __attribute__((__packed__)) RespondPacket {
  uint8_t magic; // PACKET_MAGIC sync byte
  uint8_t targetPcbId;
  uint16_t angle;   // AS5600 angle in TENTHS of a degree (0..3599, single rev)
  uint8_t temp;     // NTC temperature in Celsius
  uint16_t current; // INA219 current in mA
  uint16_t voltage; // INA219 bus voltage in mV
  uint8_t magnet;   // Hall sensor state (1 = magnet present)
  uint8_t homed;    // Homing completed flag
  uint8_t servoFirmwareVersion;
  int32_t
      totalAngle; // SIGNED accumulated raw counts across revolutions (odometry)
  int32_t realAngle; // Calibrated OUTPUT angle in TENTHS of a degree (0..3599+)
  int32_t
      countsPerRev; // AS5600 raw counts per one OUTPUT revolution (gear ratio)
  uint8_t calibrated; // 1 once the gear ratio has been measured
  uint8_t checksum;   // XOR of every byte above (incl. magic)
};

struct __attribute__((__packed__)) ServoCommand {
  uint16_t targetAngle;
  uint16_t maxCurrent;
  bool performHome;
  uint8_t rgbColor[3];
  uint8_t jog;
};

extern IncomingPacket rxCommand;
extern RespondPacket txTelemetry;
extern ServoCommand servoCommand;
extern uint8_t hardwareID;
extern int32_t totalAngleRaw;
extern uint16_t currentRawAngle;

extern CtrlMode ctrlMode;
extern bool homed;
extern bool calibrated;
extern int32_t countsPerRev;
extern int32_t targetRaw;
extern bool magnetPresent;

void setupBus();
void updateBus();
void updateEncoder();
uint16_t readINA219Current();
uint16_t getBusVoltage();
uint8_t readNTCTemperature();

#endif // BUS_H
