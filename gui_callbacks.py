# gui_callbacks.py
import dearpygui.dearpygui as dpg
import math
import time
import random
import can
import collections
import threading
from state import app_state
from config import *
from can_helpers import connect_can, disconnect_can, send_can_message, send_register_byte, send_register_float, send_register_long, request_register_value
from autotuner import start_autotune_cb, apply_gains_cb
from coil_winder import winding_thread_func
from sysid_tuner import sysid_thread_func
from analysis_helpers import analyze_step_response
from utils import log_message, ramp_value

def toggle_connection_cb():
    if app_state["is_running"]:
        disconnect_can()
    else:
        connect_can()

def update_gui_from_response(reg_id, value):
    widget_map = {
        REG_VEL_PID_P: "vel_p_slider", REG_VEL_PID_I: "vel_i_slider", REG_VEL_PID_D: "vel_d_slider",
        REG_VEL_PID_LIM: "vel_limit_slider", REG_VEL_PID_RAMP: "vel_ramp_slider",
        REG_ANG_PID_P: "angle_p_slider", REG_ANG_PID_I: "angle_i_slider", REG_ANG_PID_D: "angle_d_slider",
        REG_ANG_PID_LIM: "angle_limit_slider", REG_ANG_PID_RAMP: "angle_ramp_slider",
        REG_CURQ_PID_P: "curq_p_slider", REG_CURQ_PID_I: "curq_i_slider", REG_CURQ_PID_D: "curq_d_slider",
        REG_CURD_PID_P: "curd_p_slider", REG_CURD_PID_I: "curd_i_slider", REG_CURD_PID_D: "curd_d_slider",
        REG_VEL_LPF_T: "vel_lpf_slider",
        REG_CURQ_LPF_T: "curq_lpf_slider",
        REG_CURD_LPF_T: "curd_lpf_slider",
        REG_VOLTAGE_LIMIT: "voltage_limit_input",
        REG_DRIVER_VOLTAGE_PSU: "power_supply_input",
        REG_CURRENT_LIMIT: "current_limit_input",
        REG_VELOCITY_LIMIT: "velocity_limit_input",
        REG_VOLTAGE_SENSOR_ALIGN: "alignment_voltage_input",
        REG_POLE_PAIRS: "pole_pairs_input",
        REG_PHASE_RESISTANCE: "phase_resistance_input",
        REG_INDUCTANCE: "phase_inductance_input",
        REG_KV: "kv_rating_input",
    }
    if reg_id in widget_map:
        widget_tag = widget_map[reg_id]
        if dpg.does_item_exist(widget_tag):
            if widget_tag == "pole_pairs_input":
                dpg.set_value(widget_tag, int(value))
            else:
                dpg.set_value(widget_tag, value)
        else:
            log_message(f"GUI ERROR: Widget tag '{widget_tag}' does not exist.")

def run_current_step_test_cb():
    if app_state["active_motor_id"] is None:
        log_message("ERROR: No motor selected for test.")
        return
    test_thread = threading.Thread(target=current_step_test_thread, daemon=True)
    test_thread.start()

def current_step_test_thread():
    try:
        motor_id = app_state["active_motor_id"]
        amplitude = dpg.get_value("current_test_amp")
        
        plot_exists = False
        for p in app_state["plots"]:
            if p["motor_id"] == motor_id and "current_q" in p["series"]:
                plot_exists = True
                break
        if not plot_exists:
            log_message("INFO: Please add a plot for the active motor showing 'current_q' to visualize the test.")

        history = app_state["motors"][motor_id]["telemetry_history"]
        history["timestamps"].clear()
        history["current_q"].clear()
        
        log_message("Current Test: Starting...")
        send_register_byte(motor_id, REG_CONTROL_MODE, REG_MOTION_MODE_TORQUE)
        time.sleep(0.1)
        send_register_float(motor_id, REG_TARGET, amplitude)
        time.sleep(0.3)
        send_register_float(motor_id, REG_TARGET, 0.0)
        time.sleep(0.2)
        log_message("Current Test: Finished.")

        timestamps = history["timestamps"]
        currents = history["current_q"]
        stats = analyze_step_response(timestamps, currents, amplitude)

        dpg.set_value("current_test_rise_time", f"{stats['rise_time']*1000:.2f} ms" if stats['rise_time'] > 0 else "N/A")
        dpg.set_value("current_test_overshoot", f"{stats['overshoot']:.2f} %")
        dpg.set_value("current_test_settling_time", f"{stats['settling_time']*1000:.2f} ms" if stats['settling_time'] > 0 else "N/A")
    except Exception as e:
        log_message(f"Current Test ERROR: {e}")

