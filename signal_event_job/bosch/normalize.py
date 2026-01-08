import pandas as pd

def normalize_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Output columns must include:
      - timestamp (UTC, pandas datetime)
      - machine_id (string)
      - numeric signals: acc_x/acc_y/acc_z or similar
    Copilot must map actual Bosch column names here after inspecting the dataset.
    """
    out = df.copy()

    # Generic cleanup - strip whitespace from columns
    out.columns = [c.strip() for c in out.columns]

    # Example mapping – MUST be updated to real Bosch columns
    # Try different potential time column names
    time_col = None
    for c in ["timestamp", "time", "Date/Time"]:
        if c in out.columns:
            time_col = c
            break
            
    if time_col:
        out["timestamp"] = pd.to_datetime(out[time_col], utc=True)
    else:
        # If no timestamp, create a dummy one based on index for testing if needed
        # But per requirements we should probably raise error or look closer
        raise ValueError(f"No timestamp column found in columns: {out.columns}")

    if "machine_id" not in out.columns:
        out["machine_id"] = "UNKNOWN"

    # Identify accelerometer columns
    # Adjust this logic based on actual column names in CSV
    # e.g. "X_ vibration", "Y_vibration" etc.
    
    # For now, we'll try to map common names or keep existing if they match
    # This might need dynamic mapping after I see the file header
    
    keep_candidates = ["timestamp", "machine_id", "acc_x", "acc_y", "acc_z", "spindle_rpm", "feed_rate"]
    
    # Simple pass-through if columns already exist
    existing_keep = [c for c in keep_candidates if c in out.columns]
    
    # Return what we have for now, sorting by timestamp
    return out[existing_keep].sort_values("timestamp")
