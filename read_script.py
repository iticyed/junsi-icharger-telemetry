import hid
import struct
import time
import os

VENDOR_ID = 0x0483
PRODUCT_ID = 0x5751


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def parse_native_hid_packet(data_input):
    """Decodes the native little-endian Junsi HID status report."""
    data = bytes(data_input)
    if len(data) < 16:
        return None

    try:
        total_voltage = float(struct.unpack_from('<H', data, 14)[0]) / 1000.0
        current = float(struct.unpack_from('<h', data, 10)[0]) / 100.0

        raw_temp = struct.unpack_from('<H', data, 12)[0]
        if raw_temp < 2000:
            temp_c = float(raw_temp) / 10.0
        else:
            temp_c = float(raw_temp) / 400.0

        return {
            "Total_V": total_voltage,
            "Current_A": current,
            "Temp_C": temp_c,
            "Raw_Bytes": data
        }
    except Exception:
        return None


def print_cli_dashboard(telemetry):
    print("\033[H", end="")
    print("iCharger 406 Duo data")

    if telemetry['Total_V'] > 0.5:
        status_text = "live..."
    else:
        status_text = "waiting for packets / idle..."

    print(f"Status: {status_text}")
    print("-" * 55)

    print(f"voltage: {telemetry['Total_V']:6.3f} V")

    if telemetry['Current_A'] > 0.02:
        print(f"current: {telemetry['Current_A']:+6.2f} A  (charging)")
    elif telemetry['Current_A'] < -0.02:
        print(f"current: {telemetry['Current_A']:+6.2f} A  (discharging)")
    else:
        print(f"current:  0.00 A  (idle / finished)")

    print(f"temp: {telemetry['Temp_C']:6.1f} °C / Units")

    print("RAW HID BYTES (Offsets 00-15):")
    if telemetry['Raw_Bytes']:
        hex_string = " ".join(f"{b:02X}" for b in telemetry['Raw_Bytes'][:16])
        print(f"  {hex_string}")
    else:
        print("  No active bytes.")

    print("-" * 55)
    print("press ctrl+C to exit")


def main():
    try:
        device = hid.device()
        device.open(VENDOR_ID, PRODUCT_ID)
        device.set_nonblocking(1)

        clear_screen()
        print("connecting...")
        time.sleep(1)
        clear_screen()

        active_telemetry = {
            "Total_V": 0.0, "Current_A": 0.0, "Temp_C": 0.0, "Raw_Bytes": None
        }

        while True:
            data = device.read(64)

            if data:
                parsed = parse_native_hid_packet(data)
                if parsed and parsed["Total_V"] > 0.1:
                    active_telemetry = parsed

            print_cli_dashboard(active_telemetry)

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\ndisconnected")
        try:
            device.close()
        except:
            pass
    except Exception as e:
        print(f"\nConnection Error: {e}")


if __name__ == "__main__":
    main()
