#include <Arduino.h>
#include <ArduinoJson.h>     // ArduinoJson v7
#include <SerialTransfer.h>
#include <Servo.h>
#include <Wire.h>            // Hardware I2C 

#define RS485_TX 16
#define RS485_RX 17
#define RS485_DE 18
#define SERVO_4_PIN 7
#define SERVO_5_PIN 14
#define SERVO_6_PIN 15

// AS5600 (voltage mode, OUT pin) analog angle feedback for the two local PWM
// servos that actually have an angle sensor.
// NOTE: On RP2350 / Pico 2 the ADC is ONLY available on GP26, GP27, GP28, GP29
// (these are 3.3V-max and NOT 5V tolerant). Power the AS5600 from 3.3V so its
// OUT pin stays within 0-3.3V. Remap the pins below to match your wiring.
#define AS5600_SERVO4_VOUT_PIN 19  // first local PWM servo (ID 4) telemetry
#define AS5600_SERVO5_VOUT_PIN 21  // second local PWM servo (ID 5) angle

// RP2350 / Pico 2 Pin Definitions for Wire0
#define I2C_SDA_PIN 8
#define I2C_SCL_PIN 9

// INA219 I2C Target Addresses based on strap configurations
#define INA_SERVO4_ADDR 0x40  // ADDR: GND, GND
#define INA_SERVO5_ADDR 0x44  // ADDR: 3V3, GND
#define INA_SERVO6_ADDR 0x41  // ADDR: GND, 3V3
#define INA_SHUNT_REG   0x01  // Shunt Voltage Register Address

SerialTransfer busTransfer;  
Servo servo4;
Servo servo5;
Servo servo6;
 
// --- RS485 Binary Structs (Perfectly matched to your working baseline) ---
struct __attribute__((__packed__)) IncomingPacket {
  uint8_t magic;        // PACKET_MAGIC sync byte
  uint8_t targetPcbId;
  uint16_t targetAngle;
  uint8_t performHome;
  uint8_t rgbColor[3];
  uint16_t maxCurrent;
  uint8_t checksum;   // XOR of every byte above (incl. magic)
};

struct __attribute__((__packed__)) RespondPacket {
  uint8_t magic;                 // PACKET_MAGIC sync byte
  uint8_t targetPcbId;
  uint16_t angle;
  uint8_t temp;
  uint16_t current;
  uint16_t voltage;
  uint8_t magnet;
  uint8_t homed;
  uint8_t servoFirmwareVersion;
  int32_t totalAngle;             // SIGNED accumulated raw counts across revolutions (odometry)
  int32_t realAngle;              // Calibrated OUTPUT angle in tenths of a degree
  int32_t countsPerRev;           // AS5600 raw counts per output revolution (gear ratio)
  uint8_t calibrated;             // 1 once gear ratio measured
  uint8_t checksum;   // XOR of every byte above (incl. magic)
};

#define PACKET_MAGIC 0xA5

// Lightweight 8-bit XOR checksum (must match the servo firmware)
uint8_t calcChecksum(const uint8_t* data, uint8_t len) {
  uint8_t c = 0;
  for (uint8_t i = 0; i < len; i++) c ^= data[i];
  return c;
}

IncomingPacket txData;
RespondPacket rxData;

// --- Local State Cache to compile the final JSON telemetry response ---
struct JointState {
  bool online = false;
  uint16_t angle = 0;
  uint8_t temp = 0;
  uint16_t current = 0;
  uint16_t voltage = 0;
  uint8_t magnet = 0;
  uint8_t homed = 0;
  uint8_t fw = 0;
  int32_t totalAngle = 0;   // odometry: signed accumulated raw AS5600 counts
  int32_t realAngle = 0;    // calibrated output angle (tenths of a degree)
  int32_t countsPerRev = 0; // gear ratio: raw counts per output revolution
  uint8_t calibrated = 0;   // 1 once gear ratio measured
  uint8_t chk = 0;   // checksum valid flag from servo
};
JointState joints[7];

const uint8_t MAX_RS485_PCBS = 4;
uint8_t currentPcbId = 0;
uint32_t loopCounter = 0;

