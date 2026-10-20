"""Writes TERMS.md from terms.py, so the terms in the repository match the ones SimpleTool shows.

Run from the repository root after changing terms.py:
    python tools/terms_md.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import terms  # noqa: E402

PATH = os.path.join(ROOT, "TERMS.md")
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


if __name__ == "__main__":
    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(render())
    print(f"Written {PATH}")
