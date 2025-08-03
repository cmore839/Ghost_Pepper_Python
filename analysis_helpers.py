# analysis_helpers.py
"""
Contains functions to analyze system responses, such as a step response.
"""
import numpy as np

def analyze_step_response(timestamps, data, step_value):
    """
    Calculates key performance indicators for a step response.

    Returns:
        A dictionary containing rise_time, overshoot, and settling_time.
    """
    if len(timestamps) < 2 or step_value == 0:
        return {"rise_time": 0, "overshoot": 0, "settling_time": 0}

    # Normalize time to start at 0
    timestamps = np.array(timestamps) - timestamps[0]
    data = np.array(data)

    # --- Rise Time (10% to 90%) ---
    try:
        ten_percent_val = step_value * 0.1
        ninety_percent_val = step_value * 0.9
        t10 = timestamps[np.where(data >= ten_percent_val)[0][0]]
        t90 = timestamps[np.where(data >= ninety_percent_val)[0][0]]
        rise_time = t90 - t10
    except IndexError:
        rise_time = -1 # Indicates failure to reach 90%

    # --- Overshoot ---
    max_val = np.max(data)
    overshoot = ((max_val - step_value) / step_value) * 100 if max_val > step_value else 0

    # --- Settling Time (within +/- 5% of step_value) ---
    try:
        settling_band_upper = step_value * 1.05
        settling_band_lower = step_value * 0.95
        
        # Find the last time the signal goes outside the band
        outside_band_indices = np.where((data > settling_band_upper) | (data < settling_band_lower))[0]
        
        if len(outside_band_indices) > 0:
            last_outside_time = timestamps[outside_band_indices[-1]]
            settling_time = last_outside_time
        else: # Never went outside the band
            settling_time = timestamps[-1]
            
    except IndexError:
        settling_time = -1

    return {
        "rise_time": rise_time,
        "overshoot": overshoot,
        "settling_time": settling_time
    }