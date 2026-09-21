# revo

[![View PCB on KiCanvas](https://hack.club/pcb-badge)](https://kicanvas.org/?repo=https://github.com/ratmuds/revo/tree/main/PCB/revo-joint-encoder)
[![View PCB on KiCanvas](https://hack.club/pcb-badge)](https://kicanvas.org/?repo=https://github.com/ratmuds/revo/tree/main/PCB/revo-main-bottom)
[![View PCB on KiCanvas](https://hack.club/pcb-badge)](https://kicanvas.org/?repo=https://github.com/ratmuds/revo/tree/main/PCB/revo-main)
[![View PCB on KiCanvas](https://hack.club/pcb-badge)](https://kicanvas.org/?repo=https://github.com/ratmuds/revo/tree/main/PCB/revo-servo-hat)
[![View PCB on KiCanvas](https://hack.club/pcb-badge)](https://kicanvas.org/?repo=https://github.com/ratmuds/revo/tree/main/PCB/revo-servo)

a cool robot arm

<img width="1487" height="782" alt="image" src="https://github.com/user-attachments/assets/d1c303de-a520-447c-8deb-7a144a126fa4" />


# [![Watch the video](https://www.youtube.com/watch?v=T2Xa6mJVtoo)](https://www.youtube.com/watch?v=T2Xa6mJVtoo)

# What is it?

revo is a robot arm I made that is 6 DoF, and is equipped with 12 PCBs (5 unique designs), multiple cameras, many microcontrollers, and a lot of files

<img width="400" height="225" alt="20260920_110023_1 (2) (1)" src="https://github.com/user-attachments/assets/ce5229cd-cb60-42fb-a54a-bdfd74ca1c91" />

# Why?

I wanted to make a robot arm that punched above it's weight. The price is pretty similar to smaller robot arms on Amazon that may not include cameras, which would need to be purchased seperately. The way this is achieved by using cheap servos, servos that are 100% NOT made for this purpose, and adding most of the functionality of a smart servo back by using a TON of PCBs. It was a lot of soldering. I just wanted to make something that had more features for less money :)

<img width="400" height="225" alt="20260702_180830" src="https://github.com/user-attachments/assets/9b1d1fba-f3f2-43e5-b712-aca054bbc806" />

### Motors

Each motor has voltage, current, and a connector for a NTC thermistor for temperature monitoring. The MG996R servos each have a sensor PCB that plugs in and provides angle data via a AS5600 IC and another IC for a magnetic endstop since I had issues with physical endstops before. The MG996R needs a custom case to mount everything, which took me an incredible amount of time to get working due to super weird tolerances, especially the way I have it working requiring a seperate 3D printed extension for the shaft to mount a magnet. The code also has to track this magnet super fast and track how many full revolutions it makes, and calculates the correct real angle from that. It's also running LADRC instead of basic sweep or PID, which has helped a little with jittering and general inaccuracies.

Each MG996R servo has two JST-VH connectors and two JST-1.25mm connectors. They daisy chain 6V and a RS-485 bus for reliable data transfer. The daisy chaining helps with the wiring, and the differential signals help with noise resistance and the distance. Each servo compares a checksum and magic byte that is received to verify data integrity before loading it into structs and using the data. They have multiple LEDs to provide information such as errors, calibration status, data corruption, invalid PCB ID, code alive status, etc.

<img width="400" height="225" alt="20260907_163033" src="https://github.com/user-attachments/assets/a017e20e-25c8-4bfb-a000-0b54dd0aa2d4" />

### Mainboard

The mainboard has a RPi Pico for controlling, and a bunch of sensors for the DS5180 servo motors. The mainboard also has a two step power circuit that requires a logic signal from the Pico and the E-STOP to be depressed to allow the electricity to flow through. This is then routed to 3 seperate buck modules that regulate the voltage. There is a 6V module for the MG996Rs, and two 7.4V modules for the DS5180s. There also is two smaller modules for 12V and 3.3V.

<img width="400" height="222" alt="20260705_112805" src="https://github.com/user-attachments/assets/fbf79def-7233-41fd-b6b3-e325a6a809f9" />

### Control

There are multiple ways to control the robot arm, such as manually controlling the values in the dashboard, dragging IK in the dashboard, or the coolest way, VR. You can see it in action in the demo video above :)

<img width="448" height="210" alt="image" src="https://github.com/user-attachments/assets/deb475fa-b1bd-4878-b2d7-fd38e093a1e8" />

## Some images

# MORE IMAGES IN `/PCB`!!!!!!!!

<img width="671" height="224" alt="Screenshot 2026-09-20 174516" src="https://github.com/user-attachments/assets/c969aab0-12bd-467e-b1e3-4f70ca88bbfd" />
<img width="550" height="430" alt="Screenshot 2026-09-20 174107" src="https://github.com/user-attachments/assets/7d077cdc-5c1b-497f-bf9d-7912c1e889fb" />
<img width="382" height="516" alt="Screenshot 2026-09-20 174226" src="https://github.com/user-attachments/assets/375ac525-b4b6-4a89-acd2-24b143a949e9" />
<img width="678" height="242" alt="Screenshot 2026-09-20 174343" src="https://github.com/user-attachments/assets/edaec710-af87-4338-8faa-b0b207de1238" />


# MORE IMAGES IN `/PCB`!!!!!!!!

# Looking back

There are a lot of not great things with this arm. The mainboard is incredibly hard to assemble. The screws like to fall out. There are cables everywhere despite me trying to clean it up a bit. And it's inaccurate. But that's because the motors I'm using are literally like $5 each. I would recommend better motors if you want to make a robot arm, but this project was just to see if I could do it and pushing my limits in all fields like programming, electronics, and CAD/mechanical design.

# "Installation"

## Please do not replicate this robot arm.
It is a proof of concept that is not ready for real world use. There are no instructions for building it because of that reason. It is a fragile piece of robotics and not meant for any sort of practical usage or replication! If you really want to, it's not that difficult though if you look through the CAD :)

There is a lot of different files.

 - `firmware/dashboard`: The dashboard for controlling and viewing telemetry data. Use `pnpm i` to install, `pnpm run dev` to run.
 - `firmware/mainboard-firmware`: Please use the Arduino IDE and compile for your RPi Pico board.
 - `firmware/pc-code`: Use `uv run camera_server.py` to host the cameras (loads three) and `uv run main.py` to host the communication layer between the mainboard and the web dashboard.
 - `firmware/servo-firmware`: Please use PlatformIO in VSCode (or similar) and compile. You will need a UPDI programmer to upload the code to the MG996Rs containing ATtiny3216s. Note that the servos cannot output any serial so you will have to rely on LEDs if it's not communicating with the mainboard!

## VR

I used a Meta Quest 2 and used the Link app on my PC (GPU required) and you can go to `localhost:5173/VR` while hosting the dashboard to access the WebXR page.

## PCBs

The five PCB designs are in the `/PCB` folder. There are more images in that folder for reference. I ordered them and hand soldered them, which took a long time but I got faster as time went on.

## Bill of Materials (this is so so so long)

### Hardware & Components

Please don't actually build this project, but if you do ORDER SPARES!!!!!!

| Name | Type | Amount | Notes |
| --- | --- | --- | --- |
| 80KG High Torque Digital Servo (270°) | Servo Motor | 3 | 1/5 scale waterproof metal gear servos for base, shoulder, and elbow joints |
| MG996R Metal Gear Digital Servo | Servo Motor | 4 | 4.8V–6.0V high torque standard servos for wrist and gripper joints |
| 18T Round Disc Metal Servo Horn | Hardware | 2 | Round disc steering servo horn for 60KG/80KG/150KG servos |
| MG996R Metal Servo Horns (25T) | Hardware | 4 | Metal steering servo horns for MG996R servos |
| 6806-2RS Deep Groove Ball Bearings | Bearing | 2 | 30mm ID x 42mm OD x 7mm bore double sealed chrome steel bearings for joints |
| Radial Magnet for AS5600 | Magnet | 4 | Diametrically / radially magnetized disc magnets for AS5600 magnetic encoders |
| 6x2mm Neodymium Disc Magnets (N35) | Magnet | 1 pack | Permanent NdFeB round magnets for latching/accessories |
| M2.5 Heat-Set Brass Threaded Inserts | Fastener | 100 pcs | M2.5 x 3mm x 4mm knurled embed nuts for 3D printed components |
| M2.5 Screw Assortment | Fastener | 1 pack | Assorted lengths for robot arm structure and PCB mounting |
| M3 Low-Profile Socket Head Screws | Fastener | 1 pack | 304 stainless steel Allen hex thin/short head cap bolts |
| 180W Dell Power Supply AC Adapter | Power Supply | 1 | 19.5V 180W power brick for main system power |
| Dell 7.4x5.0mm to XT60 Adapter (XT-017) | Adapter | 1 | Converts Dell power brick 7.4x5.0mm barrel jack to XT60 plug |
| 10A Step-Down Buck Converter Module | Buck Converter Module | 2 | 4-32V to 1.2-32V adjustable CV/CC step-down regulator for servo/system power |
| MP1584EN 3A Buck Converter Module | Buck Converter Module | 2 | Ultra-compact 3A adjustable DC-DC step-down power module (Mini360 style) |
| Red Mushroom Emergency Stop Switch | Switch | 1 | 1NO 1NC DPST latching push-button E-STOP switch (660V 10A, plugs into J17) |
| Aptina AR0144 720P 60fps Global Shutter Camera | Camera | 1 | High-speed 170° fisheye USB camera module for tracking and vision |
| OV9726 1MP USB Camera Module | Camera | 4 | 720P CMOS 50° FOV USB cameras (used in camera_server.py) |
| 3010 Cooling Fan (12V) | Fan | 1 | 30x30x10mm 2-pin 12V DC cooling fan (connects to FAN PWR J24/J23) |
| WS2812B RGB LED Ring (12-Bit) | RGB LED Module | 2 | 5050 RGB LED ring with integrated WS2812 drivers (12 LEDs each) |
| 18AWG Tinned Copper Wire (5m) | Wiring | 5m | Flexible PVC tinned copper high-current power delivery cable |
| XT60 Male to Female Extension Cable | Wiring / Cable | 1 | 14AWG silicone wire extension cable (10cm) |
| JST 1.25mm 4-Pin Pre-Crimped Cables | Wiring / Connector | 10 pairs | Micro 4-pin male/female plugs with 100mm 26AWG wire for RS485 daisy chain |
| Assorted Hookup Wires | Wiring | 1 set | General length jumper and hookup wires |
| XT60E-M Screw-Mount Male Plug | Connector | 1 | Gold-plated panel/chassis mount XT60 connector (matches mainboard J21) |
| 2.54mm Pin Headers Kit | Connector | 30 pcs | Straight & right-angle male and female 2.54mm headers for PCBs |
| JST 1.25mm Horizontal Connector Kit | Connector Kit | 1 box | Horizontal sockets, plugs, and crimp pins for servo data bus |
| VH 3.96mm Connector Kit | Connector Kit | 1 box | VH 3.96mm housings and terminals for high-current power connectors (B2PS-VH) |
| PH 2.0mm Connector Kit | Connector Kit | 2 boxes | PH 2.0mm housings and crimp terminals for LiPo / sensor wiring |
| Terminal Crimping Pliers (SN-2549) | Tool | 1 | Crimping tool for JST 1.25mm, PH 2.0mm, VH 3.96mm, SM 2.54mm terminals |
| Raspberry Pi Pico | MCU Module | 1 | RP2040 microcontroller board for revo mainboard (A1) |
| INA219AIDR Current Sensor IC | Current Monitor IC | 6 | SOIC-8 I2C bidirectional current/power monitor ICs (spares/on-board) |
| HT7333 / HT7350 LDO Regulators | Voltage Regulator | 10-pack | SOT-89 250mA low-dropout regulators (both 3.3V and 5.0V) |
| NTC Thermistor 10k (MF52AT) | Thermistor | 4 (plus 20pc pack) | B=3950, 10kΩ @ 25°C thermal sensors for servo motor monitoring |

### PCB Components (SMD / THT)

| Name | Type | Amount | Notes |
| --- | --- | --- | --- |
| 0.1uF | Capacitor | 12 | `C_0805_2012Metric_Pad1.18x1.45mm_HandSolder`; revo-main: C7, C8, C9; revo-main-bottom: C5; revo-servo: C1, C3, C5, C7; revo-servo-hat: C7, C8, C9; revo-joint-encoder: C7 |
| 1000uF | Capacitor | 1 | `CP_Radial_D10.0mm_P5.00mm`; MPN: 16ZLH1000MEFC10X16; revo-main: C11 |
| 100uF | Capacitor | 1 | `CP_Elec_6.3x5.4`; revo-servo: C4 |
| 100uF | Capacitor | 1 | `CP_Radial_D6.3mm_P2.50mm`; MPN: 732-8707-1-ND; revo-main-bottom: C10 |
| 10uF | Capacitor | 4 | `C_0805_2012Metric_Pad1.18x1.45mm_HandSolder`; revo-main: C12, C13; revo-servo: C8, C9 |
| 470uF | Capacitor | 1 | `CP_Radial_D10.0mm_P5.00mm`; MPN: 35ZLH470MEFCT810X16; revo-main: C2 |
| 470uF | Capacitor | 3 | `CP_Radial_D10.0mm_P5.00mm`; MPN: 25ZLH470MEFC10X12.5; revo-main: C3, C4, C6 |
| 0.02R 2W | Resistor | 3 | `R_2512_6332Metric_Pad1.40x3.35mm_HandSolder`; MPN: CRA2512-FZ-R020ELF; revo-main: R1, R2, R3 |
| 0.1R 2W | Resistor | 1 | `R_2512_6332Metric_Pad1.40x3.35mm_HandSolder`; revo-servo: R1 |
| 1.5k | Resistor | 1 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; revo-main-bottom: R11 |
| 100R | Resistor | 1 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; revo-main: R22 |
| 10k | Resistor | 7 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; revo-main: R5, R6, R7, R23; revo-main-bottom: R10; revo-servo: R16, R19 |
| 120R | Resistor | 1 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; revo-main-bottom: R4 |
| 120R | Resistor | 1 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; *(DNP / Do Not Populate)*; revo-servo: R4 |
| 2.2K | Resistor | 1 | `R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal`; MPN: 13-MFR50SFTE52-2K2CT-ND; revo-main: R21 |
| 20k | Resistor | 1 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; revo-servo: R18 |
| 220R | Resistor | 4 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; revo-servo: R14, R20; revo-servo-hat: R14; revo-joint-encoder: R16 |
| 330R | Resistor | 4 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; revo-main: R20; revo-servo: R13; revo-servo-hat: R13; revo-joint-encoder: R15 |
| 4.7k | Resistor | 5 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; revo-main-bottom: R8, R9; revo-servo: R11, R12, R15 |
| 4.7k | Resistor | 2 | `R_0805_2012Metric_Pad1.20x1.40mm_HandSolder`; *(DNP / Do Not Populate)*; revo-joint-encoder: R13, R14 |
| NTC 10k | Thermistor | 1 | `R_Axial_DIN0204_L3.6mm_D1.6mm_P5.08mm_Horizontal`; revo-servo: R17 |
| SS34 | Diode | 2 | `D_SMA`; revo-main: D1; revo-servo: D1 |
| SS54 | Diode | 1 | `DO-214AC`; MPN: SS54; revo-main: D2 |
| LED | LED | 7 | `D_0805_2012Metric_Pad1.15x1.40mm_HandSolder`; revo-main: D5, D6; revo-servo: D3, D4, D5; revo-servo-hat: D4; revo-joint-encoder: D4 |
| WS2812B_5050 | RGB LED | 1 | `LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm`; revo-servo-hat: D1 |
| 2N7002 | MOSFET | 1 | `SOT-23`; revo-main: Q2 |
| AOD4185 | MOSFET | 1 | `TO-252-2`; revo-main: Q3 |
| BSS138 | MOSFET | 1 | `SOT-23`; revo-main: Q4 |
| ATtiny3216-S | MCU | 1 | `SOIC-20W_7.5x12.8mm_P1.27mm`; revo-servo: U1 |
| RaspberryPi_Pico | MCU Module | 1 | `RaspberryPi_Pico_Common_Unspecified`; revo-main-bottom: A1 |
| AS5600 | Magnetic Encoder | 2 | `SOIC8`; revo-servo-hat: U1; revo-joint-encoder: U1 |
| DRV5032ZEDBZR | Hall Sensor | 1 | `SOT95P237X112-3N`; revo-servo-hat: U2 |
| INA219AxD | Current Monitor IC | 4 | `SOIC-8_3.9x4.9mm_P1.27mm`; revo-main: U6, U9, U10; revo-servo: U3 |
| THVD1420D | RS-485 Transceiver | 2 | `SOIC-8_3.9x4.9mm_P1.27mm`; revo-main-bottom: U7; revo-servo: U2 |
| HT7333 | Voltage Regulator | 1 | `IC_HT7333`; revo-servo: U6 |
| HT7350 | Voltage Regulator | 1 | `IC_HT7333`; revo-main: U1 |
| Mini360 | Buck Converter Module | 2 | `Mini360_step-down`; revo-main-bottom: U2, U3 |
| 3V3 | Connector | 2 | `PinHeader_1x02_P2.54mm_Vertical`; revo-main: J28; revo-main-bottom: J27 |
| BUZZER | Connector | 2 | `PinHeader_1x01_P2.54mm_Vertical`; revo-main: J15; revo-main-bottom: J18 |
| Conn | Connector | 4 | `PinHeader_1x01_P2.54mm_Vertical`; revo-main: J34, J35; revo-main-bottom: J32, J36 |
| Conn | Connector | 2 | `PinHeader_1x03_P2.54mm_Vertical`; revo-main: J26; revo-main-bottom: J25 |
| Data In | Connector | 2 | `JST_1x04_P1.25mm_Locking_Horizontal_SMD`; revo-main-bottom: J2; revo-servo: J2 |
| Data Out | Connector | 1 | `JST_1x04_P1.25mm_Locking_Horizontal_SMD`; revo-servo: J3 |
| DS5180 | Connector | 3 | `PinHeader_1x03_P2.54mm_Vertical`; revo-main: J8, J9, J10 |
| E-STOP | Connector | 1 | `PinHeader_1x02_P2.54mm_Vertical`; revo-main: J17 |
| FAN PWR | Connector | 2 | `PinHeader_1x02_P2.54mm_Vertical`; revo-main: J24; revo-main-bottom: J23 |
| I2C | Connector | 2 | `PinHeader_1x02_P2.54mm_Vertical`; revo-main: J29; revo-main-bottom: J30 |
| JST_2mm_LiPo | Connector | 5 | `JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical`; revo-main: J4, J5, J6, J7, J20 |
| KF301-2P | Connector | 3 | `HANDSON_KF301-2P`; revo-main: J14, J16, J19 |
| KF301-2P | Connector | 1 | `KF7.62_2P`; revo-main: J13 |
| LED | Connector | 1 | `PinSocket_1x03_P2.54mm_Vertical`; revo-joint-encoder: J3 |
| Main Connector | Connector | 1 | `JST_1x04_P2.0mm_Horizontal_PTH`; revo-joint-encoder: J1 |
| Main Connector | Connector | 2 | `JST_1x04_P2.0mm_Vertical_PTH`; revo-main-bottom: J1, J3 |
| Motor | Connector | 1 | `PinSocket_1x03_P2.54mm_Vertical`; revo-servo: J4 |
| Power | Connector | 2 | `B2PS-VH`; revo-main: X1; revo-servo: X1 |
| Power Out | Connector | 1 | `B2PS-VH`; revo-servo: X2 |
| Programming | Connector | 2 | `PinSocket_1x03_P2.54mm_Vertical`; revo-servo: J1; revo-joint-encoder: J2 |
| RPi 5 SPI | Connector | 1 | `PinHeader_1x05_P2.54mm_Vertical`; revo-main-bottom: J11 |
| Sensor Board Connector | Connector | 2 | `PinHeader_1x06_P2.54mm_Horizontal`; revo-servo: J6; revo-servo-hat: J1 |
| SERVO CONN | Connector | 2 | `PinHeader_1x03_P2.54mm_Vertical`; revo-main: J12; revo-main-bottom: J22 |
| XT60-M | Connector | 1 | `AMASS_XT60-M`; revo-main: J21 |
| Home | Switch | 2 | `SW_Tactile_SPST_NO_Straight_CK_PTS636Sx25SMTRLFS`; revo-main: SW1; revo-servo: SW1 |
| Step | Switch | 1 | `SW_Tactile_SPST_NO_Straight_CK_PTS636Sx25SMTRLFS`; revo-servo: SW2 |
| 10A | Fuse | 1 | `Fuse_1808`; revo-main: F2 |
| 25A | Fuse | 1 | `Fuse_1808`; revo-main: F1 |
| CEM-1206S | Buzzer | 1 | `CUI_CEM-1206S`; revo-main: LS1 |
| 1.0mm | Test Point | 10 | `TestPoint-1.0mm`; revo-servo: TP1, TP2, TP3, TP4, TP5, TP6, TP7, TP8, TP9, TP10 |
| Jumper_2_Open | Jumper | 3 | `SolderJumper-2_P1.3mm_Open_TrianglePad1.0x1.5mm`; revo-servo: JP1, JP2, JP3 |
