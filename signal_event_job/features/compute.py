import pandas as pd
import numpy as np

def compute_window_features(ts_df: pd.DataFrame, window_sec: int, tenant_id: str, site_id: str, source_file: str) -> pd.DataFrame:
    df = ts_df.copy()
    # Floor to window bucket
    df["ts"] = df["timestamp"].dt.floor(f"{window_sec}s")

    group_cols = ["ts", "machine_id"]
    agg = {}

    # Identify which acc columns differ from the standard and adapt if needed
    # (Assuming normalization unified them to acc_x/y/z)
    for axis in ["acc_x", "acc_y", "acc_z"]:
        if axis in df.columns:
            agg[axis] = ["mean", "std", "max"]

    if not agg:
        # If no acc columns, we can't compute features effectively
        return pd.DataFrame()

    feat = df.groupby(group_cols).agg(agg)
    # Flatten columns: acc_x_mean, acc_x_std, etc.
    feat.columns = ["_".join(col).strip() for col in feat.columns.values]
    feat = feat.reset_index()

    # derive RMS and peak
    for axis in ["acc_x", "acc_y", "acc_z"]:
        m = f"{axis}_mean"
        s = f"{axis}_std"
        mx = f"{axis}_max"
        if m in feat.columns and s in feat.columns:
            feat[f"{axis}_rms"] = np.sqrt((feat[m] ** 2) + (feat[s] ** 2))
        
        # simplified peak logic: just take max for now, or mix
        if mx in feat.columns:
            if "acc_peak" not in feat.columns:
                feat["acc_peak"] = feat[mx]
            else:
                feat["acc_peak"] = np.maximum(feat["acc_peak"], feat[mx])

    feat["tenant_id"] = tenant_id
    feat["site_id"] = site_id
    feat["window_sec"] = window_sec
    feat["source_file"] = source_file
    feat["ingested_at"] = pd.Timestamp.utcnow()

    # Filter columns to match strict BQ schema
    # Filter columns to match strict BQ schema
    keep_cols = [
        "tenant_id", "site_id", "machine_id", "ts", "window_sec",
        "acc_rms_x", "acc_rms_y", "acc_rms_z", "acc_peak",
        "source_file", "ingested_at"
    ]
    
    # Ensure all columns exist
    for c in keep_cols:
        if c not in feat.columns:
            feat[c] = None
            
    return feat[keep_cols]
