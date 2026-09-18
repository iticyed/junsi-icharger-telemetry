#control.py - iCharger 406 DUO USB HID Modbus library.

# Provides a small object-oriented interface to the charger. In the main
# entry point, create an ICharger instance, connect it, then use its
# methods to read and control the charger.

# Protocol reference: iCharger MODBUS Protocol V2.1 (Junsi).
# Framing verified against petrochen/icharger-python (tested on a 308 DUO;
# same protocol family as the 406 DUO).


import hid
import threading


class ICharger:
 # USB HID device identifiers and protocol constants
    VENDOR_ID = 0x0483
    PRODUCT_ID = 0x5751
    HID_PACKET_SIZE = 64
    HID_FRAME_TYPE = 0x30

    ADDR_DEVICE_INFO = 0x0000   # device info registers
    ADDR_CHANNEL_1 = 0x0100     # Channel 1 data
    ADDR_CHANNEL_2 = 0x0200     # Channel 2 data 
    ADDR_CONTROL = 0x8000       # control registers

# control register offsets (from ADDR_CONTROL)
    CTRL_OPERATION = 0
    CTRL_MEMORY = 1
    CTRL_CHANNEL = 2
    CTRL_ORDER_LOCK = 3
    CTRL_ORDER = 4
    CTRL_LIMIT_CURRENT = 5
    CTRL_LIMIT_VOLTAGE = 6

# the iCharger Modbus protocol requires a special unlock value before sending an order
# otherwise the command is ignored.
    ORDER_UNLOCK = 0x55AA
    ORDER_STOP = 0
    ORDER_RUN = 1
    ORDER_MODIFY = 2

