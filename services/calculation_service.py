# services/calculation_service.py
import numpy as np

class CalculationService:
    """Performs mathematical operations on data streams."""

    def compute_subtraction(self, stream1, stream2):
        """Computes the element-wise subtraction of two data streams."""
        if not stream1 or not stream2:
            return None

        timestamps1 = np.array(stream1["timestamps"])
        values1 = np.array(stream1["values"])
        timestamps2 = np.array(stream2["timestamps"])
        values2 = np.array(stream2["values"])

        if len(timestamps1) < 2 or len(timestamps2) < 2:
            return None

        interpolated_values2 = np.interp(timestamps1, timestamps2, values2)
        result = values1 - interpolated_values2
        
        return {"timestamps": timestamps1, "values": result}

    def compute_derivative(self, stream):
        """Computes the numerical derivative of a stream with respect to time."""
        if not stream or len(stream["timestamps"]) < 2:
            return None

        timestamps = np.array(stream["timestamps"])
        values = np.array(stream["values"])
        
        derivative = np.gradient(values, timestamps)

        return {"timestamps": timestamps, "values": derivative}