# Created by: Michael Klements
# For 40mm 5V PWM Fan Control On A Raspberry Pi
# Sets fan speed proportional to CPU temperature - best for good quality fans
# Works well with a Pi Desktop Case with OLED Stats Display
# Installation & Setup Instructions - https://www.the-diy-life.com/connecting-a-pwm-fan-to-a-raspberry-pi/

# EDITED BY: platomat.com
# this scripts writes permanently a fan_status.json file that looks like this:
# {"temp_current": 54.5, "temp_min": 45, "temp_max": 80, "fan_speed_current": 27, "fan_speed_min": 0, "fan_speed_max": 100}

# so this data could be used to read it and to display some of its data in node-red or somewhere else


import RPi.GPIO as IO
import time
import subprocess
import json
import os

# --- Fan setup ---
pwmGpio = 14            # GPIO number
pwmFrequenzy = 25       # Hz
updateInterval = 3      # seconds

IO.setwarnings(False)
IO.setmode(IO.BCM)
IO.setup(pwmGpio, IO.OUT)
fan = IO.PWM(pwmGpio, pwmFrequenzy)
fan.start(0)

# --- Config ---
minTemp = 48
maxTemp = 80
minSpeed = 0
maxSpeed = 100

# JSON output file
status_file = "fan_status.json"

def get_temp():
    """Read CPU temperature in °C as float"""
    output = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True)
    temp_str = output.stdout.decode()
    try:
        return float(temp_str.split('=')[1].split('\'')[0])
    except (IndexError, ValueError):
        raise RuntimeError('Could not get temperature')

def renormalize(n, range1, range2):
    """Scale number from range1 to range2"""
    delta1 = range1[1] - range1[0]
    delta2 = range2[1] - range2[0]
    return (delta2 * (n - range1[0]) / delta1) + range2[0]

while True:
    # read temp and clamp
    temp = get_temp()
    if temp < minTemp:
        temp = minTemp
    elif temp > maxTemp:
        temp = maxTemp

    # map to fan speed
    speed = int(renormalize(temp, [minTemp, maxTemp], [minSpeed, maxSpeed]))
    fan.ChangeDutyCycle(speed)

    # build status dict
    status = {
        "temp_current": round(temp, 1),
        "temp_min": minTemp,
        "temp_max": maxTemp,
        "fan_speed_current": speed,
        "fan_speed_min": minSpeed,
        "fan_speed_max": maxSpeed
    }

    # write to file (atomic update)
    tmp_file = status_file + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(status, f)
    os.replace(tmp_file, status_file)

    time.sleep(updateInterval)