def start_resume_winding_cb():
    current_mode = app_state["winding_mode"]
    if current_mode == "idle":
        try:
            app_state["winding_config"] = {
                "bobbin_id": int(dpg.get_value("winder_bobbin_selector")),
                "tension_id": int(dpg.get_value("winder_tension_selector")),
                "revolutions": dpg.get_value("winder_revs"),
                "speed": dpg.get_value("winder_speed"),
                "accel": dpg.get_value("winder_accel"),
                "torque": dpg.get_value("winder_torque"),
                "holding_torque": dpg.get_value("winder_holding_torque"),
            }
            app_state["winding_thread"] = threading.Thread(target=winding_thread_func, daemon=True)
            app_state["winding_thread"].start()
            app_state["winding_mode"] = "winding"
        except (ValueError, TypeError):
            log_message("Winder Error: Ensure Bobbin and Tension motors are selected.")
        except Exception as e:
            log_message(f"Winder Error: {e}")
    elif current_mode == "paused":
        log_message("Winder: Resuming...")
        app_state["winding_mode"] = "winding"

def pause_winding_cb():
    if app_state["winding_mode"] == "winding":
        log_message("Winder: Pausing...")
        app_state["winding_mode"] = "pausing"

def stop_reset_winding_cb():
    mode = app_state["winding_mode"]
    if mode == "finished":
        log_message("Winder: Exiting and disabling motors.")
        app_state["winding_mode"] = "exit"
    elif mode not in ["idle", "stopping"]:
        log_message("Winder: Stopping sequence...")
        app_state["winding_mode"] = "stopping"
    elif mode == "idle":
        app_state["winding_status"] = "Idle"

def unwind_spool_cb():
    if app_state["winding_mode"] == "finished":
        log_message("Winder: Starting to unwind spool...")
        app_state["winding_mode"] = "unwinding"

def reverse_jog_cb():
    if app_state["winding_mode"] == "paused":
        jog_revs = dpg.get_value("winder_jog_revs")
        log_message(f"Winder: Reversing {jog_revs} revolutions...")
        app_state["winding_dynamic"]["reverse_target_delta"] = jog_revs * 2 * math.pi
        app_state["winding_mode"] = "reversing"

def reverse_to_start_cb():
    if app_state["winding_mode"] == "paused":
        log_message("Winder: Reversing to start...")
        app_state["winding_dynamic"]["reverse_target_delta"] = app_state["winding_dynamic"]["progress_angle"]
        app_state["winding_mode"] = "reversing"

def start_sysid_cb():
    active_id = app_state["active_motor_id"]
    if active_id is None:
        log_message("SysID ERROR: No motor selected.")
        return
    if app_state["sysid_active"]:
        return
    app_state["sysid_results"] = None
    dpg.set_value("sysid_k_text", "--"); dpg.set_value("sysid_tau_text", "--")
    dpg.set_value("sysid_p_text", "--"); dpg.set_value("sysid_i_text", "--")
    app_state["sysid_config"] = {
        "motor_id": active_id,
        "start_freq": dpg.get_value("sysid_start_freq"),
        "end_freq": dpg.get_value("sysid_end_freq"),
        "amplitude": dpg.get_value("sysid_amp"),
        "duration": dpg.get_value("sysid_dur"),
        "lambda_tc": dpg.get_value("sysid_lambda"),
    }
    app_state["sysid_active"] = True
    dpg.configure_item("sysid_start_btn", label="Running...", enabled=False)
    dpg.disable_item("sysid_apply_btn")
    app_state["sysid_thread"] = threading.Thread(target=sysid_thread_func, daemon=True)
    app_state["sysid_thread"].start()

def apply_sysid_gains_cb():
    active_id = app_state["active_motor_id"]
    results = app_state["sysid_results"]
    if active_id and results:
        p_gain = results["p"]
        i_gain = results["i"]
        log_message(f"Applying SysID Gains to motor {active_id}: P={p_gain:.3f}, I={i_gain:.3f}")
        send_register_float(active_id, REG_VEL_PID_P, p_gain)
        send_register_float(active_id, REG_VEL_PID_I, i_gain)
        dpg.set_value("vel_p_slider", p_gain)
        dpg.set_value("vel_i_slider", i_gain)

