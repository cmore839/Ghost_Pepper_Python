# services/data_service.py
import collections
import numpy as np
from services.calculation_service import CalculationService

class DataService:
    def __init__(self):
        self._raw_data_streams = {}
        self._calculated_streams = {}
        self._history_length = 1000
        self._calculation_service = CalculationService()

    def register_stream(self, key):
        if key not in self._raw_data_streams:
            self._raw_data_streams[key] = {
                "timestamps": collections.deque(maxlen=self._history_length),
                "values": collections.deque(maxlen=self._history_length)
            }

    def register_calculated_stream(self, key, calculation_type, input_keys):
        self._calculated_streams[key] = {
            "type": calculation_type,
            "inputs": input_keys
        }

    def add_data_point(self, key, timestamp, value):
        if key not in self._raw_data_streams:
            self.register_stream(key)
        
        self._raw_data_streams[key]["timestamps"].append(timestamp)
        self._raw_data_streams[key]["values"].append(value)


    def get_stream_data(self, key):
        """
        Returns the data for a given stream, computing it if necessary.
        """
        if key in self._raw_data_streams:
            return self._raw_data_streams.get(key)
        elif key in self._calculated_streams:
            return self._compute_stream(key)
        return None

    def _compute_stream(self, key):
        """Performs the on-the-fly calculation for a virtual stream."""
        config = self._calculated_streams.get(key)
        if not config: return None
        
        if config["type"] == "subtract":
            stream1 = self.get_stream_data(config["inputs"][0])
            stream2 = self.get_stream_data(config["inputs"][1])
            return self._calculation_service.compute_subtraction(stream1, stream2)
        
        elif config["type"] == "differentiate":
            stream1 = self.get_stream_data(config["inputs"][0])
            return self._calculation_service.compute_derivative(stream1)
            
        return None

    def get_all_stream_keys(self):
        """Returns a list of all available data stream keys."""
        keys = list(self._raw_data_streams.keys()) + list(self._calculated_streams.keys())
        return sorted(keys)

    def change_history_length(self, new_length):
        """Changes the history buffer size for all raw data streams."""
        self._history_length = new_length
        for key in self._raw_data_streams:
            self._raw_data_streams[key]["timestamps"] = collections.deque(self._raw_data_streams[key]["timestamps"], maxlen=self._history_length)
            self._raw_data_streams[key]["values"] = collections.deque(self._raw_data_streams[key]["values"], maxlen=self._history_length)