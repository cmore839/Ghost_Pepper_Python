# services/analysis_service.py
import numpy as np

class AnalysisService:
    """
    Contains functions to analyze system responses, such as a step response.
    """
    def analyze_step_response(self, timestamps, data, step_value):
        """
        Calculates key performance indicators for a step response.

        Returns:
            A dictionary containing rise_time, overshoot, and settling_time.
        """
        if len(timestamps) < 2 or step_value == 0:
            return {"rise_time": 0, "overshoot": 0, "settling_time": 0, "peak_time": 0}

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
            rise_time = -1 

        # --- Overshoot and Peak Time ---
        peak_index = np.argmax(data)
        peak_time = timestamps[peak_index]
        max_val = data[peak_index]
        overshoot = ((max_val - step_value) / step_value) * 100 if max_val > step_value else 0

        # --- Settling Time (within +/- 5% of step_value) ---
        try:
            settling_band_upper = step_value * 1.05
            settling_band_lower = step_value * 0.95
            
            outside_band_indices = np.where((data > settling_band_upper) | (data < settling_band_lower))[0]
            
            if len(outside_band_indices) > 0:
                last_outside_time = timestamps[outside_band_indices[-1]]
                settling_time = last_outside_time
            else: 
                settling_time = timestamps[-1]
                
        except IndexError:
            settling_time = -1

        return {
            "rise_time": rise_time,
            "overshoot": overshoot,
            "settling_time": settling_time,
            "peak_time": peak_time
        }