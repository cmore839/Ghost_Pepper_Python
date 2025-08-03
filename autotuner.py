# autotuner.py
"""
Contains the logic for the Relay Autotuning process, which runs in a
separate thread to keep the GUI responsive.
"""
import time
import threading
import numpy as np
import dearpygui.dearpygui as dpg
from state import app_state
from config import *
from can_helpers import send_register_byte, send_register_float, log_message

def start_autotune_cb():
    active_id = app_state["active_motor_id"]
    if active_id is None:
        log_message("Autotune ERROR: No motor selected.")
        return
        
    if not app_state["is_running"] or app_state["autotune_active"]:
        return
        
    app_state["autotune_active"] = True
    app_state["autotune_results"] = None
    
    dpg.configure_item("autotune_start_btn", label="Running...", enabled=False)
    dpg.disable_item("autotune_apply_btn")
    
    amp = dpg.get_value("autotune_amp")
    dur = dpg.get_value("autotune_dur")
    
    app_state["autotune_thread"] = threading.Thread(target=autotune_thread_func, args=(active_id, amp, dur), daemon=True)
    app_state["autotune_thread"].start()

def apply_gains_cb():
    active_id = app_state["active_motor_id"]
    if active_id and app_state["autotune_results"]:
        p_gain = app_state["autotune_results"]["p"]
        i_gain = app_state["autotune_results"]["i"]
        
        log_message(f"Applying Velocity Gains to motor {active_id}: P={p_gain:.3f}, I={i_gain:.3f}")
        
        send_register_float(active_id, REG_VEL_PID_P, p_gain)
        send_register_float(active_id, REG_VEL_PID_I, i_gain)
        
        dpg.set_value("vel_p_slider", p_gain)
        dpg.set_value("vel_i_slider", i_gain)

def autotune_thread_func(motor_id, relay_amplitude, duration):
    try:
        log_message(f"Autotune: Starting for motor {motor_id}...")
        app_state["autotune_status"] = "Running relay test..."
        send_register_byte(motor_id, REG_CONTROL_MODE, REG_MOTION_MODE_TORQUE)
        time.sleep(0.2)

        relay_data = []
        start_time = time.time()
        last_output = 0

        while time.time() - start_time < duration and app_state["autotune_active"]:
            motor_state = app_state["motors"].get(motor_id)
            if not motor_state: 
                time.sleep(0.01)
                continue
            
            current_velocity = motor_state["live_data"]["velocity"]
            output = relay_amplitude if current_velocity < 0 else -relay_amplitude
            
            if output != last_output:
                send_register_float(motor_id, REG_TARGET, output)
                last_output = output
                
            relay_data.append((time.time(), current_velocity))
            time.sleep(0.01)

        if not app_state["autotune_active"]:
             log_message("Autotune: Canceled.")
             send_register_float(motor_id, REG_TARGET, 0)
             return

        log_message("Autotune: Relay test finished. Analyzing response...")
        app_state["autotune_status"] = "Analyzing..."
        send_register_float(motor_id, REG_TARGET, 0)

        stable_data = np.array([d for d in relay_data if d[0] > start_time + (duration / 4)])
        if len(stable_data) < 20: raise ValueError("Not enough stable data. Try a longer duration.")
            
        velocities = stable_data[:, 1]
        crossings = np.where(np.diff(np.sign(velocities)))[0]
        if len(crossings) < 3: raise ValueError("Could not detect sufficient oscillations.")
            
        periods = np.diff(stable_data[crossings, 0]) * 2
        Tu = np.mean(periods)
        a = (np.max(velocities) - np.min(velocities)) / 2.0
        
        if a < 0.01: raise ValueError(f"Oscillation amplitude ({a:.3f}) is too small.")

        Ku = (4 * relay_amplitude) / (np.pi * a)
        Kp = 0.45 * Ku
        Ti = Tu / 1.2
        Ki = Kp / Ti if Ti > 0 else 0
        
        log_message(f"Autotune: Analysis complete. Ku={Ku:.3f}, Tu={Tu:.3f}s")
        log_message(f"Autotune: Calculated Gains -> P = {Kp:.3f}, I = {Ki:.3f}")
        
        app_state["autotune_results"] = {"p": Kp, "i": Ki}
        app_state["autotune_status"] = "Done! Gains are ready to apply."
        dpg.enable_item("autotune_apply_btn")

    except Exception as e:
        log_message(f"Autotune ERROR: {e}")
        app_state["autotune_status"] = f"Error: {e}"
    finally:
        app_state["autotune_active"] = False
        if dpg.is_dearpygui_running():
            dpg.configure_item("autotune_start_btn", label="Start Autotune", enabled=True)