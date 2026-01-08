import pandas as pd

def detect_anomalies(feat_df: pd.DataFrame, z_threshold: float) -> pd.DataFrame:
    if feat_df.empty:
        return feat_df

    df = feat_df.copy()

    # simple baseline per machine: rolling median/std
    df = df.sort_values(["machine_id", "ts"])
    
    if "acc_peak" not in df.columns:
        # Fallback if acc_peak wasn't computed
        df["is_anomaly"] = False
        df["anomaly_reason"] = None
        df["z"] = 0.0
        return df

    # Rolling statistics
    # Note: apply with raw=False is slower but safer for generic functions, 
    # here we use median/abs which works fine.
    df["acc_peak_baseline"] = df.groupby("machine_id")["acc_peak"].transform(lambda s: s.rolling(60, min_periods=10).median())
    
    def get_mad(x):
        return (x - x.median()).abs().median()

    df["acc_peak_mad"] = df.groupby("machine_id")["acc_peak"].transform(lambda s: s.rolling(60, min_periods=10).apply(get_mad, raw=False))
    
    # Avoid division by zero
    df["z"] = (df["acc_peak"] - df["acc_peak_baseline"]) / (df["acc_peak_mad"].replace(0, pd.NA))
    # fill NA z-scores (start related) with 0
    df["z"] = df["z"].fillna(0)

    df["is_anomaly"] = df["z"].abs() >= z_threshold
    df["anomaly_reason"] = df["is_anomaly"].map(lambda x: "VIB_SPIKE" if x else None)

    return df
