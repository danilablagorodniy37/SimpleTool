"""The notes of a GitHub release: what every release says, the SHA-256 of the exe and the version's CHANGELOG section.

The release workflow runs it after the build:
    python tools/release_notes.py 0.6.1 dist/SimpleTool.exe dist/release-notes.md
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")
REPO = "danilablagorodniy37/SimpleTool"

HEADER = """A Windows 10 and 11 tweaker for privacy, system features, File Explorer and the context menu, with a memory \
limiter for programs such as Chrome and Discord. Every change can be reverted. English, Russian and Ukrainian.

> **Beta. Use it at your own risk.** Before SimpleTool applies anything it asks for a Windows restore point and \
creates it for you. On the first run it shows its [terms of use](https://github.com/{repo}/blob/main/TERMS.md) and \
works only after you accept them.

**Download:** `SimpleTool.exe` below — a single portable file for 64-bit Windows 10 and 11, nothing to install. Run \
it as administrator to use every tweak.
SHA-256: `{sha256}`

GitHub Actions built this exe from the tagged source code. To check that, run \
`gh attestation verify SimpleTool.exe -R {repo}` with the [GitHub CLI](https://cli.github.com/).

The exe is not code-signed, so Windows SmartScreen may say "Windows protected your PC" the first time: choose \
**More info → Run anyway**. Some antivirus products flag programs built with PyInstaller by mistake.

More: [blagotech.uk/simpletool](https://blagotech.uk/simpletool/) · Found a problem? Write to service@blagotech.uk \
and attach `%LOCALAPPDATA%\\SimpleTool\\error.log` if there is one.
"""


def section(version, text):
    """The body of "## <version>" in the changelog, without its heading. Empty if there is none."""
    match = re.search(rf"^## {re.escape(version)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def render(version, exe):
    with open(exe, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    with open(CHANGELOG, encoding="utf-8") as f:
        changes = section(version, f.read())
    if not changes:
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    return HEADER.format(repo=REPO, sha256=sha256) + f"\n## What's new in {version}\n\n{changes}\n"


if __name__ == "__main__":
    version, exe, out = sys.argv[1:4]
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(version, exe))
    print(f"Written {out}")
