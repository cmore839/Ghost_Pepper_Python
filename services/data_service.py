# services/data_service.py
import collections
import numpy as np

class DataService:
    """Manages all real-time data streams for plotting and analysis."""

    def __init__(self):
        """Initializes the DataService."""
        self._data_streams = {}
        self.history_length = 500  # Default history length
        self._calculated_streams = {}
        print("DataService Initialized.")

    def register_stream(self, key):
        """
        Registers a new data stream with a fixed-length deque based on the CURRENT history_length.
        """
        if key not in self._data_streams:
            print(f"Registering stream '{key}' with history length: {self.history_length}")
            self._data_streams[key] = {
                "timestamps": collections.deque(maxlen=self.history_length),
                "values": collections.deque(maxlen=self.history_length)
            }

    def add_data_point(self, key, timestamp, value):
        """Adds a single data point to a stream."""
        if key not in self._data_streams:
            self.register_stream(key)
        
        self._data_streams[key]["timestamps"].append(timestamp)
        self._data_streams[key]["values"].append(value)

    def change_history_length(self, length):
        """
        Updates the history length for ALL existing and future streams.
        This is the critical function that fixes the bug.
        """
        new_length = max(10, int(length))
        
        if self.history_length == new_length:
            return

        print(f"Changing history length from {self.history_length} to {new_length} for ALL streams.")
        self.history_length = new_length
        
        # --- THIS IS THE CRITICAL FIX ---
        # This loop iterates through every existing stream (including gui_target)
        # and replaces its old data buffer with a new one that has the correct,
        # updated maxlen, while preserving the recent data.
        for key, stream in self._data_streams.items():
            current_timestamps = list(stream["timestamps"])
            current_values = list(stream["values"])
            
            stream["timestamps"] = collections.deque(current_timestamps, maxlen=self.history_length)
            stream["values"] = collections.deque(current_values, maxlen=self.history_length)
        # --- END OF FIX ---

    def get_stream_data(self, key):
        """Gets the data for a specific stream."""
        if key in self._calculated_streams:
            return self._compute_calculated_stream(key)

        if key not in self._data_streams:
            self.register_stream(key)
        
        return self._data_streams.get(key)

    def get_all_stream_keys(self):
        """Returns a list of all available stream keys."""
        return sorted(list(self._data_streams.keys()) + list(self._calculated_streams.keys()))

    def register_calculated_stream(self, name, operation, source_keys):
        """Registers a new stream that is calculated from source streams."""
        if name in self.get_all_stream_keys():
            return
        self._calculated_streams[name] = {
            "operation": operation,
            "sources": source_keys
        }

    def _compute_calculated_stream(self, key):
        """Performs the calculation for a derived stream."""
        config = self._calculated_streams.get(key)
        if not config: return None

        source_data = [self.get_stream_data(s) for s in config["sources"]]
        if not all(source_data) or not all(d["timestamps"] for d in source_data):
            return {"timestamps": collections.deque(maxlen=self.history_length), "values": collections.deque(maxlen=self.history_length)}

        ref_times = np.array(source_data[0]["timestamps"])
        if len(ref_times) < 2:
             return {"timestamps": collections.deque(maxlen=self.history_length), "values": collections.deque(maxlen=self.history_length)}
             
        interp_values = [np.array(source_data[0]["values"])]
        for i in range(1, len(source_data)):
            source_times = np.array(source_data[i]["timestamps"])
            source_values = np.array(source_data[i]["values"])
            if len(source_times) > 1:
                interp_values.append(np.interp(ref_times, source_times, source_values))
            else:
                return {"timestamps": collections.deque(maxlen=self.history_length), "values": collections.deque(maxlen=self.history_length)}
        
        result_values = np.zeros_like(ref_times)
        if config["operation"] == "subtract" and len(interp_values) == 2:
            result_values = interp_values[0] - interp_values[1]
        elif config["operation"] == "differentiate" and len(interp_values) == 1:
            result_values = np.gradient(interp_values[0], ref_times, edge_order=2)

        return {
            "timestamps": collections.deque(ref_times, maxlen=self.history_length),
            "values": collections.deque(result_values, maxlen=self.history_length)
        }