import os

SUPPORTED_EXT = (".csv", ".parquet", ".h5", ".hdf5", ".npy", ".npz", ".mat")

def discover_bosch_files(root: str, limit: int = 2):
    """
    Finds candidate data files. We intentionally limit for initial PoC.
    Copilot must adjust filtering once the repo structure is known.
    """
    out = []
    print(f"Scanning for files in {root} with extensions {SUPPORTED_EXT}")
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(SUPPORTED_EXT):
                full_path = os.path.join(dirpath, fn)
                out.append(full_path)
                if len(out) >= limit:
                    return out
    return out
