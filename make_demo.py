"""
make_demo.py -- creates the saved example that anyone can open in the app WITHOUT an API key.

Run it ONCE on a computer that has a working key (venv active, in the project folder):
    python make_demo.py data/before.jpeg data/after.jpeg

What it does:
  1. checks the photos contain no GPS location data (the repo is public)
  2. runs the real AI on the pair
  3. saves copies of the photos and the AI's answer in the demo/ folder

Then commit the demo/ folder (git add demo) and push it. The app shows a
"Load the saved example" button whenever demo/demo.json exists.
"""
import json
import os
import shutil
import sys

from PIL import Image

from pipeline import PipelineError, compare_photos


def has_gps(path) -> bool:
    try:
        return bool(Image.open(path).getexif().get_ifd(0x8825))   # 0x8825 = GPS info
    except Exception:
        return False


if len(sys.argv) != 3:
    print(__doc__)
    sys.exit(1)

before_src, after_src = sys.argv[1], sys.argv[2]
for p in (before_src, after_src):
    if not os.path.exists(p):
        print(f"ERROR: file not found: {p}")
        sys.exit(1)
    if has_gps(p):
        print(f"ERROR: {p} still contains GPS location data. Remove it first (see check_photos.py).")
        sys.exit(1)

try:
    items = compare_photos(before_src, after_src)
except PipelineError as e:
    print("ERROR:", e)
    sys.exit(1)

os.makedirs("demo", exist_ok=True)
before_name = "before" + os.path.splitext(before_src)[1].lower()
after_name = "after" + os.path.splitext(after_src)[1].lower()
shutil.copyfile(before_src, os.path.join("demo", before_name))
shutil.copyfile(after_src, os.path.join("demo", after_name))

with open(os.path.join("demo", "demo.json"), "w", encoding="utf-8") as f:
    json.dump({"before": before_name, "after": after_name, "items": items}, f, indent=2)

print(f"Saved the example to the demo/ folder with {len(items)} possible difference(s):")
for it in items:
    print(" -", it["description"])
print("\nNext: git add demo && git commit -m \"Add saved demo example\" && git push")
