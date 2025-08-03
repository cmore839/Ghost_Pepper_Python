# utils.py
"""
Contains common utility functions shared across modules to prevent
circular import errors.
"""
import dearpygui.dearpygui as dpg
import time

def log_message(message):
    """Logs a message to the GUI's log box with a timestamp."""
    if dpg.is_dearpygui_running() and dpg.does_item_exist("log_box"):
        log_time = time.strftime("%H:%M:%S", time.localtime())
        current_log = dpg.get_value("log_box")
        new_log = f"[{log_time}] {message}\n" + (current_log if current_log else "")
        dpg.set_value("log_box", new_log)

def ramp_value(current_val, target_val, rate, dt):
    """
    Linearly ramps a value towards a target at a given rate.
    `dt` is the delta-time or time step.
    """
    if current_val == target_val:
        return target_val

    error = target_val - current_val
    step = rate * dt
    
    if abs(error) < step:
        return target_val
    
    return current_val + (step if error > 0 else -step)