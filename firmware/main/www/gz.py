"""gzip the phone page for the firmware image (fixed mtime, so builds are reproducible)."""
import gzip
import sys

data = open(sys.argv[1], "rb").read()
with open(sys.argv[2], "wb") as f:
    f.write(gzip.compress(data, compresslevel=9, mtime=0))
