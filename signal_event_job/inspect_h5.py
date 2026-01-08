import h5py
import sys

def print_structure(name, obj):
    print(name, obj)
    if isinstance(obj, h5py.Dataset):
        print(f"  Shape: {obj.shape}, Dtype: {obj.dtype}")
        print(f"  Attrs: {dict(obj.attrs)}")
    elif isinstance(obj, h5py.Group) or isinstance(obj, h5py.File):
        print(f"  Attrs: {dict(obj.attrs)}")

if len(sys.argv) < 2:
    print("Usage: python inspect_h5.py <file>")
    sys.exit(1)

fpath = sys.argv[1]
try:
    with h5py.File(fpath, 'r') as f:
        print(f"Inspecting {fpath}...")
        f.visititems(print_structure)
except Exception as e:
    print(f"Error opening {fpath}: {e}")
