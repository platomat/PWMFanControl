# PWMFanControl
Simple script to control a PWM fan on a Raspberry Pi based on CPU temperature.

This is a fork of: https://github.com/mklements/PWMFanControl

## EDIT
This scripts writes permanently a ```fan_status.json``` file that looks like this:
```
{"temp_current": 54.5, "temp_min": 45, "temp_max": 80, "fan_speed_current": 27, "fan_speed_min": 0, "fan_speed_max": 100}
```
So this data could be used to read it and to display some of its data in node-red or somewhere else

