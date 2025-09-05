# Created by: Michael Klements
# For 40mm 5V PWM Fan Control On A Raspberry Pi
# Sets fan speed in stepped increments - better for low quality fans
# Works well with a Pi Desktop Case with OLED Stats Display
# Installation & Setup Instructions - https://www.the-diy-life.com/connecting-a-pwm-fan-to-a-raspberry-pi/

# EDITED BY: platomat.com
# this scripts writes permanently a fan_status.json file that looks like this:
# {"temp_current": 54.5, "temp_min": 45, "temp_max": 80, "fan_speed_current": 27, "fan_speed_min": 0, "fan_speed_max": 100}
# also the steps to run the fan are modified


import RPi.GPIO as IO
import time
import subprocess
import json
import os

# -------- Fan / timing --------
pwmGpio = 14           # BCM pin for PWM
pwmFrequenzy = 25      # Hz
updateInterval = 3     # seconds

IO.setwarnings(False)
IO.setmode(IO.BCM)
IO.setup(pwmGpio, IO.OUT)
fan = IO.PWM(pwmGpio, pwmFrequenzy)
fan.start(0)

# -------- Dynamic config --------
minTemp   = 40.0        # °C: start of control range
maxTemp   = 70.0        # °C: full speed at/above this
minSpeed  = 0           # % duty (lower clamp)
maxSpeed  = 100         # % duty (upper clamp)

MIN_NONZERO_DUTY = 20   # Start non-zero steps at MIN_NONZERO_DUTY
NUM_STEPS = 6           # number of steps between min..max (e.g. 4 -> 5 duty levels incl. 0%)
H_RATIO   = 0.2         # hysteresis as fraction of one temperature step (e.g. 0.2 = 20%)

# JSON file next to this script (cron-safe)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
status_file = os.path.join(BASE_DIR, "fan_status.json")

def get_temp():
    """Read CPU temperature in °C as float."""
    out = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True)
    s = out.stdout.decode()
    try:
        return float(s.split("=")[1].split("'")[0])
    except (IndexError, ValueError):
        raise RuntimeError("Could not get temperature")

def build_dynamic_tables(tmin, tmax, dmin, dmax, nsteps):
    if nsteps < 1 or tmax <= tmin:
        raise ValueError("Invalid min/max or steps")
    seg = (tmax - tmin) / nsteps
    thresholds = [tmin + i * seg for i in range(nsteps)] + [tmax]


    # duties: index 0 stays 0, indices 1..nsteps ramp from MIN_NONZERO_DUTY..100
    duties = [0] + [
        int(round(MIN_NONZERO_DUTY + i * (dmax - MIN_NONZERO_DUTY) / (nsteps - 1)))
        for i in range(nsteps)
    ]
    return thresholds, duties, seg

# Precompute dynamic tables
THR, DUTY, SEG = build_dynamic_tables(minTemp, maxTemp, minSpeed, maxSpeed, NUM_STEPS)
HYST = H_RATIO * SEG  # hysteresis in °C based on segment width

def pick_duty(temp, last_duty):
    """
    Step-based selection with hysteresis:
    - Step up immediately when temp crosses up into a higher segment.
    - Step down only when temp falls below the upper bound of the *current* segment minus HYST.
    Mapping rule:
      temp in [THR[i], THR[i+1]) -> duty DUTY[i]
      temp >= THR[-1]            -> duty DUTY[-1]
      temp < THR[0]              -> duty DUTY[0]
    """
    # Determine current index (no hysteresis)
    if temp < THR[0]:
        target = DUTY[0]
        idx = 0
    elif temp >= THR[-1]:
        target = DUTY[-1]
        idx = len(DUTY) - 1
    else:
        idx = next(i for i in range(len(THR) - 1) if THR[i] <= temp < THR[i+1])
        target = DUTY[idx]

    if last_duty is None or HYST <= 0:
        return target

    # If stepping down (target < last), enforce hysteresis
    if target < last_duty:
        # Find index of last_duty
        try:
            last_idx = DUTY.index(last_duty)
        except ValueError:
            return target  # unknown last -> just accept target

        # Upper bound of the current (higher) segment is THR[last_idx] if last_idx > 0,
        # else nothing to hold on to.
        if last_idx > 0:
            upper_of_lower_segment = THR[last_idx]  # boundary to step down across
            if temp > (upper_of_lower_segment - HYST):
                return last_duty  # hold until clearly below with hysteresis
    return target

last_duty = None

while True:
    t = get_temp()
    # clamp just for status display (control already bounded by thresholds)
    t_clamped = max(min(t, maxTemp), minTemp)

    duty = pick_duty(t, last_duty)
    fan.ChangeDutyCycle(duty)
    last_duty = duty

    # Persist status (atomic)
    status = {
        "temp_current": round(t, 1),
        "temp_min": minTemp,
        "temp_max": maxTemp,
        "fan_speed_current": duty,
        "fan_speed_min": minSpeed,
        "fan_speed_max": maxSpeed
    }
    tmp = status_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status, f)
    os.replace(tmp, status_file)

    time.sleep(updateInterval)