def flip_sensor_dir_cb():
    active_id = app_state["active_motor_id"]
    if active_id is None:
        log_message("ERROR: No motor selected to configure.")
        return
    log_message(f"GUI: Sending Flip Sensor Direction command to motor {active_id}...")
    send_register_byte(active_id, REG_CUSTOM_FLIP_SENSOR_DIR, 1)

def scan_for_motors():
    if not app_state["is_running"]: log_message("ERROR: Must be connected to CAN bus to scan."); return
    log_message("Scanning for motors...")
    app_state["motors"].clear()
    app_state["active_motor_id"] = None
    update_motor_selector_ui()
    msg = can.Message(arbitration_id=CAN_ID_SCAN_BROADCAST, is_extended_id=False)
    send_can_message(msg)

def select_active_motor(sender, app_data):
    try:
        active_id = int(app_data) if app_data else None
        app_state["active_motor_id"] = active_id
        log_message(f"Selected motor {active_id}")
        if active_id is not None:
            log_message(f"Requesting all parameters from motor {active_id}...")
            params_to_request = [
                REG_VOLTAGE_LIMIT, REG_DRIVER_VOLTAGE_PSU, REG_CURRENT_LIMIT, REG_VELOCITY_LIMIT,
                REG_VOLTAGE_SENSOR_ALIGN, REG_POLE_PAIRS, REG_PHASE_RESISTANCE, REG_INDUCTANCE, REG_KV,
                REG_VEL_PID_P, REG_VEL_PID_I, REG_VEL_PID_D, REG_VEL_PID_LIM, REG_VEL_PID_RAMP, REG_VEL_LPF_T,
                REG_ANG_PID_P, REG_ANG_PID_I, REG_ANG_PID_D, REG_ANG_PID_LIM, REG_ANG_PID_RAMP,
                REG_CURQ_PID_P, REG_CURQ_PID_I, REG_CURQ_PID_D, 
                REG_CURD_PID_P, REG_CURD_PID_I, REG_CURD_PID_D,
                REG_CURQ_LPF_T, REG_CURD_LPF_T,
            ]
            for param in params_to_request:
                log_message(f"GUI: Requesting reg 0x{param:02x}...")
                request_register_value(active_id, param)
                time.sleep(0.05)
    except (ValueError, TypeError):
        app_state["active_motor_id"] = None

def update_motor_selector_ui():
    motor_ids_str = [str(mid) for mid in sorted(app_state["motors"].keys())]
    current_value = str(app_state["active_motor_id"]) if app_state["active_motor_id"] else ""
    selector_tags = [
        "motor_selector", "ganging_leader_selector", "ganging_follower_selector",
        "plot_motor_selector", "winder_bobbin_selector", "winder_tension_selector"
    ]
    for tag in selector_tags:
        if dpg.does_item_exist(tag):
            if tag == "motor_selector":
                dpg.configure_item(tag, items=motor_ids_str, default_value=current_value)
            else:
                dpg.configure_item(tag, items=motor_ids_str)

def set_can_id():
    old_id = app_state["active_motor_id"]
    if old_id is None: log_message("ERROR: No motor selected to configure."); return
    try:
        new_id = dpg.get_value("new_can_id_input")
        if not (0 < new_id < 128): log_message("ERROR: CAN ID must be between 1 and 127."); return
        if new_id == old_id: log_message("INFO: New ID is the same as the current ID."); return
        log_message(f"Setting motor {old_id} to new ID {new_id}...")
        send_register_byte(old_id, REG_MOTOR_ADDRESS, new_id)
        log_message("ID set. Click 'Save All Parameters' to make it permanent.")
    except Exception as e: log_message(f"Error setting CAN ID: {e}")
        
def set_target_cb(sender, app_data): send_register_float(app_state["active_motor_id"], REG_TARGET, app_data)
def set_control_mode_cb(sender, app_data):
    mode_map = {"Torque": 0, "Velocity": 1, "Angle": 2}
    mode = mode_map.get(app_data, 2)
    send_register_byte(app_state["active_motor_id"], REG_CONTROL_MODE, mode)
    dpg.set_value("target_input", 0.0)
