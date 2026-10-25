"""
scrub_history.py -- removes every photo that contains GPS location data from the WHOLE git history.

Why: photos with location data were committed earlier (even though they are no longer in the
latest files). On a public GitHub repo, anyone can still open the old commits.

How to run (once, from the project folder, with all your work committed):
    pip install git-filter-repo
    python scrub_history.py
Then upload the cleaned history:
    git push --force origin main
Your teammates must then delete their local copy and clone the repo again.

What it does NOT touch: your current files, and photos that have no location data.
A backup of the old history is saved next to the project folder first.
"""
import io
import os
import subprocess
import sys
import tempfile

from PIL import Image

IMAGE_TYPES = (".jpg", ".jpeg", ".png")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True)


def gps_photos():
    """{blob id: set of paths} for every image in ANY commit that contains GPS data (judged by content)."""
    found = {}
    listing = git("rev-list", "--objects", "--all").stdout.decode(errors="ignore").splitlines()
    for line in listing:
        sha, _, path = line.partition(" ")
        if not path.lower().endswith(IMAGE_TYPES):
            continue
        try:
            data = git("cat-file", "-p", sha).stdout
            has_gps = bool(Image.open(io.BytesIO(data)).getexif().get_ifd(0x8825))   # 0x8825 = GPS info
        except Exception:
            has_gps = False
        if has_gps:
            found.setdefault(sha, set()).add(path)
    return found


def main():
    top = git("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        print("ERROR: run this from inside your project folder (the one with the .git folder).")
        return 1
    os.chdir(top.stdout.decode().strip())

    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        print("ERROR: you have uncommitted changes. Commit them first:")
        print('       git add -A && git commit -m "save work before cleanup"')
        return 1

    if git("filter-repo", "--version").returncode != 0:
        print("ERROR: the git-filter-repo tool is not installed. Run:  pip install git-filter-repo")
        return 1

    found = gps_photos()
    if not found:
        print("Good news: no photo anywhere in the history contains GPS location data. Nothing to do.")
        return 0

    print(f"Found {len(found)} photo(s) with location data in the history:")
    for sha, paths in found.items():
        print(f"  {sha[:10]}  {', '.join(sorted(paths))}")

    origin = git("remote", "get-url", "origin").stdout.decode().strip()
    backup = os.path.join(os.path.dirname(os.getcwd()), "GDG-backup-before-scrub.bundle")
    if git("bundle", "create", backup, "--all").returncode != 0:
        print("ERROR: could not create the backup, so nothing was changed.")
        return 1
    print(f"\nBackup of the old history saved: {backup}")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(found) + "\n")
        ids_file = f.name
    result = git("filter-repo", "--strip-blobs-with-ids", ids_file, "--force")
    os.unlink(ids_file)
    if result.returncode != 0:
        print("ERROR while rewriting history:\n" + result.stderr.decode(errors="ignore"))
        return 1
    if origin:
        git("remote", "add", "origin", origin)      # filter-repo removes the remote on purpose

    left = gps_photos()
    print(f"\nAfter cleanup: {len(left)} photo(s) with location data remain in the history.")
    if left:
        print("Something is still there. Do not push. Ask for help.")
        return 1

    print("\nDONE. Next step (this replaces the history on GitHub):")
    print("    git push --force origin main")
    print("Then every teammate should delete their local project folder and run: git clone <repo url>")
    print("(copy your .env file out of the old folder first).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
