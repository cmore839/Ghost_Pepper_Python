# models/plot_config.py
from dataclasses import dataclass, field
from typing import List
import uuid

@dataclass
class SeriesConfig:
    """Represents a single data series on a plot's Y-axis."""
    id: str = field(default_factory=lambda: f"series_{uuid.uuid4().hex[:8]}")
    data_key: str = ""
    dpg_tag: str = ""

@dataclass
class PlotConfig:
    """Represents our single plot window which can have multiple Y-axes."""
    id: str = "main_plot"
    name: str = "Live Data Plot"
    series_list: List[SeriesConfig] = field(default_factory=list)
    dpg_tag: str = ""