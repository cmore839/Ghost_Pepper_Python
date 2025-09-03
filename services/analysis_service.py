# services/analysis_service.py
import numpy as np

class AnalysisService:
    def analyze_step_response(self, timestamps, values, amplitude):
        if len(timestamps) < 2:
            return {'error': 'Not enough data'}
        
        t = np.array(timestamps)
        y = np.array(values)
        
        try:
            # Find the time where the response reaches 63.2% of its final value
            tau_val = y[0] + 0.632 * (y[-1] - y[0])
            tau_idx = np.where(y >= tau_val)[0][0]
            tau = t[tau_idx] - t[0]
            
            # Estimate Rise Time (10% to 90%)
            val_10 = y[0] + 0.1 * (y[-1] - y[0])
            val_90 = y[0] + 0.9 * (y[-1] - y[0])
            idx_10 = np.where(y >= val_10)[0][0]
            idx_90 = np.where(y >= val_90)[0][0]
            rise_time = (t[idx_90] - t[idx_10]) * 1000 # in ms

            return {
                "time_constant": tau,
                "rise_time": rise_time
            }
        except IndexError:
            return {'error': 'Could not determine response characteristics'}

    def analyze_step_response_performance(self, target_data, actual_data, final_value):
        """Analyzes a step response for overshoot, rise time, and settling time."""
        if len(actual_data['values']) < 20:
            return {"error": "Not enough data for analysis."}

        times = np.array(actual_data['timestamps'])
        values = np.array(actual_data['values'])
        start_value = values[0]
        
        peak_value = np.max(values)
        overshoot = ((peak_value - final_value) / (final_value - start_value)) * 100 if final_value != start_value else 0
        
        ten_percent_val = start_value + 0.1 * (final_value - start_value)
        ninety_percent_val = start_value + 0.9 * (final_value - start_value)
        
        try:
            time_at_10 = times[np.where(values >= ten_percent_val)[0][0]]
            time_at_90 = times[np.where(values >= ninety_percent_val)[0][0]]
            rise_time = time_at_90 - time_at_10
        except IndexError:
            rise_time = -1

        tolerance = 0.02 * abs(final_value - start_value)
        unsettled_indices = np.where(np.abs(values - final_value) > tolerance)[0]
        
        settling_time = times[unsettled_indices[-1]] - times[0] if len(unsettled_indices) > 0 else 0

        return {
            "Overshoot (%)": f"{overshoot:.2f}",
            "Rise Time (ms)": f"{rise_time * 1000:.2f}" if rise_time != -1 else "N/A",
            "Settling Time (ms)": f"{settling_time * 1000:.2f}"
        }

    def analyze_tracking_error(self, target_data, actual_data):
        """Calculates tracking error statistics between two signals."""
        if len(target_data['values']) < 20 or len(actual_data['values']) < 20:
            return {"error": "Not enough data for analysis."}
            
        target_times = np.array(target_data['timestamps'])
        target_values = np.array(target_data['values'])
        actual_times = np.array(actual_data['timestamps'])
        actual_values = np.array(actual_data['values'])
        
        interp_actual_values = np.interp(target_times, actual_times, actual_values)
        
        error = target_values - interp_actual_values
        
        rms_error = np.sqrt(np.mean(error**2))
        peak_error = np.max(np.abs(error))
        
        return {
            "RMS Tracking Error (rad)": f"{rms_error:.4f}",
            "Peak Tracking Error (rad)": f"{peak_error:.4f}"
        }