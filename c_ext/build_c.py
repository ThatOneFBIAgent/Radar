"""
Build script for the radar_signal C extension using cffi.

Run: python c_ext/build_c.py

This produces a compiled shared library that can be imported
from Python as _radar_signal.
"""

from cffi import FFI
import os

ffi = FFI()

# Define the C interface
ffi.cdef("""
    void ema_smooth(const double* data, int len, double alpha, double* out);
    void wma_smooth(const double* data, int len, int window, double* out);
    void compute_magnitude(
        const double* x, const double* y, const double* z,
        int len, double* out
    );
""")

# Read the C source
c_dir = os.path.dirname(os.path.abspath(__file__))
c_source_path = os.path.join(c_dir, "radar_signal.c")

with open(c_source_path, "r") as f:
    c_source = f.read()

ffi.set_source(
    "_radar_signal",
    c_source,
    include_dirs=[c_dir],
    libraries=["m"],  # math library (Linux/macOS), ignored on Windows
)

if __name__ == "__main__":
    ffi.compile(verbose=True)
    print("✓ radar_signal C extension compiled successfully")
