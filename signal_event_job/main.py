import os
from datetime import datetime, timezone
import pandas as pd

from bosch.discover import discover_bosch_files
from bosch.loader import load_timeseries_file
from bosch.normalize import normalize_timeseries
from features.compute import compute_window_features
from detection.anomaly import detect_anomalies
from detection.segment import segment_anomalies_to_events
from bq.writer import ensure_tables, write_features, write_events_merge, reset_tables, log_dq_metrics
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from etl_job.rollup_job import run_rollup

TENANT_ID = os.environ.get("TENANT_ID", "demo_tenant")
SITE_ID = os.environ.get("SITE_ID", "demo_site")
BOSCH_DATA_ROOT = os.environ["BOSCH_DATA_ROOT"]
CLEAN_START = os.environ.get("CLEAN_START", "false").lower() == "true"

WINDOW_SEC = int(os.environ.get("WINDOW_SEC", "1"))
Z_THRESHOLD = float(os.environ.get("Z_THRESHOLD", "5.0"))
MIN_EVENT_SEC = int(os.environ.get("MIN_EVENT_SEC", "2"))

def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    if CLEAN_START:
        print("CLEAN_START=true, resetting tables...")
        reset_tables()
    else:
        ensure_tables()

    files = discover_bosch_files(BOSCH_DATA_ROOT, limit=int(os.environ.get("FILE_LIMIT", "2")))
    if not files:
        raise RuntimeError(f"No Bosch data files found under BOSCH_DATA_ROOT={BOSCH_DATA_ROOT}")

    print(f"Found {len(files)} files to process.")

    all_events = []

    for path in files:
        print(f"Processing {path}...")
        raw_df = load_timeseries_file(path)
        ts_df = normalize_timeseries(raw_df)  # must output timestamp + machine_id + numeric columns

        feat_df = compute_window_features(
            ts_df,
            window_sec=WINDOW_SEC,
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            source_file=path,
        )
        write_features(feat_df)

        anomaly_df = detect_anomalies(feat_df, z_threshold=Z_THRESHOLD)
        events_df = segment_anomalies_to_events(
            anomaly_df,
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            min_event_sec=MIN_EVENT_SEC,
            run_id=run_id
        )
        if not events_df.empty:
            write_events_merge(events_df)
            all_events.append(events_df)
            print(f"  -> Generated {len(events_df)} events.")
        else:
            print("  -> No events generated.")

    if all_events:
        combined_events = pd.concat(all_events)
        log_dq_metrics(TENANT_ID, SITE_ID, combined_events)
    else:
        # even if no events, log a zero-size batch for the gate
        log_dq_metrics(TENANT_ID, SITE_ID, pd.DataFrame(columns=["machine_id", "start_ts", "duration_seconds"]))

    print("Triggering Rollup Job...")
    run_rollup()

    print(f"Done. run_id={run_id}")

if __name__ == "__main__":
    main()
