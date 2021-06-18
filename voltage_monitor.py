#!/usr/bin/python
# Read voltage from TI ADS1015, and report it to MQTT broker
# AMV 2020/09, modified from
# http://www.pibits.net/code/tmp102-sensor-and-raspberry-pi-python-example.php

import time
import smbus
import paho.mqtt.publish as publish

# I2C Config
i2c_ch = 1
i2c_address = 0x49

# MQTT Config
mqtt_broker = "mqtt"
mqtt_port = 1883
mqtt_topic = "network_telemetry/lab/voltage"

# Home Assistant auto-discovery
mqtt_discovery_topic = "homeassistant/sensor/dc_rail_voltage/config"
mqtt_discovery_payload = '{"device_class": "voltage", "name": "DC Rail Voltage", "unique_id": "dc_rail_voltage", "state_topic": "network_telemetry/lab/voltage"}'
ha_discovery = True

# Voltage Divider Configuration
## Nominal +12VDC current divided down to +2.164VDC for ADC measurement
## R1 = 10k, R2 = 2.2k
div_ratio = 5.545

# ADS1015 Register addresses
reg_sample = 0x00
reg_config = 0x01
reg_threshold_low = 0x10
reg_threshold_high = 0x11

# ADS1015 Config register bitmasks (MSB)
reg_os        = 0b10000000
reg_mux       = 0b01110000
reg_pga       = 0b00001110
reg_mode      = 0b00000001
# ADS1015 Config register bitmasks (LSB)
reg_dr        = 0b11100000
reg_comp_mode = 0b00010000
reg_comp_pol  = 0b00001000
reg_comp_lat  = 0b00000100
reg_comp_que  = 0b00000011

# Calculate the 2's complement of a number
def twos_comp(val, bits):
    if (val & (1 << (bits - 1))) != 0:
        val = val - (1 << bits)
    return val

# Read voltage conversion from ADS1015
def read_v():

    # Read conversion registers
    # Value is left-justified 12-bit
    val = bus.read_i2c_block_data(i2c_address, reg_sample, 2)
#    print("Conversion Register Value:", val)
    v = (val[0] << 4) | (val[1] >> 4)
#    print("16-bit conversion:", v)

    # Convert to 2s complement 
    v = twos_comp(v, 12)

    # Convert registers value to volage
    # LSB == 1mV when PGA == 0b010 (default)
    # LSB == 2mV when PGA == 0b001 (+-4.096V)
    v = v * 0.002

    # measured voltage x divider ratio to get original voltage

    return (v * div_ratio)

#MQTT Publish
def mqtt_pub(topic, message):
    publish.single(topic, payload=message, hostname=mqtt_broker, port=mqtt_port)

# Initialize I2C (SMBus)
bus = smbus.SMBus(i2c_ch)

# Read the CONFIG register (2 bytes)
val = bus.read_i2c_block_data(i2c_address, reg_config, 2)
print("Old CONFIG:", val)

# Set configuation, high-byte:
## MODE 0 - continuous conversion
## MUX 4 - sample A0 relative to GND
## PGA 2 - FSR +- 4.096V
val[0] = (reg_mode & 0) | (reg_mux & (0b100 << 4)) | (reg_pga & (0b001 << 1))
# Set configuration, low-byte:
## DR 4 - 1600 SPS
## COMP_MODE 0 -Normal
## COMP_POL 0 - Normal
## COMP_LAT 0 - Normal
## COMP_QUE 3 - Normal
val[1] = (reg_dr & (4 << 5)) | (reg_comp_que & 3)

# Write changes back to CONFIG
bus.write_i2c_block_data(i2c_address, reg_config, val)

# Read CONFIG to verify that we changed it
val = bus.read_i2c_block_data(i2c_address, reg_config, 2)
print("New CONFIG:", val)

# Send auto-configuration topic to Home Assistant
if ha_discovery:
    mqtt_pub(mqtt_discovery_topic, mqtt_discovery_payload)

# Publish volage every minute
while True:
    voltage = read_v()
#    print(round(voltage, 3), "V")
    mqtt_pub(mqtt_topic, round(voltage, 3))
    time.sleep(60)

