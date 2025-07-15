import dearpygui.dearpygui as dpg
import serial
import threading
import time
import struct
import collections
import math

# --- Serial/CAN Configuration ---
COM_PORT = 'COM3'
SERIAL_BAUDRATE = 115200 # Baud rate of the COM port itself

# --- slcan ASCII Commands ---
CMD_OPEN_CAN_CHANNEL = b'O\r'
CMD_SET_BITRATE_1M = b'S8\r'
CMD_CLOSE_CAN_CHANNEL = b'C\r'

# --- Motor & Command Configuration ---
MOTOR_ID = 1
CMD_SET_ENABLED = 0x02
CMD_SET_ANGLE = 0x01
CMD_TELEMETRY_CONTROL = 0x12
TELEMETRY_FRAME_ID = MOTOR_ID + 100

# --- App State ---
app_state = {
    "serial_port": None,
    "is_running": False,
    "is_paused": False,
    "read_thread": None,
    "motor_enabled": False,
    "timestamps": collections.deque(maxlen=1000), # Increased default history
    "angles": collections.deque(maxlen=1000),
    "start_time": time.time(),
    "log_messages": "",
    "last_freq_calc_time": time.time(),
    "update_count": 0
}

# --- DPG Callbacks and Functions ---

def log_message(message):
    """Prepends a new message to the log display."""
    log_time = time.strftime("%H:%M:%S")
    app_state["log_messages"] = f"[{log_time}] {message}\n" + app_state["log_messages"]
    if dpg.does_item_exist("log_box"):
        dpg.set_value("log_box", app_state["log_messages"])

def parse_slcan_message(line):
    """Parses a raw slcan string (e.g., 't0656...') into ID, DLC, and data."""
    try:
        if line.startswith('t') or line.startswith('d'):
            arbitration_id = int(line[1:4], 16)
            dlc = int(line[4:5], 16)
            data_hex = line[5:5 + (dlc * 2)]
            data_bytes = bytes.fromhex(data_hex)
            return arbitration_id, dlc, data_bytes
    except (ValueError, IndexError):
        pass
    return None, None, None

def read_serial_thread():
    """Background thread to continuously read from the serial port."""
    while app_state["is_running"]:
        try:
            if app_state["serial_port"].in_waiting > 0:
                raw_data = app_state["serial_port"].read(app_state["serial_port"].in_waiting)
                decoded_data = raw_data.decode('ascii', errors='ignore').strip()
                
                for line in decoded_data.split('\r'):
                    if not line: continue
                    
                    arb_id, dlc, data = parse_slcan_message(line)

                    if arb_id == TELEMETRY_FRAME_ID and dlc == 6:
                        angle_rad, loop_us = struct.unpack('<fH', data)
                        
                        app_state["timestamps"].append(time.time() - app_state["start_time"])
                        app_state["angles"].append(angle_rad)

                        if not app_state["is_paused"]:
                            dpg.set_value("current_angle_text", f"Current Angle: {angle_rad:.4f} rad")
                            dpg.set_value("loop_time_text", f"Controller Loop (µs): {loop_us}")
                            dpg.set_value("angle_series", [list(app_state["timestamps"]), list(app_state["angles"])])
                            dpg.fit_axis_data("x_axis")
                            dpg.fit_axis_data("y_axis")

                        app_state["update_count"] += 1
                        current_time = time.time()
                        time_delta = current_time - app_state["last_freq_calc_time"]
                        if time_delta >= 1.0:
                            frequency = app_state["update_count"] / time_delta
                            dpg.set_value("update_freq_text", f"GUI Update Freq (Hz): {frequency:.1f}")
                            app_state["update_count"] = 0
                            app_state["last_freq_calc_time"] = current_time

        except serial.SerialException:
            log_message("ERROR: Serial port disconnected.")
            app_state["is_running"] = False
            break
        time.sleep(0.0001) # Sleep for 0.1ms to be responsive to 2kHz+

def send_slcan_command(command_bytes):
    """Sends a raw command to the serial port."""
    if app_state["serial_port"] and app_state["serial_port"].is_open:
        app_state["serial_port"].write(command_bytes)
        log_message(f"SEND: {command_bytes.decode().strip()}")

def connect_serial():
    try:
        log_message(f"Opening serial port {COM_PORT}...")
        app_state["serial_port"] = serial.Serial(COM_PORT, SERIAL_BAUDRATE, timeout=0.1)
        time.sleep(1)

        send_slcan_command(CMD_OPEN_CAN_CHANNEL)
        time.sleep(0.1)
        send_slcan_command(CMD_SET_BITRATE_1M)
        time.sleep(0.1)

        app_state["is_running"] = True
        app_state["read_thread"] = threading.Thread(target=read_serial_thread, daemon=True)
        app_state["read_thread"].start()
        
        dpg.set_item_label("connect_button", "Disconnect")
        dpg.configure_item("status_text", default_value="Status: Connected", color=[0, 255, 0])
        dpg.enable_item("main_controls_group")
        
        log_message("Connection successful. Starting telemetry.")
        control_telemetry(True)
        
    except Exception as e:
        log_message(f"ERROR: {e}")

