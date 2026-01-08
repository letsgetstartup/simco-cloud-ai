import pandas as pd
import hashlib
import json

def _event_id(tenant_id: str, site_id: str, machine_id: str, start_ts: pd.Timestamp, reason: str) -> str:
    # Ensure start_ts is string format
    base = f"{tenant_id}|{site_id}|{machine_id}|{start_ts.isoformat()}|{reason}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def segment_anomalies_to_events(df: pd.DataFrame, tenant_id: str, site_id: str, min_event_sec: int, run_id: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    rows = []
    # Ensure sorted order for iteration
    for machine_id, g in df.groupby("machine_id"):
        g = g.sort_values("ts")
        in_evt = False
        start = None
        reason = None
        peak_z = None

        for _, r in g.iterrows():
            is_anom = bool(r.get("is_anomaly", False))
            
            if is_anom and not in_evt:
                in_evt = True
                start = r["ts"]
                reason = r.get("anomaly_reason") or "ANOMALY"
                peak_z = float(r.get("z", 0)) if pd.notna(r.get("z")) else None
            elif (not is_anom) and in_evt:
                end = r["ts"]
                duration = int((end - start).total_seconds())
                if duration >= min_event_sec:
                    rows.append({
                        "event_id": _event_id(tenant_id, site_id, machine_id, start, reason),
                        "tenant_id": tenant_id,
                        "site_id": site_id,
                        "machine_id": machine_id,
                        "event_type": "VIBRATION_ANOMALY",
                        "reason_code": reason,
                        "reason_text": "Derived from Bosch vibration features",
                        "start_ts": start,
                        "end_ts": end,
                        "duration_seconds": duration,
                        "source_updated_at": pd.Timestamp.utcnow(),
                        "ingested_at": pd.Timestamp.utcnow(),
                        "metadata_json": json.dumps({"run_id": run_id, "peak_z": peak_z}),
                    })
                in_evt = False

        # Close running event at end of stream? 
        # Usually better to leave it open or verify usage. For batch, we might close it.
        # Check user preference. "segment anomalies into events (start/end/duration)".
        if in_evt:
             end = g["ts"].iloc[-1]
             duration = int((end - start).total_seconds())
             if duration >= min_event_sec:
                rows.append({
                    "event_id": _event_id(tenant_id, site_id, machine_id, start, reason),
                    "tenant_id": tenant_id,
                    "site_id": site_id,
                    "machine_id": machine_id,
                    "event_type": "VIBRATION_ANOMALY",
                    "reason_code": reason,
                    "reason_text": "Derived from Bosch vibration features (End of Batch)",
                    "start_ts": start,
                    "end_ts": end,
                    "duration_seconds": duration,
                    "source_updated_at": pd.Timestamp.utcnow(),
                    "ingested_at": pd.Timestamp.utcnow(),
                    "metadata_json": json.dumps({"run_id": run_id, "peak_z": peak_z}),
                })

    return pd.DataFrame(rows)
