# monitor.py - iCharger 406 DUO terminal monitor and controller.

# Shows live status for one channel (for now) while accepting typed commands:

#    start              starts charging on the selected channel
#    stop               stops and cancel any pending timer
#    limit <mA> <mV>    set current/voltage limits
#    timer <minutes>    start charging, auto-stop after N minutes
#    quit               disconnect and exit

# To run simply type <python monitor.py> in a terminal
# requires <pip install hidapi>


import sys
import threading
import time

from icharger_control import ICharger


class Monitor:
    REFRESH_SECONDS = 1.0

    def __init__(self, charger, channel):
        self.charger = charger
        self.channel = channel
        self.typing = threading.Event()
        self.running = True
        self.timer = None

    def render(self, status):
        sys.stdout.write("\033[2J\033[H")

        label = "CH1" if self.channel == 0 else "CH2"
        print(f"iCharger 406 DUO - {label}\n")

        if status is None:
            print(f"  status read failed: {self.charger.error}")
        else:
            print(f"  Status:   {status['run_status_name']}")
            print(f"  Voltage:  {status['voltage_v']:.3f} V")
            print(f"  Current:  {status['current_a']:.2f} A")
            print(f"  Capacity: {status['capacity_mah']} mAh")
            print(f"  Temp:     {status['temp_c']:.1f} C")

            if status["cells_mv"]:
                cells = "  ".join(f"{value}mV" for value in status["cells_mv"])
                print(f"  Cells:    {cells}")

            if status["run_error"]:
                print(f"  ERROR CODE: {status['run_error']}")

        if self.timer is not None:
            print("\n  [timer running - will auto-stop]")

        print(
            "\nCommands: start | stop | limit <mA> <mV> | "
            "timer <minutes> | quit"
        )

    def status_loop(self):
        while self.running:
            waited = 0.0

            while waited < self.REFRESH_SECONDS:
                if self.typing.is_set():
                    break
                time.sleep(0.1)
                waited += 0.1

            if self.typing.is_set():
                continue

            self.render(self.charger.read_status(self.channel))

    def cancel_timer(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def timer_stop(self):
        self.timer = None
        self.charger.stop(self.channel)

    def handle_command(self, command):
        parts = command.split()
        if not parts:
            return True

        operation = parts[0].lower()

        if operation in ("quit", "exit"):
            return False

        if operation == "start":
            self.cancel_timer()
            ok = self.charger.start(self.channel)
            print("Started." if ok else f"Failed to start: {self.charger.error}")

        elif operation == "stop":
            self.cancel_timer()
            ok = self.charger.stop(self.channel)
            print("Stopped." if ok else f"Failed to stop: {self.charger.error}")

        elif operation == "limit" and len(parts) == 3:
            try:
                current_ma, voltage_mv = int(parts[1]), int(parts[2])
            except ValueError:
                print("Usage: limit <current_mA> <voltage_mV>")
                return True

            ok, current_ma, voltage_mv = self.charger.set_limits(
                self.channel, current_ma, voltage_mv
            )

            if ok:
                print(
                    f"Limits set: {current_ma}mA / {voltage_mv}mV "
                    "(clamped to charger max if needed)"
                )
            else:
                print(f"Failed to set limits: {self.charger.error}")

        elif operation == "timer" and len(parts) == 2:
            try:
                minutes = float(parts[1])
            except ValueError:
                print("Usage: timer <minutes>")
                return True

            self.cancel_timer()

            if not self.charger.start(self.channel):
                print(f"Failed to start: {self.charger.error}")
                return True

            self.timer = threading.Timer(minutes * 60, self.timer_stop)
            self.timer.daemon = True
            self.timer.start()
            print(f"Started, will auto-stop in {minutes} minutes.")

        else:
            print(
                "Unknown command. Options: start | stop | "
                "limit <mA> <mV> | timer <minutes> | quit"
            )

        return True

    def run(self):
        thread = threading.Thread(target=self.status_loop, daemon=True)
        thread.start()

        try:
            while self.running:
                self.typing.set()
                try:
                    command = input("\n> ").strip()
                finally:
                    self.typing.clear()

                if not self.handle_command(command):
                    break

        except KeyboardInterrupt:
            print("\nInterrupted.")
        finally:
            self.running = False
            self.cancel_timer()


def main():
    charger = ICharger()

    print("Connecting to iCharger 406 DUO...")
    if not charger.connect():
        print(f"Could not connect: {charger.error}")
        print(
            "Check the USB cable and that USB mode is selected on the "
            "charger (System Menu -> Communication -> USB Port)."
        )
        return

    try:
        info = charger.read_device_info()
        if info:
            print(
                f"Connected. Device ID {info['device_id']}, "
                f"SW v{info['sw_version']}, HW v{info['hw_version']}"
            )

        choice = input("Which channel? [1/2]: ").strip()
        channel = 1 if choice == "2" else 0

        Monitor(charger, channel).run()
    finally:
        charger.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
