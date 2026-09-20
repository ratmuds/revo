#include "bus.h"
#include "api/ArduinoAPI.h"
#include "led.h"

SerialTransfer transfer;
IncomingPacket rxCommand;
RespondPacket txTelemetry;
ServoCommand servoCommand;
uint8_t hardwareID = 0;

int32_t totalAngleRaw = 0;
uint16_t currentRawAngle = 0;
static uint16_t prevRawAngle = 0;
static bool angleSeeded = false;

CtrlMode ctrlMode = MODE_IDLE;
bool homed = false;
bool calibrated = false;
int32_t countsPerRev = FIXED_CPR;
int32_t targetRaw = 0;
bool magnetPresent = false;

uint8_t calcChecksum(const uint8_t *data, uint8_t len);

bool readAS5600Angle(uint16_t *out) {
  Wire.beginTransmission(0x36);
  Wire.write(0x0C); // Raw Angle MSB register
  if (Wire.endTransmission(false) != 0) {
    return false; // Communication failed
  }

  Wire.requestFrom(0x36, 2);
  if (Wire.available() >= 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    *out = ((uint16_t)(msb & 0x0F) << 8) | lsb; // 12-bit clean (0..4095)
    return true;
  }
  return false;
}

void configAS5600() {
  Wire.beginTransmission(0x36);
  Wire.write(0x07); // CONF MSB
  Wire.write(0x00); // PM=NOM, HYST=OFF, OUTS=analog
  Wire.write(0x3C); // SF=2x (0.286ms fastest response), FTH=24 LSBs, WD=OFF
  Wire.endTransmission();
}

// NTC Thermistor lookup table (idk if this is correct)
const uint16_t NTC_ADC_TABLE[] = {788, 684, 568, 457, 355, 271,
                                  204, 152, 114, 85,  64};

// INA219 Configuration (Address 0x40, A0/A1 tied to ground)
void setupINA219() {
  Wire.beginTransmission(0x40);
  Wire.write(0x00); // Config register
  Wire.write(0x39); // MSB: 32V Range, PG/8 (320mV Limit)
  Wire.write(0x9F); // LSB: 12-bit ADC, continuous mode
  Wire.endTransmission();
}

uint16_t readINA219Register(uint8_t reg) {
  Wire.beginTransmission(0x40);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return 0;
  }
  Wire.requestFrom(0x40, 2);
  uint16_t value = 0;
  if (Wire.available() >= 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    value = (msb << 8) | lsb;
  }
  return value;
}

uint16_t readINA219Current() {
  int16_t shuntRaw = (int16_t)readINA219Register(0x01);
  int16_t currentmA = shuntRaw / 10; // 10uV/LSB, 0.1R shunt -> /10 mA
  if (currentmA < 0)
    currentmA = 0;
  return (uint16_t)currentmA;
}

uint16_t readINA219Voltage() {
  uint16_t busRaw = readINA219Register(0x02);
  return (busRaw >> 3) * 4; // 4 mV/LSB
}

uint16_t readAnalogVoltage() {
  uint16_t adc = analogRead(VOLTAGE_PIN);
  // Divider 1/3, 5V ref -> V_bus = adc * 15000 / 1023 mV
  return (uint16_t)((adc * 15000UL) / 1023);
}

uint16_t getBusVoltage() {
  uint16_t v = readINA219Voltage();
  if (v == 0)
    v = readAnalogVoltage();
  return v;
}

uint8_t readNTCTemperature() {
  uint16_t adc = analogRead(NTC_PIN);
  if (adc >= NTC_ADC_TABLE[0])
    return 0;
  if (adc <= NTC_ADC_TABLE[10])
    return 100;
  for (uint8_t i = 0; i < 10; i++) {
    if (adc <= NTC_ADC_TABLE[i] && adc > NTC_ADC_TABLE[i + 1]) {
      uint16_t adc_high = NTC_ADC_TABLE[i];
      uint16_t adc_low = NTC_ADC_TABLE[i + 1];
      uint8_t temp_low = i * 10;
      uint32_t num = 10UL * (adc_high - adc);
      uint16_t den = adc_high - adc_low;
      return temp_low + (uint8_t)(num / den);
    }
  }
  return 25;
}

void updateEncoder() {
  uint16_t raw = 0;
  if (readAS5600Angle(&raw)) {
    currentRawAngle = raw;
    if (angleSeeded) {
      int16_t delta = (int16_t)raw - (int16_t)prevRawAngle;
      if (delta > 2048) {
        delta -= 4096; // wrapped backward past 0
      } else if (delta < -2048) {
        delta += 4096; // wrapped forward past 0
      }
      totalAngleRaw += delta;
    } else {
      prevRawAngle = raw;
      angleSeeded = true;
    }
    prevRawAngle = raw;
  }
}

