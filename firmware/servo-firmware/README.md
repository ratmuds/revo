# revo servo firmware

this is the servo firmware for revo, (the PCBs that go on the MG996Rs)

please use PlatformIO to compile, and use the left headers to plug in either a RPi Pico or dedicated UPDI programmer to upload the code. The PCB has the resistor to convert UPDI to the single wire programming protocol ATtinys use or something yeah

the `constants.h` file has some useful constants to edit, and some motor mappings that can adjust the per motor configs

on boot the code will use the solder jumpers to determine PCB ID! please solder them and don't duplicate values!!!!!!!!!!!!!!!!!!