def enable_motor_cb(sender, app_data): send_register_byte(app_state["active_motor_id"], REG_ENABLE, 1 if app_data else 0)
def set_telemetry_frequency(sender, app_data):
    active_id = app_state["active_motor_id"]
    if active_id is None: return
    try:
        freq_hz = int(app_data.replace(" Hz", ""))
        period_us = int(1_000_000 / freq_hz) if freq_hz > 0 else 0
        log_message(f"Setting motor {active_id} telemetry to {freq_hz} Hz")
        send_register_long(active_id, REG_CUSTOM_TELEMETRY_PERIOD, period_us)
    except ValueError: log_message(f"Invalid frequency format: {app_data}")
def toggle_bandwidth_mode(sender, app_data):
    is_enabled = app_data
    dpg.configure_item("bandwidth_tuning_widgets", show=is_enabled)
    dpg.configure_item("curq_p_slider", enabled=not is_enabled); dpg.configure_item("curq_i_slider", enabled=not is_enabled)
    dpg.configure_item("curd_p_slider", enabled=not is_enabled); dpg.configure_item("curd_i_slider", enabled=not is_enabled)

def apply_bandwidth_gains(sender, app_data):
    active_id = app_state["active_motor_id"]
    try:
        bandwidth_hz = dpg.get_value("current_bw_input")
        resistance = dpg.get_value("phase_resistance_input")
        inductance = dpg.get_value("phase_inductance_input")
        if bandwidth_hz <= 0 or resistance <= 0 or inductance <= 0:
            log_message("ERROR: Bandwidth, Resistance, and Inductance must be positive numbers.")
            return
        p_gain = inductance * bandwidth_hz * 2 * math.pi
        i_gain = resistance * bandwidth_hz * 2 * math.pi
        log_message(f"Applying Current Gains from BW ({bandwidth_hz} Hz): P={p_gain:.4f}, I={i_gain:.4f}")
        lpf_tf = 1.0 / (2 * math.pi * 10 * bandwidth_hz)
        log_message(f"Applying Current LPF Tf from BW: {lpf_tf:.5f} s")
        send_register_float(active_id, REG_CURQ_PID_P, p_gain); send_register_float(active_id, REG_CURQ_PID_I, i_gain)
        send_register_float(active_id, REG_CURD_PID_P, p_gain); send_register_float(active_id, REG_CURD_PID_I, i_gain)
        send_register_float(active_id, REG_CURQ_LPF_T, lpf_tf); send_register_float(active_id, REG_CURD_LPF_T, lpf_tf)
        dpg.set_value("curq_p_slider", p_gain); dpg.set_value("curd_p_slider", p_gain)
        dpg.set_value("curq_i_slider", i_gain); dpg.set_value("curd_i_slider", i_gain)
        dpg.set_value("curq_lpf_slider", lpf_tf); dpg.set_value("curd_lpf_slider", lpf_tf)
    except Exception as e: log_message(f"ERROR calculating bandwidth gains: {e}")

def add_gang_follower_cb():
    leader_id_str = dpg.get_value("ganging_leader_selector"); follower_id_str = dpg.get_value("ganging_follower_selector")
    mode = dpg.get_value("ganging_mode_selector")
    if not leader_id_str or not follower_id_str: log_message("Ganging: Leader and Follower must be selected."); return
    leader_id = int(leader_id_str); follower_id = int(follower_id_str)
    if leader_id == follower_id: log_message("Ganging: Leader and Follower cannot be the same motor."); return
    app_state["gangs"] = [{"leader": leader_id, "followers": [{"id": follower_id, "mode": mode.lower()}]}]
    log_message(f"Motion gang created: Leader={leader_id}, Follower={follower_id} ({mode})")
    redraw_ganging_ui()

def apply_ganged_target(sender, app_data):
    if not app_state["gangs"]: log_message("Ganging: No motion gang configured."); return
    gang = app_state["gangs"][0]
    send_register_float(gang["leader"], REG_TARGET, app_data)
    for follower in gang["followers"]:
        follower_target = app_data if follower["mode"] == "sync" else -app_data
        send_register_float(follower["id"], REG_TARGET, follower_target)

def redraw_ganging_ui():
    if not dpg.does_item_exist("ganging_status_group"): return
    dpg.delete_item("ganging_status_group", children_only=True)
    if app_state["gangs"]:
        gang = app_state["gangs"][0]
        dpg.add_text(f"Leader: {gang['leader']}", parent="ganging_status_group")
        for f in gang["followers"]: dpg.add_text(f" - Follower: {f['id']} ({f['mode']})", parent="ganging_status_group")