// Read AS5600 OUT pin (voltage mode) and return angle in tenths of a degree.
// 0V -> 0deg, 3.3V (VCC) -> 360deg  =>  tenths = raw / 4095 * 3600
uint16_t readAs5600AngleTenths(uint8_t pin) {
  int raw = analogRead(pin);                 // 12-bit: 0..4095 for 0..3.3V
  uint32_t tenths = (uint32_t)raw * 3600UL / 4095UL;
  return (uint16_t)tenths;
}

// Helper to read and compute current in mA directly from register maps
uint16_t readInaCurrentmA(uint8_t address) {
  Wire.beginTransmission(address);
  Wire.write(INA_SHUNT_REG);
  if (Wire.endTransmission() != 0) {
    return 0; // Device not acknowledging or missing
  }

  Wire.requestFrom(address, (uint8_t)2);
  if (Wire.available() >= 2) {
    int16_t rawShunt = (Wire.read() << 8) | Wire.read();
    // 10uV per count / 0.05 Ohms shunt = rawShunt / 5 for mA
    int32_t currentmA = rawShunt / 5;
    return (currentmA < 0) ? (uint16_t)(-currentmA) : (uint16_t)currentmA;
  }
  return 0;
}

void setup() {
  // Fast communication link to Python script on the PC
  Serial.begin(115200); 
  
  pinMode(RS485_DE, OUTPUT);
  digitalWrite(RS485_DE, LOW); 
  
  // High-reliability baseline configuration for the physical bus
  Serial1.setTX(RS485_TX);
  Serial1.setRX(RS485_RX);
  Serial1.begin(9600);        
  busTransfer.begin(Serial1);

  // Initialize Hardware I2C with specified RP2350 pins
  Wire.setSDA(I2C_SDA_PIN);
  Wire.setSCL(I2C_SCL_PIN);
  Wire.begin();
  Wire.setClock(400000); // Run standard Fast Mode (400kHz)

  // Local physical PWM connections
  servo4.attach(SERVO_4_PIN, 500, 2500);
  servo5.attach(SERVO_5_PIN, 500, 2500);
  servo6.attach(SERVO_6_PIN, 500, 2500);

  // Configure 12-bit ADC for the AS5600 OUT pin readings
  analogReadResolution(12);
}

