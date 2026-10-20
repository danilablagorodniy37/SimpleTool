"""Checking for a newer SimpleTool. Only when the user presses "Check for updates": SimpleTool never goes online
by itself.

blagotech.uk/api/simpletool answers with the newest stable release on GitHub (the same one the website's
download button gives). Nothing about the PC is sent: the request carries only what every web request does.
"""
import json
import re
import urllib.error
import urllib.request

LATEST_URL = "https://blagotech.uk/api/simpletool"
# The website page for each language: it has the download button and the release notes
PAGES = {"en": "https://blagotech.uk/simpletool/", "ru": "https://blagotech.uk/ru/simpletool/",
         "uk": "https://blagotech.uk/ua/simpletool/"}
# Only these addresses are opened from the answer: a page that went wrong cannot send the user anywhere else
TRUSTED = ("https://github.com/danilablagorodniy37/SimpleTool/", "https://blagotech.uk/")
TIMEOUT = 15
MAX_ANSWER = 64 * 1024


class CheckFailed(Exception):
    """The newest version could not be found out: no connection, the website is down, a strange answer."""


def parse_version(text):
    """ "0.6.1" -> (0, 6, 1); None if the text is not a version number."""
    if not isinstance(text, str) or not re.fullmatch(r"\d{1,4}(\.\d{1,4}){0,3}", text):
        return None
    numbers = [int(n) for n in text.split(".")]
    while len(numbers) > 1 and numbers[-1] == 0:  # 0.6 and 0.6.0 are the same version
        numbers.pop()
    return tuple(numbers)


def trusted(url):
    return url if isinstance(url, str) and url.startswith(TRUSTED) else None


def read_latest(current):
    """The website's answer as a dict. Raises CheckFailed."""
    request = urllib.request.Request(LATEST_URL, headers={"User-Agent": f"SimpleTool/{current}",
                                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read(MAX_ANSWER + 1)
    except urllib.error.HTTPError as exc:
        raise CheckFailed(f"blagotech.uk answered {exc.code}") from None
    except urllib.error.URLError as exc:
        raise CheckFailed(str(exc.reason)) from None
    except (OSError, ValueError) as exc:  # timeouts, a connection closed halfway
        raise CheckFailed(str(exc) or type(exc).__name__) from None
    if len(body) > MAX_ANSWER:
        raise CheckFailed("the answer is too long")
    try:
        data = json.loads(body.decode("utf-8"))
    except ValueError:
        raise CheckFailed("the answer is not JSON") from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise CheckFailed("the website could not ask GitHub, try again later")
    return data


def check(current):
    """{"version", "newer", "url", "page"}: the newest version, whether it is newer than current, the exe to
    download and the release notes (None if unknown). Raises CheckFailed."""
    data = read_latest(current)
    latest = parse_version(data.get("version"))
    if latest is None:
        raise CheckFailed("the answer has no version number")
    mine = parse_version(current) or (0,)
    return {"version": data["version"], "newer": latest > mine, "url": trusted(data.get("url")),
            "page": trusted(data.get("page"))}
