"""Writes TERMS.md and terms.json from terms.py, so the terms in the repository match the ones SimpleTool shows.

terms.json is what the website copies: on blagotech.uk, npm run sync-terms takes it from this repository.

Run from the repository root after changing terms.py:
    python tools/terms_md.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import terms  # noqa: E402

PATH = os.path.join(ROOT, "TERMS.md")
JSON_PATH = os.path.join(ROOT, "terms.json")
ORDER = [("en", "English"), ("ru", "Русский"), ("uk", "Українська")]


def render():
    lines = ["# SimpleTool terms of use", "",
             " · ".join(f"[{name}](#{terms.TERMS[lang]['title'].lower().replace(' ', '-')})" for lang, name in ORDER),
             ""]
    for lang, _ in ORDER:
        text = terms.TERMS[lang]
        lines += [f"## {text['title']}", "", f"*{text['updated']}*", "", text["intro"], ""]
        for number, (heading, body) in enumerate(text["sections"], 1):
            lines += [f"### {number}. {heading}", "", body.replace("%LOCALAPPDATA%\\SimpleTool",
                                                                    "`%LOCALAPPDATA%\\SimpleTool`"), ""]
    return "\n".join(lines)


def render_json():
    data = {"version": terms.VERSION}
    for lang, _ in ORDER:
        text = terms.TERMS[lang]
        data[lang] = {"title": text["title"], "updated": text["updated"], "intro": text["intro"],
                      "sections": [{"title": heading, "body": body} for heading, body in text["sections"]]}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    for path, content in ((PATH, render()), (JSON_PATH, render_json())):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"Written {path}")