def disconnect_serial():
    if app_state["is_running"]:
        log_message("Stopping telemetry and disconnecting.")
        control_telemetry(False)
        time.sleep(0.1)
        send_slcan_command(CMD_CLOSE_CAN_CHANNEL)
        app_state["is_running"] = False
        if app_state["read_thread"]:
            app_state["read_thread"].join(timeout=1)
        if app_state["serial_port"]:
            app_state["serial_port"].close()
    
    dpg.set_item_label("connect_button", "Connect")
    dpg.configure_item("status_text", default_value="Status: Disconnected", color=[255, 255, 0])
    dpg.disable_item("main_controls_group")
    log_message("Disconnected.")

def toggle_connection():
    if app_state["is_running"]:
        disconnect_serial()
    else:
        connect_serial()

def toggle_motor_enable():
    app_state["motor_enabled"] = not app_state["motor_enabled"]
    payload_hex = "01" if app_state["motor_enabled"] else "00"
    data_hex = f"{CMD_SET_ENABLED:02X}{payload_hex}"
    dlc = len(data_hex) // 2
    command = f"t{MOTOR_ID:03X}{dlc:X}{data_hex}\r".encode()
    send_slcan_command(command)
    label = "Disable Motor" if app_state["motor_enabled"] else "Enable Motor"
    dpg.set_item_label("enable_button", label)

def send_angle_command(sender, app_data):
    angle_deg = app_data
    dpg.set_value("angle_readout", f"{angle_deg:.1f}°")
    angle_rad = math.radians(angle_deg)
    rad_bytes = struct.pack('<f', angle_rad)
    payload_hex = rad_bytes.hex()
    data_hex = f"{CMD_SET_ANGLE:02X}{payload_hex}"
    dlc = len(data_hex) // 2
    command = f"t{MOTOR_ID:03X}{dlc:X}{data_hex}\r".encode()
    send_slcan_command(command)

def control_telemetry(start: bool):
    payload_hex = "01" if start else "00"
    data_hex = f"{CMD_TELEMETRY_CONTROL:02X}{payload_hex}"
    dlc = len(data_hex) // 2
    command = f"t{MOTOR_ID:03X}{dlc:X}{data_hex}\r".encode()
    send_slcan_command(command)

def toggle_pause_plot():
    app_state["is_paused"] = not app_state["is_paused"]
    label = "Resume Plot" if app_state["is_paused"] else "Pause Plot"
    dpg.set_item_label("pause_button", label)

def change_plot_history(sender, app_data):
    new_size = int(app_data)
    app_state["timestamps"] = collections.deque(app_state["timestamps"], maxlen=new_size)
    app_state["angles"] = collections.deque(app_state["angles"], maxlen=new_size)
    log_message(f"Plot history window set to {new_size} points.")

def toggle_log_window():
    if dpg.is_item_shown("log_window"):
        dpg.hide_item("log_window")
    else:
        dpg.show_item("log_window")

# --- GUI Construction ---
dpg.create_context()
dpg.create_viewport(title='Direct Serial CAN Control Panel', width=1000, height=750)

with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (37, 37, 38), category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5, category=dpg.mvThemeCat_Core)
    with dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (70, 70, 70))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (85, 85, 85))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (60, 60, 60))
dpg.bind_theme(global_theme)

with dpg.window(label="Log / Diagnostics", tag="log_window", width=800, height=250, show=False):
    dpg.add_input_text(tag="log_box", multiline=True, default_value="Welcome!", height=-1, width=-1, readonly=True)

with dpg.window(tag="main_window"):
    with dpg.group(horizontal=True):
        dpg.add_button(label="Connect", callback=toggle_connection, tag="connect_button")
        dpg.add_button(label="Show/Hide Log", callback=toggle_log_window)
        dpg.add_text("Status: Disconnected", tag="status_text")
    
    dpg.add_separator()

    with dpg.group(horizontal=True):
        # Left Panel for Controls and Status
        with dpg.child_window(width=300):
            with dpg.group(tag="main_controls_group"):
                dpg.add_text("Motor Controls")
                dpg.add_button(label="Enable Motor", callback=toggle_motor_enable, tag="enable_button", width=-1)
                dpg.add_slider_float(label="Target Angle", width=-1, min_value=-360, max_value=360, callback=send_angle_command, tag="angle_slider")
                dpg.add_text("0.0°", tag="angle_readout")
                
                dpg.add_separator()
                dpg.add_text("Live Status")
                dpg.add_text("Current Angle: --", tag="current_angle_text")
                dpg.add_text("Controller Loop (µs): --", tag="loop_time_text")
                dpg.add_text("GUI Update Freq (Hz): --", tag="update_freq_text")
                
                dpg.add_separator()
                dpg.add_text("Plot Controls")
                dpg.add_button(label="Pause Plot", callback=toggle_pause_plot, tag="pause_button", width=-1)
                dpg.add_slider_int(label="History (pts)", min_value=50, max_value=10000, default_value=1000, callback=change_plot_history, width=-1)

        # Right Panel for the Plot
        with dpg.child_window(width=-1):
             with dpg.plot(label="Angle History", height=-1, width=-1):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis")
                dpg.add_plot_axis(dpg.mvYAxis, label="Angle (rad)", tag="y_axis")
                dpg.add_line_series([], [], label="Motor Angle", parent="y_axis", tag="angle_series")

dpg.disable_item("main_controls_group")

# --- Start the Application ---
def on_closing():
    disconnect_serial()
    dpg.destroy_context()

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("main_window", True)
dpg.set_exit_callback(on_closing)

while dpg.is_dearpygui_running():
    dpg.render_dearpygui_frame()