void setupBus() {
  pinMode(RS485_DE, OUTPUT);
  digitalWrite(RS485_DE, LOW);

  pinMode(ADDR_A1, INPUT_PULLUP);
  pinMode(ADDR_A2, INPUT_PULLUP);
  pinMode(ADDR_A3, INPUT_PULLUP);
  delay(100); // Allow internal pull-ups to settle

  Serial.begin(9600);
  transfer.begin(Serial);

  // AS5600 + INA219 live on alternate I2C pins (PA1/PA2)
  Wire.swap(1);
  Wire.begin();
  Wire.setClock(400000); // supa fast
  configAS5600();
  setupINA219();

  // Seed encoder initial reading
  updateEncoder();

  // Get the address of this servo
  uint8_t bit0 = !digitalRead(ADDR_A1);
  uint8_t bit1 = !digitalRead(ADDR_A2);
  uint8_t bit2 = !digitalRead(ADDR_A3);
  hardwareID = (bit2 << 2) | (bit1 << 1) | bit0;
}

void updateBus() {
  // Check if there is an available transfer
  if (transfer.available()) {
    uint8_t recBytes = transfer.bytesRead;

    // Ignore telemetry responses sent by sibling servos (or transceiver echo)
    if (recBytes == sizeof(RespondPacket)) {
      return;
    }

    // Only process command packets from the master controller
    if (recBytes != sizeof(IncomingPacket)) {
      return;
    }

    transfer.rxObj(rxCommand);

    // Verify sync byte + checksum to check for data integrity
    uint8_t expected =
        calcChecksum((uint8_t *)&rxCommand, sizeof(IncomingPacket) - 1);
    if (rxCommand.magic != PACKET_MAGIC || rxCommand.checksum != expected) {
      stateError = true; // flash red to show corruption
      return;            // invalid -> ignore
    }

    // Valid command packet received from the master
    lastMasterPacketTime = millis();
    lastSeenTargetId = rxCommand.targetPcbId;
    dataLedOffTime = millis() + 25;

    if (rxCommand.targetPcbId == hardwareID) {
      lastPacketTime = millis();

      // Bus-requested homing
      static uint8_t lastPerformHome = 0;
      if (rxCommand.performHome && !lastPerformHome) {
        ctrlMode = MODE_HOMING;
        homed = false;
        calibrated = false;
      }
      lastPerformHome = rxCommand.performHome;
      servoCommand.performHome = rxCommand.performHome;

      // PWM jog mode
      servoCommand.jog = rxCommand.jog;

      // Target angle
      servoCommand.targetAngle = rxCommand.targetAngle;
      if (!rxCommand.jog && calibrated && countsPerRev != 0) {
        targetRaw =
            (int32_t)((int64_t)rxCommand.targetAngle * countsPerRev / 3600LL);
        ctrlMode = MODE_POSITION;
      }

      // Max current
      servoCommand.maxCurrent = rxCommand.maxCurrent;

      // RGB LED
      servoCommand.rgbColor[0] = rxCommand.rgbColor[0];
      servoCommand.rgbColor[1] = rxCommand.rgbColor[1];
      servoCommand.rgbColor[2] = rxCommand.rgbColor[2];

      // --- Telemetry ---
      txTelemetry.magic = PACKET_MAGIC;
      txTelemetry.targetPcbId = hardwareID;

      uint16_t angleTenths = (uint32_t)currentRawAngle * 3600UL / 4096UL;
      txTelemetry.angle = angleTenths;
      txTelemetry.totalAngle = totalAngleRaw;
      if (calibrated && countsPerRev != 0) {
        txTelemetry.realAngle =
            (int32_t)((int64_t)totalAngleRaw * 3600LL / countsPerRev);
      } else {
        txTelemetry.realAngle =
            (int32_t)((int64_t)totalAngleRaw * 3600LL / 4096LL);
      }

      txTelemetry.temp = readNTCTemperature();
      txTelemetry.current = readINA219Current();
      txTelemetry.voltage = getBusVoltage();
      txTelemetry.magnet = magnetPresent ? 1 : 0;
      txTelemetry.homed = homed ? 1 : 0;
      txTelemetry.servoFirmwareVersion = 13;
      txTelemetry.countsPerRev = millis() / 1000;
      txTelemetry.calibrated = calibrated ? 1 : 0;

      txTelemetry.checksum =
          calcChecksum((uint8_t *)&txTelemetry, sizeof(RespondPacket) - 1);

      transfer.txObj(txTelemetry);

      delay(2);
      digitalWrite(RS485_DE, HIGH);
      delayMicroseconds(50);

      transfer.sendData(sizeof(txTelemetry));
      Serial.flush();

      delay(2);
      digitalWrite(RS485_DE, LOW);
    }
  }
}

// Lightweight 8-bit XOR checksum
uint8_t calcChecksum(const uint8_t *data, uint8_t len) {
  uint8_t c = 0;
  for (uint8_t i = 0; i < len; i++)
    c ^= data[i];
  return c;
}