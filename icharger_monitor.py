# monitor.py - iCharger 406 DUO terminal monitor and controller.

# Shows live status for one channel (for now) while accepting typed commands:

#    start              starts charging on the selected channel
#    stop               stops and cancel any pending timer
#    limit <mA> <mV>    set current/voltage limits
#    timer <minutes>    start charging, auto-stop after N minutes
#    quit               disconnect and exit

# To run simply type <python monitor.py> in a terminal
# requires <pip install hidapi>


import curses
import time

from icharger_control import ICharger


def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)   
    stdscr.timeout(100)     
    charger = ICharger()
    
    stdscr.addstr(0, 0, "Connecting to iCharger 406 DUO...")
    stdscr.refresh()

    stdscr.addstr("Connecting to iCharger 406 DUO...")
    stdscr.refresh()
    
    if not charger.connect():
        stdscr.addstr(2, 0, f"Could not connect: {charger.error}")
        stdscr.addstr(4, 0, "Press any key to exit.")
        stdscr.nodelay(False)
        stdscr.getch()
        return

    stdscr.clear()
    stdscr.addstr(0, 0, "Which channel? [1 or 2]: ")
    stdscr.refresh()
    stdscr.nodelay(False)
    
    choice = stdscr.getch()
    channel = 1 if choice == ord('2') else 0
    
    stdscr.nodelay(True)

    last_refresh = 0.0
    refresh_interval = 1.0     # eefresh charger telemetry once per second
    input_buffer = ""
    status_msg = ""
    running = True

    while running:
        current_time = time.time()
        
        if current_time - last_refresh >= refresh_interval:
            last_refresh = current_time
            status = charger.read_status(channel)
            
            stdscr.clear()
            label = "CH1" if channel == 0 else "CH2"
            stdscr.addstr(0, 0, f"iCharger 406 DUO - {label}")
            
            if status is None:
                stdscr.addstr(2, 2, f"Status read failed: {charger.error}", curses.A_REVERSE)
            else:
                stdscr.addstr(2, 2, f"Status:   {status['run_status_name']}")
                stdscr.addstr(3, 2, f"Voltage:  {status['voltage_v']:.3f} V")
                stdscr.addstr(4, 2, f"Current:  {status['current_a']:.2f} A")
                stdscr.addstr(5, 2, f"Capacity: {status['capacity_mah']} mAh")
                stdscr.addstr(6, 2, f"Temp:     {status['temp_c']:.1f} C")
                
                if status["cells_mv"]:
                    cells = "  ".join(f"{v}mV" for v in status["cells_mv"])
                    stdscr.addstr(7, 2, f"Cells:    {cells}")
            
            stdscr.addstr(9, 0, "Commands: start | stop | limit <mA> <mV> | quit")
            if status_msg:
                stdscr.addstr(10, 2, f"Result: {status_msg}")

        stdscr.addstr(12, 0, f"> {input_buffer}")
        stdscr.clrtoeol()
        stdscr.refresh()

        ch = stdscr.getch()
        
        if ch == -1:
            continue
            
        elif ch in (ord('\n'), ord('\r')):
            cmd = input_buffer.strip().lower()
            parts = cmd.split()
            input_buffer = ""
            
            if not parts:
                continue
                
            op = parts[0]
            
            if op in ("quit", "exit"):
                running = False
                
            elif op == "start":
                ok = charger.start(channel)
                status_msg = "Started." if ok else f"Failed: {charger.error}"
                
            elif op == "stop":
                ok = charger.stop(channel)
                status_msg = "Stopped." if ok else f"Failed: {charger.error}"
                
            elif op == "limit" and len(parts) == 3:
                try:
                    ok, c, v = charger.set_limits(channel, int(parts[1]), int(parts[2]))
                    status_msg = f"Limits set: {c}mA / {v}mV" if ok else f"Failed: {charger.error}"
                except ValueError:
                    status_msg = "Usage: limit <mA> <mV>"
            else:
                status_msg = f"Unknown command: '{op}'"
                
            last_refresh = 0.0 

        elif ch in (127, 8, curses.KEY_BACKSPACE):
            input_buffer = input_buffer[:-1]
            
        elif 32 <= ch <= 126:
            input_buffer += chr(ch)

    charger.disconnect()

if __name__ == "__main__":
    curses.wrapper(main)