void loop() {
  // Check for incoming operational directives from Python
  if (Serial.available()) {
    String jsonIn = Serial.readStringUntil('\n');

    JsonDocument doc; 
    DeserializationError error = deserializeJson(doc, jsonIn);

    if (!error && doc["magic"] == "REVO") {
      JsonArray servos = doc["servos"];

      // Process only if a complete payload for all 7 kinematics is present
      if (servos.size() == 7) {
        
        // ----------------------------------------------------------------------
        // A. Update Local Hardware PWM Lines (IDs 4, 5, 6)
        // ----------------------------------------------------------------------
        servo4.write(servos[4]["a"].as<uint16_t>());
        servo5.write(servos[5]["a"].as<uint16_t>());
        servo6.write(servos[6]["a"].as<uint16_t>());

        // Gather real telemetry from INA219 chips
        joints[4].current = readInaCurrentmA(INA_SERVO4_ADDR);
        joints[5].current = readInaCurrentmA(INA_SERVO5_ADDR);
        joints[6].current = readInaCurrentmA(INA_SERVO6_ADDR);

        // Maintain local telemetry cache for the analog PWM joints
        // First two local PWM servos have real AS5600 angle sensors
        joints[4].angle = readAs5600AngleTenths(AS5600_SERVO4_VOUT_PIN);
        joints[5].angle = readAs5600AngleTenths(AS5600_SERVO5_VOUT_PIN);
        // Third local PWM servo has no sensor: echo the commanded value from PC
        joints[6].angle = servos[6]["a"].as<uint16_t>();

        for (int i = 4; i < 7; i++) {
          joints[i].online  = true;
          joints[i].temp    = 0;   
          joints[i].voltage = 0;
          joints[i].magnet  = 0;
          joints[i].homed   = 0;
          joints[i].fw      = 10;
          joints[i].chk     = 1;
        }

        // ----------------------------------------------------------------------
        // B. Query Single RS-485 Target Component via the Serial Pipeline
        // ----------------------------------------------------------------------
        JsonObject currentRs485Cmd = servos[currentPcbId];
        
        // Wrap JSON primitives securely into structured binary data
        txData.magic       = PACKET_MAGIC;
        txData.targetPcbId = currentPcbId;
        txData.targetAngle = currentRs485Cmd["a"].as<uint16_t>();
        txData.performHome = currentRs485Cmd["h"].as<uint8_t>();
        txData.maxCurrent  = currentRs485Cmd["c"].as<uint16_t>();
        txData.rgbColor[0] = currentRs485Cmd["rgb"][0].as<uint8_t>();
        txData.rgbColor[1] = currentRs485Cmd["rgb"][1].as<uint8_t>();
        txData.rgbColor[2] = currentRs485Cmd["rgb"][2].as<uint8_t>();
        txData.checksum    = calcChecksum((uint8_t*)&txData, sizeof(txData) - 1);

        busTransfer.txObj(txData);
        
        // Switch to Transmit Mode
        digitalWrite(RS485_DE, HIGH);
        delayMicroseconds(50);
        
        busTransfer.sendData(sizeof(txData));
        Serial1.flush();               
        
        // The magical baseline timing padding that prevents line collision
        delay(2); 
        
        // Release line back to Receive Mode to clear path for ATtiny response
        digitalWrite(RS485_DE, LOW);   
        
        // Check for incoming packets (200ms listening horizon)
        unsigned long startMillis = millis();
        bool responseReceived = false;
        
        while (millis() - startMillis < 200) { 
          if (busTransfer.available()) {
            busTransfer.rxObj(rxData);
            responseReceived = true;
            break;
          }
        }
        
        // Evaluate feedback validity against our round-robin token index
        uint8_t chkOk = 0;
        if (responseReceived) {
          uint8_t exp = calcChecksum((uint8_t*)&rxData, sizeof(rxData) - 1);
          chkOk = (rxData.magic == PACKET_MAGIC && rxData.checksum == exp) ? 1 : 0;
        }
        if (responseReceived && chkOk && (rxData.targetPcbId == currentPcbId)) {
          joints[currentPcbId].online  = true;
          joints[currentPcbId].angle   = rxData.angle;
          joints[currentPcbId].temp    = rxData.temp;
          joints[currentPcbId].current = rxData.current;
          joints[currentPcbId].voltage = rxData.voltage;
          joints[currentPcbId].magnet  = rxData.magnet;
          joints[currentPcbId].homed   = rxData.homed;
          joints[currentPcbId].fw      = rxData.servoFirmwareVersion;
          joints[currentPcbId].totalAngle = rxData.totalAngle;
          joints[currentPcbId].realAngle = rxData.realAngle;
          joints[currentPcbId].countsPerRev = rxData.countsPerRev;
          joints[currentPcbId].calibrated = rxData.calibrated;
          joints[currentPcbId].chk     = chkOk;
        } else {
          joints[currentPcbId].online  = false; 
        }

        // ----------------------------------------------------------------------
        // C. Ship Compiled JSON Status Frame back up to Python
        // ----------------------------------------------------------------------
        JsonDocument outDoc;
        outDoc["magic"] = "STAT";
        outDoc["counter"] = loopCounter++;
        
        JsonArray outJoints = outDoc["joints"].to<JsonArray>();
        
        for (int i = 0; i < 7; i++) {
          JsonObject j = outJoints.add<JsonObject>();
          j["id"] = i;
          j["o"] = joints[i].online ? 1 : 0;
          
            if (joints[i].online) {
              j["a"] = joints[i].angle;
              j["t"] = joints[i].temp;
              j["c"] = joints[i].current;
              j["v"] = joints[i].voltage;
              j["m"] = joints[i].magnet;
              j["h"] = joints[i].homed;
              j["f"] = joints[i].fw;
              j["ta"] = joints[i].totalAngle;
              j["ra"] = joints[i].realAngle;
              j["cpr"] = joints[i].countsPerRev;
              j["cal"] = joints[i].calibrated;
              j["chk"] = joints[i].chk;
            }
        }

        // Serialize and push downstream via native high-speed USB interface
        serializeJson(outDoc, Serial);
        Serial.println();

        // Increment target pointer to address the next slave on the next loop
        currentPcbId++;
        if (currentPcbId >= MAX_RS485_PCBS) {
          currentPcbId = 0;
        }
      }
    }
  }
}