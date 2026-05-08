"""
b3njib3nji Kodi Repo Builder
----------------------------
Run this script any time you want to update the repo (e.g. after updating addon_sources.json).
It will:
  1. Download add-on zips listed in addon_sources.json
  2. Package the repository add-on itself into a zip
  3. Regenerate addons.xml and addons.xml.md5

Requirements: Python 3.6+  (no extra packages needed)
Usage:        python build.py
"""

import hashlib
import json
import os
import shutil
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO_DIR = Path(__file__).parent
REPO_ADDON_ID = "repository.b3njib3nji"


# ── helpers ──────────────────────────────────────────────────────────────────

def download(url: str, dest: Path):
    print(f"    Downloading {dest.name} ...")
    urllib.request.urlretrieve(url, dest)


def addon_xml_from_zip(zip_path: Path) -> str | None:
    """Return the raw addon.xml text from inside an add-on zip."""
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name == "addon.xml" or name.endswith("/addon.xml"):
                return z.read(name).decode("utf-8")
    return None


# ── step 1: download add-ons ─────────────────────────────────────────────────

def download_addons():
    sources_path = REPO_DIR / "addon_sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))

    print("\n[1/3] Downloading add-ons")
    for addon in sources["addons"]:
        addon_id = addon["id"]
        url = addon.get("url", "")
        version = addon.get("version", "")

        if "FILL_IN" in url or not url:
            print(f"  SKIP  {addon_id}  — URL not set in addon_sources.json")
            continue

        addon_dir = REPO_DIR / addon_id
        addon_dir.mkdir(exist_ok=True)
        zip_name = f"{addon_id}-{version}.zip"
        zip_path = addon_dir / zip_name

        if zip_path.exists():
            print(f"  SKIP  {zip_name}  (already downloaded)")
        else:
            download(url, zip_path)
            print(f"  OK    {zip_name}")


# ── step 2: package the repo add-on ──────────────────────────────────────────

def package_repo_addon():
    print("\n[2/3] Packaging repository add-on")
    repo_src = REPO_DIR / REPO_ADDON_ID
    addon_xml_path = repo_src / "addon.xml"

    tree = ET.parse(addon_xml_path)
    version = tree.getroot().get("version", "1.0.0")
    zip_path = repo_src / f"{REPO_ADDON_ID}-{version}.zip"

    # Rebuild zip every time so it stays in sync with addon.xml changes
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in repo_src.iterdir():
            if f.suffix != ".zip":
                z.write(f, f"{REPO_ADDON_ID}/{f.name}")

    print(f"  OK    {zip_path.name}")


# ── step 3: build addons.xml ─────────────────────────────────────────────────

def build_addons_xml():
    print("\n[3/3] Building addons.xml")

    addon_entries: list[str] = []

    # Always include the repo add-on itself
    repo_xml_text = (REPO_DIR / REPO_ADDON_ID / "addon.xml").read_text(encoding="utf-8")
    addon_entries.append(ET.tostring(ET.fromstring(repo_xml_text), encoding="unicode"))

    # Collect all other add-on zips
    for addon_dir in sorted(REPO_DIR.iterdir()):
        if not addon_dir.is_dir():
            continue
        if addon_dir.name.startswith((".", "_", "repository.", "settings_templates")):
            continue

        zips = sorted(addon_dir.glob("*.zip"), reverse=True)
        if not zips:
            continue

        xml_text = addon_xml_from_zip(zips[0])
        if xml_text:
            addon_entries.append(ET.tostring(ET.fromstring(xml_text), encoding="unicode"))
            print(f"  + {addon_dir.name}")

    content = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n'
    for entry in addon_entries:
        content += "  " + entry + "\n"
    content += "</addons>\n"

    addons_xml = REPO_DIR / "addons.xml"
    addons_xml.write_text(content, encoding="utf-8")

    md5 = hashlib.md5(content.encode("utf-8")).hexdigest()
    (REPO_DIR / "addons.xml.md5").write_text(md5, encoding="utf-8")

    print(f"\n  addons.xml  — {len(addon_entries)} add-on(s) listed")
    print(f"  addons.xml.md5 = {md5}")


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  b3njib3nji Kodi Repo Builder")
    print("=" * 50)

    download_addons()
    package_repo_addon()
    build_addons_xml()

    print("\n✓ Done — commit and push to GitHub to publish.")
