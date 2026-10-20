"""Warns when the terms of use on blagotech.uk are not the ones this SimpleTool shows.

The website copies them from terms.json (on the website: node tools/sync-terms.js) and marks each terms page
with <meta name="simpletool-terms-version">. The release workflow runs this after publishing; it only warns,
because the website is deployed separately and may simply not be updated yet.
"""
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import terms  # noqa: E402

PAGES = ["https://blagotech.uk/simpletool/terms/", "https://blagotech.uk/ru/simpletool/terms/",
         "https://blagotech.uk/ua/simpletool/terms/"]


def site_version(url):
    request = urllib.request.Request(url, headers={"User-Agent": "SimpleTool release check"})
    with urllib.request.urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", "replace")
    match = re.search(r'<meta name="simpletool-terms-version" content="([^"]+)">', html)
    return match.group(1) if match else None


def main():
    behind = []
    for url in PAGES:
        try:
            version = site_version(url)
        except OSError as exc:
            behind.append(f"{url} could not be read: {exc}")
            continue
        if version != terms.VERSION:
            behind.append(f"{url} has the terms {version or '(no version)'}, SimpleTool shows {terms.VERSION}")
    for line in behind:
        print(f"::warning::{line}. On the website run node tools/sync-terms.js, rebuild and deploy.")
    if not behind:
        print(f"blagotech.uk shows the terms {terms.VERSION}, the same as SimpleTool")


if __name__ == "__main__":
    main()
