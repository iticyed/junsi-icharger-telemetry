## Junsi iCharger 406/4010 DUO Telemetry and Control System

A Python-based control and monitoring system for the Junsi iCharger 406/4010 DUO, designed to automate hybrid battery charging and testing workflows through USB HID/Modbus communication.

The project replaces repetitive manual charger operation with a programmable interface for starting and stopping charging operations, configuring charge limits, and monitoring battery telemetry in real time.

Dependencies:
```
pip install hidapi
```
Windows users requiring terminal styling windows or non-standard terminals may need to install the windows curses translation helper:

```
pip install windows-curses
```

NOT FUNCTIONAL: Currently crashes with index out of bounds error. 

⚠️ WARNING ⚠️
The memory slot used is hard-coded (for now).

icharger_control.py:
```
def start(self, channel, operation=None, memory_slot = 3):
```
Configure your NiMH preset slot using the charger's physical wheel interface. Note its list index placement (the first preset index is 0, the second is 1, the third is 2, etc.). Ensure your code's memory_slot targets this selection correctly.

#### Project Motivation
Hybrid battery testing can involve repeatedly starting charging cycles, monitoring measurements, recording results, and stopping equipment manually.

This project explores how software automation can replace that repetitive workflow with a programmable interface to the charger.

The broader goal is to connect hardware control, software engineering, data collection, and battery analysis into a single practical system.