def set_plot_history(sender, app_data):
    new_maxlen = app_data
    log_message(f"Setting plot history to {new_maxlen} points.")
    for motor_id in app_state["motors"]:
        for key in app_state["motors"][motor_id]["telemetry_history"]:
            old_deque = app_state["motors"][motor_id]["telemetry_history"][key]
            app_state["motors"][motor_id]["telemetry_history"][key] = collections.deque(list(old_deque), maxlen=new_maxlen)

def resize_plots():
    for plot_config in app_state["plots"]:
        if dpg.does_item_exist(plot_config["tag"]):
            dpg.configure_item(plot_config["tag"], height=-1)

def add_new_plot():
    plot_motor_id_str = dpg.get_value("plot_motor_selector")
    if not plot_motor_id_str: log_message("Plot ERROR: No motor selected to plot."); return
    plot_motor_id = int(plot_motor_id_str)
    app_state["plot_id_counter"] += 1; plot_id = app_state["plot_id_counter"]
    new_plot_config = {"id": plot_id, "tag": f"plot_{plot_id}", "motor_id": plot_motor_id, "y_axes": {}, "series": {}}
    app_state["plots"].append(new_plot_config)
    with dpg.plot(label=f"Plot {plot_id} (Motor {plot_motor_id})", width=-1, parent="plot_container", tag=new_plot_config["tag"], height=-1):
        dpg.add_plot_legend(); dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)")
    redraw_plot_manager(); resize_plots()

def remove_plot(sender, app_data, user_data):
    plot_id_to_remove = user_data
    plot_to_remove = next((p for p in app_state["plots"] if p["id"] == plot_id_to_remove), None)
    if plot_to_remove:
        app_state["plots"].remove(plot_to_remove)
        if dpg.does_item_exist(plot_to_remove["tag"]): dpg.delete_item(plot_to_remove["tag"])
        redraw_plot_manager(); resize_plots()

def add_signal_to_plot(sender, app_data, user_data):
    plot_id, signal_name = user_data, app_data
    plot_config = next((p for p in app_state["plots"] if p["id"] == plot_id), None)
    if not plot_config or signal_name in plot_config["series"]: return
    y_axis_tag = dpg.add_plot_axis(dpg.mvYAxis, label=signal_name, parent=plot_config["tag"])
    plot_config["y_axes"][signal_name] = y_axis_tag
    series_tag = dpg.add_line_series([], [], label=signal_name, parent=y_axis_tag)
    plot_config["series"][signal_name] = series_tag
    color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255), 255)
    with dpg.theme() as item_theme:
        with dpg.theme_component(dpg.mvAll): dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
    dpg.bind_item_theme(series_tag, item_theme)
    redraw_plot_manager()

def remove_signal_from_plot(sender, app_data, user_data):
    plot_id, signal_name = user_data
    plot_config = next((p for p in app_state["plots"] if p["id"] == plot_id), None)
    if not plot_config or signal_name not in plot_config["series"]: return
    dpg.delete_item(plot_config["series"][signal_name]); dpg.delete_item(plot_config["y_axes"][signal_name])
    del plot_config["series"][signal_name]; del plot_config["y_axes"][signal_name]
    redraw_plot_manager()

def redraw_plot_manager():
    if not dpg.does_item_exist("plot_manager_controls"): return
    dpg.delete_item("plot_manager_controls", children_only=True)
    for plot_config in app_state["plots"]:
        plot_id = plot_config["id"]
        with dpg.group(parent="plot_manager_controls"):
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_text(f"Plot {plot_id} (Motor {plot_config['motor_id']})")
                dpg.add_button(label="Remove", callback=remove_plot, user_data=plot_id)
            available_to_add = ["angle", "velocity", "current_q"]
            dpg.add_combo(available_to_add, label=f"##add_signal_{plot_id}", hint="Add Signal...", width=-1, callback=add_signal_to_plot, user_data=plot_id)
            for signal_name in plot_config["series"]:
                with dpg.group(horizontal=True):
                    dpg.add_text(f"  - {signal_name}")
                    dpg.add_button(label="x", small=True, callback=remove_signal_from_plot, user_data=(plot_id, signal_name))