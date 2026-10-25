"""Storage for renter submissions that the leasing office can review.

Layout on disk (the whole folder is gitignored):

    submissions/
      <renter_id>/
        renter.json                 name + unit
        <submission_id>/
          meta.json                 room, jurisdiction, upload time, confirmed items, photo hashes
          before.<ext>              exact copy of the uploaded move-in photo
          after.<ext>               exact copy of the uploaded move-out photo

Only items the renter confirmed are saved. Photos are copied byte for byte, so the
SHA-256 hashes stay valid as evidence.
"""
import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("SUBMISSIONS_DIR", os.path.join(BASE, "submissions"))


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s[:60] or "renter"


def make_renter_id(name, unit):
    return _slug(f"{name}-{unit}")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_submission(name, unit, room, jurisdiction, before_path, after_path, items):
    """Save one room's photos and the renter-confirmed items. Returns the submission id."""
    rid = make_renter_id(name, unit)
    renter_dir = os.path.join(ROOT, rid)
    os.makedirs(renter_dir, exist_ok=True)

    renter_file = os.path.join(renter_dir, "renter.json")
    if not os.path.exists(renter_file):
        with open(renter_file, "w", encoding="utf-8") as f:
            json.dump({"name": name.strip(), "unit": unit.strip()}, f)

    sid = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    folder = os.path.join(renter_dir, sid)
    os.makedirs(folder)

    before_name = "before" + (os.path.splitext(before_path)[1].lower() or ".jpg")
    after_name = "after" + (os.path.splitext(after_path)[1].lower() or ".jpg")
    shutil.copyfile(before_path, os.path.join(folder, before_name))
    shutil.copyfile(after_path, os.path.join(folder, after_name))

    meta = {
        "id": sid,
        "room": room,
        "jurisdiction": jurisdiction,
        "uploaded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "before_file": before_name,
        "after_file": after_name,
        "before_sha256": _sha256(before_path),
        "after_sha256": _sha256(after_path),
        "items": items,
    }
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)
    return sid


def list_renters():
    """All renters who have shared something, most recent upload first."""
    renters = []
    if not os.path.isdir(ROOT):
        return renters
    for rid in os.listdir(ROOT):
        info = _read_json(os.path.join(ROOT, rid, "renter.json"))
        if not info:
            continue
        subs = list_submissions(rid)
        if not subs:
            continue
        renters.append({
            "id": rid,
            "name": info.get("name", rid),
            "unit": info.get("unit", ""),
            "count": len(subs),
            "last_upload": subs[0]["uploaded_at"],
        })
    renters.sort(key=lambda r: r["last_upload"], reverse=True)
    return renters


def list_submissions(rid):
    """Every submission for one renter, newest first, with full photo paths added."""
    if rid != _slug(rid):          # block path tricks like "../"
        return []
    renter_dir = os.path.join(ROOT, rid)
    if not os.path.isdir(renter_dir):
        return []
    subs = []
    for sid in os.listdir(renter_dir):
        folder = os.path.join(renter_dir, sid)
        meta = _read_json(os.path.join(folder, "meta.json"))
        if not meta:
            continue
        meta["before_path"] = os.path.join(folder, meta["before_file"])
        meta["after_path"] = os.path.join(folder, meta["after_file"])
        subs.append(meta)
    subs.sort(key=lambda m: m["uploaded_at"], reverse=True)
    return subs
