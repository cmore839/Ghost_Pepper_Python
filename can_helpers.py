# can_helpers.py
"""
Handles all CAN bus communication, including connecting, sending,
and the background thread for reading messages.
"""
import can
import struct
import threading
import time
import dearpygui.dearpygui as dpg
from state import app_state
from config import *
from utils import log_message

def connect_can():
    try:
        log_message(f"Connecting to {CAN_INTERFACE} on {CAN_CHANNEL}...")
        can_filters = [
            {"can_id": CAN_ID_TELEMETRY_BASE, "can_mask": 0x780},
            # --- THIS IS THE FIX ---
            # The mask is changed from 0x7FF to 0x700 to allow responses
            # from all motor IDs (0x300 - 0x3FF).
            {"can_id": CAN_ID_RESPONSE_BASE, "can_mask": 0x700},
        ]
        app_state["bus"] = can.interface.Bus(interface=CAN_INTERFACE, channel=CAN_CHANNEL, bitrate=CAN_BITRATE, can_filters=can_filters)
        app_state["is_running"] = True
        app_state["start_time"] = time.time()
        app_state["read_thread"] = threading.Thread(target=read_can_thread, daemon=True)
        app_state["read_thread"].start()
        
        dpg.set_item_label("connect_button", "Disconnect")
        dpg.configure_item("status_text", default_value="Status: Connected", color=[0, 255, 0])
        dpg.enable_item("main_controls")
        log_message("Connection successful. Use 'Scan for Motors'.")
    except Exception as e:
        log_message(f"ERROR connecting to CAN: {e}")

def disconnect_can():
    if app_state.get("autotune_active", False):
        app_state["autotune_active"] = False
        if app_state["autotune_thread"] and app_state["autotune_thread"].is_alive():
            app_state["autotune_thread"].join(timeout=0.5)

    if app_state.get("sysid_active", False):
        app_state["sysid_active"] = False
        if app_state["sysid_thread"] and app_state["sysid_thread"].is_alive():
            app_state["sysid_thread"].join(timeout=0.5)

    if app_state.get("winding_mode", "idle") != "idle":
        app_state["winding_mode"] = "exit"
        if app_state["winding_thread"] and app_state["winding_thread"].is_alive():
            app_state["winding_thread"].join(timeout=0.5)

    if app_state["is_running"]:
        app_state["is_running"] = False
        if app_state["read_thread"]: app_state["read_thread"].join(timeout=1)
        if app_state["bus"]: app_state["bus"].shutdown()
    
    if dpg.is_dearpygui_running():
        dpg.set_item_label("connect_button", "Connect")
        dpg.configure_item("status_text", default_value="Status: Disconnected", color=[255, 255, 0])
        dpg.disable_item("main_controls")
        log_message("Disconnected.")

def read_can_thread():
    log_message("CAN reading thread started.")
    while app_state["is_running"]:
        try:
            msg = app_state["bus"].recv(timeout=0.1)
            if msg:
                app_state["data_queue"].put(msg)
        except Exception as e:
            log_message(f"Error in CAN read thread: {e}")
            break
    log_message("CAN reading thread stopped.")

def send_can_message(msg):
    if app_state["bus"] and app_state["is_running"]:
        try:
            app_state["bus"].send(msg)
        except can.CanError as e:
            log_message(f"ERROR sending message: {e}")

def request_register_value(motor_id, register):
    """Sends a 1-byte read request for a specific register."""
    if motor_id is None:
        log_message("Command failed: No active motor selected.")
        return
    command_id = CAN_ID_COMMAND_BASE + motor_id
    msg = can.Message(arbitration_id=command_id, data=[register], is_extended_id=False)
    send_can_message(msg)

def send_register_byte(motor_id, register, value):
    if motor_id is None: log_message("Command failed: No active motor selected."); return
    command_id = CAN_ID_COMMAND_BASE + motor_id
    msg = can.Message(arbitration_id=command_id, data=[register, value], is_extended_id=False)
    send_can_message(msg)

def send_register_float(motor_id, register, value):
    if motor_id is None: log_message("Command failed: No active motor selected."); return
    command_id = CAN_ID_COMMAND_BASE + motor_id
    data = [register] + list(struct.pack('<f', value))
    msg = can.Message(arbitration_id=command_id, data=data, is_extended_id=False)
    send_can_message(msg)
    
def send_register_long(motor_id, register, value):
    if motor_id is None: log_message("Command failed: No active motor selected."); return
    command_id = CAN_ID_COMMAND_BASE + motor_id
    data = [register] + list(struct.pack('<L', value))
    msg = can.Message(arbitration_id=command_id, data=data, is_extended_id=False)
    send_can_message(msg)