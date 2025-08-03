# coil_winder.py
"""
Contains the state machine logic for the advanced coil winding sequence.
"""
import time
import math
from state import app_state
from config import *
from can_helpers import send_register_byte, send_register_float, log_message
from utils import ramp_value

def winding_thread_func():
    config = app_state["winding_config"]
    bobbin_id = config["bobbin_id"]
    tension_id = config["tension_id"]
    
    dyn = {
        "start_angle": 0.0,
        "pause_angle": 0.0,
        "progress_angle": 0.0,
        "reverse_target_angle": 0.0,
        "current_velocity": 0.0,
        "last_update_time": time.perf_counter()
    }
    app_state["winding_dynamic"] = dyn
    
    try:
        log_message(f"Winder: Thread started. Bobbin={bobbin_id}, Tension={tension_id}.")
        
        send_register_byte(bobbin_id, REG_CONTROL_MODE, 1)
        send_register_byte(tension_id, REG_CONTROL_MODE, 0)
        time.sleep(0.1)
        send_register_byte(bobbin_id, REG_ENABLE, 1)
        send_register_byte(tension_id, REG_ENABLE, 1)

        dyn["start_angle"] = app_state["motors"][bobbin_id]["live_data"]["angle"]
        total_angle_to_wind = config["revolutions"] * 2 * math.pi
        
        # The thread now loops until it's explicitly told to exit
        while app_state["winding_mode"] != "exit":
            now = time.perf_counter()
            dt = now - dyn["last_update_time"]
            dyn["last_update_time"] = now
            
            mode = app_state["winding_mode"]
            current_bobbin_angle = app_state["motors"][bobbin_id]["live_data"]["angle"]
            
            if mode not in ["finished", "idle"]:
                dyn["progress_angle"] = abs(current_bobbin_angle - dyn["start_angle"])
            
            target_velocity = 0.0
            if mode == "winding":
                target_velocity = config["speed"]
            elif mode in ["reversing", "unwinding"]:
                target_velocity = -config["speed"]

            dyn["current_velocity"] = ramp_value(dyn["current_velocity"], target_velocity, config["accel"], dt)
            send_register_float(bobbin_id, REG_TARGET, dyn["current_velocity"])
            
            # --- State Machine Logic ---
            if mode == "winding":
                percent_complete = (dyn["progress_angle"] / total_angle_to_wind) * 100 if total_angle_to_wind > 0 else 0
                app_state["winding_status"] = f"Winding... {percent_complete:.1f}%"
                send_register_float(tension_id, REG_TARGET, config["torque"])
                if dyn["progress_angle"] >= total_angle_to_wind:
                    app_state["winding_mode"] = "finishing"

            elif mode == "pausing":
                if dyn["current_velocity"] == 0.0:
                    dyn["pause_angle"] = current_bobbin_angle
                    app_state["winding_mode"] = "paused"
                    app_state["winding_status"] = f"Paused at {dyn['progress_angle'] / (2*math.pi):.2f} revs"
            
            elif mode == "reversing":
                if "reverse_target_angle" not in dyn:
                    dyn["reverse_target_angle"] = dyn["pause_angle"] - app_state["winding_dynamic"]["reverse_target_delta"]
                app_state["winding_status"] = "Reversing..."
                if current_bobbin_angle <= dyn["reverse_target_angle"]:
                    del dyn["reverse_target_angle"]
                    app_state["winding_mode"] = "pausing"
                    continue
            
            elif mode == "unwinding":
                percent_unwound = (dyn["progress_angle"] / total_angle_to_wind) * 100 if total_angle_to_wind > 0 else 0
                app_state["winding_status"] = f"Unwinding... {100.0 - percent_unwound:.1f}%"
                send_register_float(tension_id, REG_TARGET, config["torque"]) # Use winding tension
                if current_bobbin_angle <= dyn["start_angle"]:
                    app_state["winding_mode"] = "stopping" # Ramp to zero and then exit/disable

            elif mode == "stopping":
                app_state["winding_status"] = "Stopping..."
                if dyn["current_velocity"] == 0.0:
                    app_state["winding_mode"] = "exit"
            
            elif mode == "finishing":
                app_state["winding_status"] = "Finishing..."
                if dyn["current_velocity"] == 0.0:
                    app_state["winding_mode"] = "finished"
            
            elif mode == "finished":
                # In the finished state, hold tension and wait for a new command
                send_register_float(tension_id, REG_TARGET, config["holding_torque"])
                app_state["winding_status"] = "Finished. Holding tension."

            time.sleep(0.01)

    except Exception as e:
        log_message(f"Winder FATAL ERROR: {e}")
    
    # --- Final cleanup is now only for exiting the thread entirely ---
    log_message("Winder: Thread exit. Disabling motors.")
    if bobbin_id in app_state["motors"]:
        send_register_float(bobbin_id, REG_TARGET, 0)
        time.sleep(0.05)
        send_register_byte(bobbin_id, REG_ENABLE, 0)
    if tension_id in app_state["motors"]:
        send_register_float(tension_id, REG_TARGET, 0)
        time.sleep(0.05)
        send_register_byte(tension_id, REG_ENABLE, 0)
    app_state["winding_status"] = "Idle (Reset)"
    app_state["winding_mode"] = "idle"