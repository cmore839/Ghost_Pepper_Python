# main.py
"""
Main application entry point. This file ties all the modules together,
initializes the application, and runs the main loop.
"""
import dearpygui.dearpygui as dpg
import time
import queue
import struct
import collections
from state import app_state, create_new_motor_state
from config import *
from can_helpers import connect_can, disconnect_can, log_message
from gui_layout import create_gui, apply_dark_theme
from gui_callbacks import *

def unpack_telemetry(msg):
    try:
        angle_raw, vel_raw, cur_q_raw = struct.unpack('<ihh', msg.data[0:8])
        return {"angle": angle_raw * 0.0001, "velocity": vel_raw * 0.01, "current_q": cur_q_raw * 0.001}
    except struct.error:
        return None

def process_data_from_queue():
    while not app_state["data_queue"].empty():
        try:
            msg = app_state["data_queue"].get_nowait()
            
            # Check for telemetry messages
            if CAN_ID_TELEMETRY_BASE <= msg.arbitration_id < (CAN_ID_TELEMETRY_BASE + 128):
                motor_id = msg.arbitration_id - CAN_ID_TELEMETRY_BASE
                if motor_id not in app_state["motors"]:
                    history_len = dpg.get_value("history_slider")
                    create_new_motor_state(motor_id, history_len)
                    log_message(f"Discovered new motor with ID: {motor_id}")
                    update_motor_selector_ui()
                
                telemetry = unpack_telemetry(msg)
                if telemetry:
                    motor_state = app_state["motors"][motor_id]
                    motor_state["live_data"] = telemetry
                    history = motor_state["telemetry_history"]
                    history["timestamps"].append(time.time() - app_state["start_time"])
                    for sig, val in telemetry.items():
                         history[sig].append(val)
                    if motor_id == app_state["active_motor_id"]:
                        dpg.set_value("current_angle_text", f"{telemetry['angle']:.2f} rad")
                        dpg.set_value("current_velocity_text", f"{telemetry['velocity']:.2f} rad/s")
                        dpg.set_value("current_iq_text", f"{telemetry['current_q']:.3f} A")
            
            # Check for parameter responses
            elif CAN_ID_RESPONSE_BASE <= msg.arbitration_id < (CAN_ID_RESPONSE_BASE + 128):
                motor_id = msg.arbitration_id - CAN_ID_RESPONSE_BASE
                if motor_id == app_state["active_motor_id"] and len(msg.data) >= 5:
                    reg_id = msg.data[0]
                    value = struct.unpack('<f', msg.data[1:5])[0]
                    log_message(f"Motor {motor_id} responded: Reg 0x{reg_id:02x} = {value:.3f}")
                    update_gui_from_response(reg_id, value)
        
        except queue.Empty: break
        except Exception as e: log_message(f"Error processing CAN queue: {e}")

def update_plots():
    if app_state["is_paused"]: return
    
    for plot_config in app_state["plots"]:
        motor_id = plot_config.get("motor_id")
        if motor_id in app_state["motors"]:
            history = app_state["motors"][motor_id]["telemetry_history"]
            timestamps = list(history["timestamps"])
            for signal_name, series_tag in plot_config["series"].items():
                if dpg.does_item_exist(series_tag) and signal_name in history:
                    signal_data = list(history[signal_name])
                    dpg.set_value(series_tag, [timestamps, signal_data])
            
            if app_state["auto_fit_plots"] and dpg.does_item_exist(plot_config["tag"]):
                plot_tag = plot_config["tag"]
                if len(dpg.get_item_info(plot_tag)["children"][1]) > 1:
                    dpg.fit_axis_data(dpg.get_item_info(plot_tag)["children"][1][0])
                    for axis in dpg.get_item_info(plot_tag)["children"][1][1:]:
                        dpg.fit_axis_data(axis)

def update_winder_ui():
    """Shows and hides winder controls based on the current state for a cleaner UI."""
    mode = app_state["winding_mode"]
    
    # Determine which buttons should be visible for each state
    visibility = {
        "start": mode in ["idle"],
        "pause": mode == "winding",
        "resume": mode == "paused",
        "stop": mode not in ["idle", "stopping"],
        "reverse": mode == "paused",
        "unwind": mode == "finished" # <-- NEW: Show unwind button when finished
    }

    # Configure visibility
    dpg.configure_item("winder_start_resume_btn", show=visibility["start"] or visibility["resume"])
    dpg.configure_item("winder_pause_btn", show=visibility["pause"])
    dpg.configure_item("winder_stop_btn", show=visibility["stop"])
    dpg.configure_item("winder_unwind_btn", show=visibility["unwind"]) # <-- NEW
    
    if dpg.does_item_exist("winder_jog_input_group"):
        dpg.configure_item("winder_jog_input_group", show=visibility["reverse"])

    # Update label for the start/resume/stop buttons based on context
    if mode == "paused":
        dpg.set_item_label("winder_start_resume_btn", "Resume")
    elif mode == "finished":
        dpg.set_item_label("winder_stop_btn", "Turn Off Motors & Reset")
    else:
        dpg.set_item_label("winder_start_resume_btn", "Start Winding")
        dpg.set_item_label("winder_stop_btn", "Stop & Reset")


def main():
    dpg.create_context()
    
    dpg.create_viewport(title='Multi-Motor CAN GUI', width=1500, height=950)
    
    apply_dark_theme()
    create_gui() 
    
    dpg.setup_dearpygui()
    dpg.show_viewport()
    
    # --- THIS IS THE FIX ---
    # This command properly docks the main window to the viewport
    dpg.set_primary_window("main_window", True)
    # -----------------------

    redraw_plot_manager()

    last_plot_update_time = time.time()
    plot_update_interval = 1.0 / 60.0
    last_freq_calc_time = 0
    telemetry_packet_counter = 0
    plot_update_counter = 0

    while dpg.is_dearpygui_running():
        if dpg.does_item_exist("autotune_status_text"):
            dpg.set_value("autotune_status_text", app_state["autotune_status"])

        if app_state["is_running"]:
            packet_count_this_frame = app_state["data_queue"].qsize()
            telemetry_packet_counter += packet_count_this_frame
            process_data_from_queue()
            
            if not app_state["autotune_active"]:
                now = time.time()
                if now - last_plot_update_time > plot_update_interval:
                    update_plots()
                    plot_update_counter += 1
                    last_plot_update_time = now
                if now - last_freq_calc_time > 1.0:
                    if dpg.does_item_exist("actual_freq_text"):
                        dpg.set_value("actual_freq_text", f"{telemetry_packet_counter} Hz")
                    if dpg.does_item_exist("plot_freq_text"):
                        dpg.set_value("plot_freq_text", f"{plot_update_counter} FPS")
                    telemetry_packet_counter = 0; plot_update_counter = 0
                    last_freq_calc_time = now
            else: 
                time.sleep(0.005)

        dpg.render_dearpygui_frame()

    disconnect_can()
    dpg.destroy_context()

if __name__ == "__main__":
    main()