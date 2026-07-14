import time
import struct
import json
import spidev

# Packet synchronization magics
MAGIC_TX = 0x5245564F  # 'REVO' (RPi -> Pico)
MAGIC_RX = 0x53544154  # 'STAT' (Pico -> RPi)

# SPI setup
# Bus 0, Device 0 (CE0 / GPIO8)
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000  # 1 MHz to ensure signal integrity
spi.mode = 0                # SPI Mode 0

# Packing/Unpacking format strings (< indicates little endian, no alignment padding)
# SpiCommandPacket format: magic(I), 3 x servo(H H B B B B), padding(20s)
# Each servo block: targetAngle(H), maxCurrent(H), rgb_r(B), rgb_g(B), rgb_b(B), performHome(B)
CMD_FORMAT = "<I" + "HHBBBB" * 3 + "20s"

# SpiStatusPacket format: magic(I), counter(I), 3 x JointData(B H B H H B B B), padding(7s)
# Each JointData: online(B), angle(H), temp(B), current(H), voltage(H), magnet(B), homed(B), fw(B)
STATUS_FORMAT = "<II" + "BHBHHBBB" * 3 + "7s"

def loop_servos():
    print("==================================================")
    print("Raspberry Pi 5 Revo SPI Client Online")
    print("Sending command angles & monitoring joints...")
    print("==================================================")
    
    start_time = time.time()
    
    try:
        while True:
            # 1. Generate dynamic commands (e.g., sine wave oscillation between 0 and 180 degrees)
            elapsed = time.time() - start_time
            # Oscillate target angle over time
            angle_s0 = int(90 + 90 * math_sin_wave(elapsed, period=4.0))
            angle_s1 = int(90 + 90 * math_sin_wave(elapsed + 1.3, period=4.0))
            angle_s2 = int(90 + 90 * math_sin_wave(elapsed + 2.6, period=4.0))
            
            # Pack SpiCommandPacket (48 bytes)
            # magic, 
            # servo0 (angle, currentLimit, R, G, B, home)
            # servo1 (angle, currentLimit, R, G, B, home)
            # servo2 (angle, currentLimit, R, G, B, home)
            # padding
            cmd_data = struct.pack(
                CMD_FORMAT,
                MAGIC_TX,
                # Servo 0
                angle_s0, 2000, 100 if angle_s0 > 90 else 0, 0, 100 if angle_s0 <= 90 else 0, 0,
                # Servo 1
                angle_s1, 2000, 100 if angle_s1 > 90 else 0, 0, 100 if angle_s1 <= 90 else 0, 0,
                # Servo 2
                angle_s2, 2000, 100 if angle_s2 > 90 else 0, 0, 100 if angle_s2 <= 90 else 0, 0,
                b'\x00' * 20
            )
            
            # 2. Perform full-duplex SPI transfer (transfers 48 bytes, receives 48 bytes)
            rx_raw = spi.xfer2(list(cmd_data))
            
            # 3. Unpack SpiStatusPacket
            rx_bytes = bytes(rx_raw)
            unpacked = struct.unpack(STATUS_FORMAT, rx_bytes)
            
            magic_rx = unpacked[0]
            counter_rx = unpacked[1]
            
            # Check validation magic
            if magic_rx == MAGIC_RX:
                # Reconstruct joint statuses
                joints = []
                idx = 2
                for i in range(3):
                    online = unpacked[idx]
                    raw_angle = unpacked[idx + 1]
                    temp = unpacked[idx + 2]
                    current = unpacked[idx + 3]
                    voltage = unpacked[idx + 4]
                    magnet = unpacked[idx + 5]
                    homed = unpacked[idx + 6]
                    fw_version = unpacked[idx + 7]
                    
                    idx += 8
                    
                    if online:
                        # Convert 12-bit raw angle to degrees
                        angle_deg = round((raw_angle * 360.0) / 4096.0, 2)
                        joints.append({
                            "id": i,
                            "status": "online",
                            "angle_deg": angle_deg,
                            "raw_angle": raw_angle,
                            "temperature_c": temp,
                            "current_ma": current,
                            "voltage_v": round(voltage / 1000.0, 3),
                            "magnet_detected": bool(magnet),
                            "homed": bool(homed),
                            "fw_version": fw_version
                        })
                    else:
                        joints.append({
                            "id": i,
                            "status": "offline"
                        })
                
                # Print response as beautiful JSON
                output = {
                    "status": "success",
                    "pico_counter": counter_rx,
                    "target_angles": [angle_s0, angle_s1, angle_s2],
                    "joints": joints
                }
                print(json.dumps(output, indent=2))
            else:
                print(json.dumps({
                    "status": "error",
                    "message": f"Bad magic received: {hex(magic_rx)}"
                }, indent=2))
                
            print("-" * 50)
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\nExiting Revo SPI Client.")
    finally:
        spi.close()

def math_sin_wave(elapsed, period=4.0):
    import math
    return math.sin((2 * math.pi / period) * elapsed)

if __name__ == "__main__":
    loop_servos()
