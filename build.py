"""
b3njib3nji Kodi Repo Builder
----------------------------
Run this any time you update the repo.
Generates: repo zip, wizard zip, addons.xml, addons.xml.md5, index.html files.

Requirements: Python 3.6+
Usage:        python build.py
"""

import hashlib
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO_DIR      = Path(__file__).parent
REPO_ADDON_ID = "repository.b3njib3nji"
WIZARD_ID     = "script.b3njib3nji.wizard"


# ── helpers ───────────────────────────────────────────────────────────────────

def download(url: str, dest: Path):
    print(f"    Downloading {dest.name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
        f.write(r.read())


def addon_xml_from_zip(zip_path: Path) -> str | None:
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name == "addon.xml" or name.endswith("/addon.xml"):
                return z.read(name).decode("utf-8")
    return None


def package_addon(addon_id: str) -> Path:
    """Zip up a local addon folder and return the zip path."""
    src = REPO_DIR / addon_id
    addon_xml_path = src / "addon.xml"
    version = ET.parse(addon_xml_path).getroot().get("version", "1.0.0")
    zip_path = src / f"{addon_id}-{version}.zip"

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in src.rglob("*"):
            if f.suffix == ".zip":
                continue
            z.write(f, f"{addon_id}/{f.relative_to(src)}")

    print(f"  OK    {zip_path.name}")
    return zip_path


def make_index(directory: Path, files: list[str]):
    """Write a simple HTML index that Kodi can browse."""
    lines = [
        "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 3.2 Final//EN\">",
        "<html><head><title>Index</title></head><body>",
        "<table>",
    ]
    for name in files:
        lines.append(f'<tr><td><a href="{name}">{name}</a></td></tr>')
    lines += ["</table>", "</body></html>"]
    (directory / "index.html").write_text("\n".join(lines), encoding="utf-8")


# ── step 1: download third-party add-on zips ─────────────────────────────────

def download_addons():
    sources = json.loads((REPO_DIR / "addon_sources.json").read_text(encoding="utf-8"))
    print("\n[1/4] Downloading add-ons (for local reference only)")
    for addon in sources["addons"]:
        addon_id = addon["id"]
        url      = addon.get("url", "")
        version  = addon.get("version", "")

        if not url or "FILL_IN" in url or url in ("official_kodi_repo", "repository.cocoscrapers"):
            print(f"  SKIP  {addon_id}  — handled by wizard at runtime")
            continue

        addon_dir = REPO_DIR / addon_id
        addon_dir.mkdir(exist_ok=True)
        zip_path = addon_dir / f"{addon_id}-{version}.zip"

        if zip_path.exists():
            print(f"  SKIP  {zip_path.name}  (already downloaded)")
        else:
            download(url, zip_path)
            print(f"  OK    {zip_path.name}")


# ── step 2: package locally-hosted add-ons ───────────────────────────────────

def package_addons():
    print("\n[2/4] Packaging repo and wizard add-ons")
    repo_zip   = package_addon(REPO_ADDON_ID)
    wizard_zip = package_addon(WIZARD_ID)
    return repo_zip, wizard_zip


# ── step 3: build addons.xml (repo + wizard only) ────────────────────────────

def build_addons_xml(repo_zip: Path, wizard_zip: Path):
    print("\n[3/4] Building addons.xml")

    entries = []
    for zip_path in (repo_zip, wizard_zip):
        xml_text = addon_xml_from_zip(zip_path)
        if xml_text:
            entries.append(ET.tostring(ET.fromstring(xml_text), encoding="unicode"))
            print(f"  + {zip_path.parent.name}")

    content = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n'
    for e in entries:
        content += "  " + e + "\n"
    content += "</addons>\n"

    (REPO_DIR / "addons.xml").write_text(content, encoding="utf-8")
    md5 = hashlib.md5(content.encode("utf-8")).hexdigest()
    (REPO_DIR / "addons.xml.md5").write_text(md5, encoding="utf-8")

    print(f"  addons.xml  — {len(entries)} add-on(s) listed")
    print(f"  addons.xml.md5 = {md5}")


# ── step 4: generate index.html files so GitHub Pages can be browsed ─────────

def build_indexes(repo_zip: Path, wizard_zip: Path):
    print("\n[4/4] Generating index.html files")

    # Root index
    make_index(REPO_DIR, [
        f"{REPO_ADDON_ID}/",
        f"{WIZARD_ID}/",
        "addons.xml",
        "addons.xml.md5",
    ])

    # Repo addon folder
    make_index(REPO_DIR / REPO_ADDON_ID, [
        "addon.xml",
        repo_zip.name,
    ])

    # Wizard addon folder
    make_index(REPO_DIR / WIZARD_ID, [
        "addon.xml",
        "default.py",
        wizard_zip.name,
    ])

    print("  OK    index.html files written")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  b3njib3nji Kodi Repo Builder")
    print("=" * 50)

    download_addons()
    repo_zip, wizard_zip = package_addons()
    build_addons_xml(repo_zip, wizard_zip)
    build_indexes(repo_zip, wizard_zip)

    print("\n✓ Done — upload ALL files in kodi-repo/ to GitHub to publish.")
