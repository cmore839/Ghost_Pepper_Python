# sysid_tuner.py
"""
Contains the logic for the System Identification (SysID) autotuning process
using a frequency sweep (chirp) signal.
"""
import time
import threading
import numpy as np
import dearpygui.dearpygui as dpg
import collections
from scipy.optimize import curve_fit
from state import app_state
from config import *
from can_helpers import send_register_byte, send_register_float, log_message

def simulate_first_order_response(t, K, tau, torque_input):
    """
    Simulates the velocity response of a first-order system to a given torque input.
    This is used by curve_fit to find the best K and tau.
    """
    # Create a system model: G(s) = K / (tau*s + 1)
    # This is equivalent to the differential equation: tau * dv/dt + v = K * T
    # We solve this numerically using a simple forward Euler method.
    v = np.zeros_like(t)
    for i in range(len(t) - 1):
        dt = t[i+1] - t[i]
        v_dot = (K * torque_input[i] - v[i]) / tau
        v[i+1] = v[i] + v_dot * dt
    return v

def sysid_thread_func():
    """
    Runs the System Identification process using a chirp signal.
    """
    config = app_state["sysid_config"]
    motor_id = config["motor_id"]
    
    try:
        log_message(f"SysID: Starting chirp test for motor {motor_id}...")
        app_state["sysid_status"] = "1/4: Running frequency sweep..."
        
        # 1. Prepare the motor and data collection
        send_register_byte(motor_id, REG_CONTROL_MODE, REG_MOTION_MODE_TORQUE)
        time.sleep(0.2)
        
        # Clear old telemetry data
        history_len = dpg.get_value("history_slider")
        app_state["motors"][motor_id]["telemetry_history"]["timestamps"] = collections.deque(maxlen=history_len)
        app_state["motors"][motor_id]["telemetry_history"]["velocity"] = collections.deque(maxlen=history_len)
        
        sent_commands = []
        start_time = time.perf_counter()
        
        # 2. Generate the chirp signal and send commands
        duration = config["duration"]
        f0 = config["start_freq"]
        f1 = config["end_freq"]
        amplitude = config["amplitude"]
        
        while True:
            t = time.perf_counter() - start_time
            if t > duration:
                break
            
            # Chirp signal generation (logarithmic sweep)
            k = (f1/f0)**(t/duration)
            instantaneous_phase = 2 * np.pi * duration * f0 * (k - 1) / np.log(f1/f0)
            torque_cmd = amplitude * np.sin(instantaneous_phase)
            
            send_register_float(motor_id, REG_TARGET, torque_cmd)
            sent_commands.append((t, torque_cmd))
            time.sleep(0.002) # Command rate of 500 Hz

        send_register_float(motor_id, REG_TARGET, 0.0)
        time.sleep(0.5)
        
        app_state["sysid_status"] = "2/4: Aligning data..."
        log_message("SysID: Chirp test finished. Analyzing response...")
        
        # 3. Retrieve and align data
        history = app_state["motors"][motor_id]["telemetry_history"]
        measured_times = np.array(history["timestamps"])
        measured_velocities = np.array(history["velocity"])
        
        if len(measured_times) < 50:
            raise ValueError("Not enough telemetry data. Try a longer duration or higher telemetry rate.")
            
        measured_times -= measured_times[0] # Normalize time to start at 0
        
        cmd_times, cmd_torques = zip(*sent_commands)
        
        # Interpolate measured velocity onto the command timestamp grid for alignment
        aligned_velocities = np.interp(cmd_times, measured_times, measured_velocities)
        
        # 4. Fit the data to the simulated model
        app_state["sysid_status"] = "3/4: Fitting model..."
        
        # The function passed to curve_fit must have `t` as the first argument
        fit_func = lambda t, K, tau: simulate_first_order_response(t, K, tau, cmd_torques)
        
        params, covariance = curve_fit(fit_func, cmd_times, aligned_velocities, p0=[10.0, 0.05])
        
        K, tau = params
        log_message(f"SysID: Model identified -> K = {K:.4f}, τ = {tau:.4f}")

        # 5. Calculate PI gains using IMC tuning rules
        app_state["sysid_status"] = "4/4: Calculating gains..."
        lmbda = config["lambda_tc"] # Desired closed-loop time constant
        
        kp = tau / (K * lmbda)
        ki = 1.0 / (K * lmbda)
        
        log_message(f"SysID: Calculated Gains -> P = {kp:.3f}, I = {ki:.3f}")

        app_state["sysid_results"] = {"K": K, "tau": tau, "p": kp, "i": ki}
        app_state["sysid_status"] = "Done! Gains are ready to apply."
        dpg.enable_item("sysid_apply_btn")

    except Exception as e:
        log_message(f"SysID ERROR: {e}")
        app_state["sysid_status"] = f"Error: {e}"
    finally:
        # Cleanup
        if motor_id in app_state["motors"]:
            send_register_float(motor_id, REG_TARGET, 0)
        
        app_state["sysid_active"] = False
        if dpg.is_dearpygui_running():
            dpg.configure_item("sysid_start_btn", label="Start System ID", enabled=True)