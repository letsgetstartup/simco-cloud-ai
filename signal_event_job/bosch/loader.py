import pandas as pd
import h5py
import numpy as np
from datetime import datetime, timezone
import os
import re

def _parse_filename(path: str):
    # Example: M01_Feb_2020_OP03_000.h5
    basename = os.path.basename(path)
    # Regex to capture Machine, Month, Year
    # M(\d+)_(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)_(\d{4})
    match = re.search(r"(M\d+)_([A-Za-z]+)_(\d{4})", basename)
    if match:
        machine_id = match.group(1)
        month_str = match.group(2)
        year_str = match.group(3)
        # Construct start date (1st of month)
        try:
            start_date = datetime.strptime(f"{month_str} {year_str}", "%b %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            start_date = datetime.now(timezone.utc)
        
        # DEMO FIX: Shift to present if requested
        if os.environ.get("SHIFT_TO_PRESENT", "false").lower() == "true":
            now = datetime.now(timezone.utc)
            # We keep the relative day of month if possible, but simplest is just today
            start_date = now.replace(hour=start_date.hour, minute=start_date.minute, second=start_date.second)
            
        return machine_id, start_date
    return "UNKNOWN", datetime.now(timezone.utc)

def _load_h5(path: str) -> pd.DataFrame:
    with h5py.File(path, 'r') as f:
        if 'vibration_data' not in f:
            raise ValueError(f"No vibration_data in {path}")
        data = f['vibration_data'][:]
        # shape (N, 3) -> acc_x, acc_y, acc_z
    
    # 2000 Hz
    freq = 2000
    n_samples = len(data)
    
    machine_id, start_date = _parse_filename(path)
    
    # Create time index
    # Vectorized timestamp creation
    # start_ts + (index / freq)
    
    # Using pandas create_date_range or similar is faster than iteration
    # But to_timedelta + scalar start is easiest
    timedeltas = pd.to_timedelta(np.arange(n_samples) / freq, unit='s')
    timestamps = pd.Timestamp(start_date) + timedeltas
    
    df = pd.DataFrame(data, columns=['acc_x', 'acc_y', 'acc_z'])
    df['timestamp'] = timestamps
    df['machine_id'] = machine_id
    
    return df

def load_timeseries_file(path: str) -> pd.DataFrame:
    """
    Minimal loader that supports CSV/Parquet/H5.
    """
    p = path.lower()
    if p.endswith(".csv"):
        return pd.read_csv(path)
    if p.endswith(".parquet"):
        return pd.read_parquet(path)
    if p.endswith(".h5"):
        return _load_h5(path)
        
    raise NotImplementedError(f"Unsupported file type: {path}")
