"""Build a reproducible OK-WW plugin archive using the Python standard library."""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
FILES = ("WorkshopTab.py", "manifest.json", "README.md", "NOTICE.md", "LICENSE.txt", "CHANGELOG.md")


def build(tag=None):
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8-sig"))
    version = manifest["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Expected a stable X.Y.Z version")
    if tag and tag != "v" + version:
        raise ValueError(f"Tag {tag} does not match manifest version {version}")
    if manifest.get("custom_tabs") != [["WorkshopTab", "CharacterCodeTab"]] or manifest.get("tasks") != []:
        raise ValueError("Unexpected plugin entry points")
    ast.parse((ROOT / "WorkshopTab.py").read_text(encoding="utf-8"))
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    archive = out / f"ok-team-workshop-{version}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
        for name in FILES:
            data = (ROOT / name).read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode("utf-8")
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Optional release tag, e.g. v1.0.0")
    build(parser.parse_args().tag)
