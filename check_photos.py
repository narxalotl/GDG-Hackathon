"""
check_photos.py -- shows, for every photo in a folder, the date it was taken (from the file's
metadata) and whether it still contains GPS location data.

Run it from the project folder (venv active):
    python check_photos.py data

What you want to see for each photo: a real date, and "no" under location data.
"""
import sys
from pathlib import Path

from PIL import Image

from report import NOT_FOUND, get_image_timestamp


def has_gps(path) -> bool:
    try:
        return bool(Image.open(path).getexif().get_ifd(0x8825))   # 0x8825 = GPS info
    except Exception:
        return False


folder = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})

if not files:
    print(f"No photos found in '{folder}'.")
    sys.exit(1)

print(f"{'file':38} {'photo taken':24} location data")
print("-" * 76)
missing_dates, with_gps = 0, 0
for p in files:
    taken = get_image_timestamp(p)
    gps = has_gps(p)
    missing_dates += taken == NOT_FOUND
    with_gps += gps
    print(f"{p.name[:37]:38} {taken:24} {'YES - remove before pushing!' if gps else 'no'}")

print()
print(f"{len(files)} photo(s): {missing_dates} without a date, {with_gps} with location data.")