# charger operation modes (for start command)
    OP_CHARGE = 0
    OP_STORAGE = 1
    OP_DISCHARGE = 2
    OP_CYCLE = 3
    OP_BALANCE = 4

    MAX_CURRENT_MA = 40000
    MAX_VOLTAGE_MV = 30000

    RUN_STATUS_NAMES = {
        0: "STOP", 1: "WAIT_START", 2: "CHARGE_CC", 3: "CHARGE_CV",
        4: "CHG_CV_WAITING", 5: "DISCHARGE_CC", 6: "DISCHARGE_CV",
        7: "CHECK", 8: "TRICKLE", 9: "REDUCE_CURRENT", 10: "CHG_CV_FINISHED",
        11: "STOP_ERROR", 12: "DISCHARGE_CV_STAGE", 13: "PROTECT",
        14: "ERROR_STATE", 40: "BALANCE_START", 41: "BALANCE_CHECK",
        42: "BALANCE_OK", 43: "MEASURE_IR",
    }

    def __init__(self):
        self.device = None
        self.error = ""
        self.lock = threading.Lock()

    @property
    def connected(self):
        return self.device is not None

    def connect(self):
        # open the USB HID connection. returns True on success
        try:
            self.device = hid.device()
            self.device.open(self.VENDOR_ID, self.PRODUCT_ID)
            self.device.set_nonblocking(False)
            self.error = ""
            return True
        except Exception as e:
            self.device = None
            self.error = str(e)
            return False

    def disconnect(self):
        if self.device is None:
            return

        with self.lock:
            try:
                self.device.close()
            except Exception:
                pass
            finally:
                self.device = None

    def _transact(self, function_code, payload):
        # send one Modbus-HID request and return the response PDU
        if not self.connected:
            self.error = "Not connected"
            return None

        with self.lock:
            pdu = bytes([function_code]) + payload
            adu_length = len(pdu) + 2
            packet = bytes([0x00, adu_length, self.HID_FRAME_TYPE]) + pdu
            packet = packet.ljust(65, b"\x00")

            try:
                self.device.write(list(packet))
                response = self.device.read(
                    self.HID_PACKET_SIZE,
                    timeout_ms=1000,
                )
            except Exception as e:
                self.error = str(e)
                return None

            if not response:
                self.error = "Timeout waiting for response"
                return None

            response = bytes(response)

            if response[1] != self.HID_FRAME_TYPE:
                self.error = f"Unexpected frame type 0x{response[1]:02X}"
                return None

            data = response[2:response[0]]

            if data and data[0] & 0x80:
                exception = data[1] if len(data) > 1 else 0
                self.error = f"Modbus exception, code {exception}"
                return None

            return data

    def read_input_regs(self, address, count):
        # Function code 0x04 - read-only registers
        payload = bytes([
            address >> 8, address & 0xFF,
            count >> 8, count & 0xFF,
        ])
        data = self._transact(0x04, payload)

        if data is None:
            return None

        raw = data[2:2 + data[1]]
        return [(raw[i] << 8) | raw[i + 1] for i in range(0, len(raw), 2)]

    def read_holding_regs(self, address, count):
        # Function code 0x03 - read/write registers
        payload = bytes([
            address >> 8, address & 0xFF,
            count >> 8, count & 0xFF,
        ])
        data = self._transact(0x03, payload)

        if data is None:
            return None

        raw = data[2:2 + data[1]]
        return [(raw[i] << 8) | raw[i + 1] for i in range(0, len(raw), 2)]

    def write_regs(self, address, values):
        # Function code 0x10 - write consecutive registers
        count = len(values)
        payload = bytes([
            address >> 8, address & 0xFF,
            count >> 8, count & 0xFF,
            count * 2,
        ])

        for value in values:
            payload += bytes([value >> 8, value & 0xFF])

        return self._transact(0x10, payload) is not None

    @staticmethod
    def _signed16(value):
        return value - 0x10000 if value >= 0x8000 else value

    @staticmethod
    def _signed32(value):
        return value - 0x100000000 if value >= 0x80000000 else value

    def read_device_info(self):
        regs = self.read_input_regs(self.ADDR_DEVICE_INFO, 9)
        if regs is None:
            return None

        return {
            "device_id": regs[0],
            "sw_version": regs[7],
            "hw_version": regs[8],
        }

    def read_status(self, channel):
        # Read live status for channel 0 or 1
        if channel == 0:
            base = self.ADDR_CHANNEL_1
        elif channel == 1:
            base = self.ADDR_CHANNEL_2
        else:
            raise ValueError("Invalid channel. Must be 0 or 1.")

        regs = self.read_input_regs(base, 30)
        if regs is None:
            return None

        current_a = self._signed16(regs[4]) / 100.0
        voltage_v = regs[6] / 1000.0
        capacity_mah = self._signed32((regs[7] << 16) | regs[8])
        temp_c = self._signed16(regs[9]) / 10.0
        cells = [cell for cell in regs[11:19] if 0 < cell < 5000]

        tail = self.read_input_regs(base + 55, 3)
        run_status = tail[0] if tail else None
        run_error = tail[1] if tail else None

        return {
            "voltage_v": voltage_v,
            "current_a": current_a,
            "capacity_mah": capacity_mah,
            "temp_c": temp_c,
            "cells_mv": cells,
            "run_status": run_status,
            "run_status_name": self.RUN_STATUS_NAMES.get(
                run_status, f"UNKNOWN({run_status})"
            ),
            "run_error": run_error,
        }

    def _current_memory_slot(self):
        regs = self.read_holding_regs(self.ADDR_CONTROL, 2)
        return regs[self.CTRL_MEMORY] if regs else 0

    def start(self, channel, operation=None, memory_slot = 3):
        # Start an operation using the currently SPECIFIED memory preset
        if operation is None:
            operation = self.OP_CHARGE

        values = [operation, memory_slot, channel, self.ORDER_UNLOCK, self.ORDER_RUN]
        return self.write_regs(self.ADDR_CONTROL, values)

    def stop(self, channel):
        # Stop the operation on the specified channel
        if not self.write_regs(self.ADDR_CONTROL + self.CTRL_CHANNEL, [channel]):
            return False

        return self.write_regs(
            self.ADDR_CONTROL + self.CTRL_ORDER_LOCK,
            [self.ORDER_UNLOCK, self.ORDER_STOP],
        )

    def set_limits(self, channel, current_ma, voltage_mv):
        # Set current/voltage limits, clamped to software safety limits
        current_ma = max(0, min(current_ma, self.MAX_CURRENT_MA))
        voltage_mv = max(0, min(voltage_mv, self.MAX_VOLTAGE_MV))

        values = [
            channel,
            self.ORDER_UNLOCK,
            self.ORDER_MODIFY,
            current_ma,
            voltage_mv,
        ]

        ok = self.write_regs(
            self.ADDR_CONTROL + self.CTRL_CHANNEL,
            values,
        )
        return ok, current_ma, voltage_mv
