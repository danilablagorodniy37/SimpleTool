"""Проверка перед публикацией: секреты, личные данные и файлы, которым не место в открытом репозитории.

Запуск из корня репозитория:
    python tools/check_secrets.py            # все файлы, которые попадут в репозиторий
    python tools/check_secrets.py --staged   # только подготовленные к коммиту (pre-commit)
    python tools/check_secrets.py --history  # все версии всех файлов в истории git (CI)

Что ищет:
  * токены и ключи: GitHub, GitLab, AWS, Google, Slack, Stripe, OpenAI/Anthropic, Telegram, JWT,
    приватные ключи, пароли и ключи в присваиваниях, логины в URL, строки с высокой энтропией;
  * личные данные: e-mail (кроме noreply GitHub), пути профиля C:\\Users\\<имя>, локальные диски D:–Z:,
    SID учётных записей, имена компьютеров, а на Windows — имя пользователя и компьютера;
  * файлы, которые нельзя публиковать: .env, ключи и сертификаты, базы данных, архивы,
    настройки IDE, docs/ (база «ТВикинариум» — чужой контент), данные SimpleTool с компьютера;
  * метаданные в картинках (текстовые блоки PNG, EXIF).
Ложное срабатывание можно пропустить пометкой «secret-scan: allow» в той же строке.
Код выхода 1, если что-то найдено.
"""
import math
import os
import re
import subprocess
import sys

ALLOW = "secret-scan: allow"

SECRETS = [
    ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("AWS access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    ("GitLab token", r"\bglpat-[A-Za-z0-9_-]{20,}"),
    ("Slack token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    ("webhook URL", r"https://(?:hooks\.slack\.com/services|discord(?:app)?\.com/api/webhooks)/\S+"),
    ("Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("Stripe key", r"\b[rs]k_(?:live|test)_[0-9A-Za-z]{16,}"),
    ("OpenAI/Anthropic key", r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    ("Telegram bot token", r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"),
    ("JWT", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("credentials in URL", r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
    ("hard-coded secret", r"(?i)\b(?:pass(?:word|wd)?|pwd|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret)\b"
                          r"\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"),
]

PERSONAL = [
    ("e-mail", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("user profile path", r"(?i)[A-Z]:[\\/]{1,2}Users[\\/]{1,2}(?!(?:Public|Default|All Users)\b)[^\\/\s\"'<>|]+"),
    ("home directory path", r"/(?:home|Users)/[A-Za-z_][\w.-]*"),
    ("local drive path", r"(?<![A-Za-z0-9])[D-Zd-z]:[\\/](?=[\w.-])"),
    ("account SID", r"\bS-1-5-21-\d+-\d+-\d+"),
    ("computer name", r"\b(?:DESKTOP|LAPTOP|WIN)-[A-Z0-9]{6,}\b"),
]

FORBIDDEN = [
    (r"(^|/)\.env(\.[^/]*)?$", "environment file"),
    (r"\.(pem|key|p12|pfx|jks|keystore|ppk|kdbx|ovpn)$", "key or certificate"),
    (r"(^|/)id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$", "SSH key"),
    (r"(^|/)(credentials|secrets?)(\.[^/]*)?$", "credentials file"),
    (r"\.(sqlite3?|db|mdb|accdb)$", "database"),
    (r"\.(zip|rar|7z|tar|gz|tgz)$", "archive (contents cannot be checked)"),
    (r"(^|/)\.(idea|vscode)/", "IDE settings"),
    (r"(^|/)docs/", "local materials: notes and third-party content"),
    (r"(^|/)(backup|settings)\.json$", "SimpleTool data from a computer"),
    (r"\.(log|dmp)$", "log or dump"),
]

NOREPLY = ("users.noreply.github.com", "example.com", "example.org")
TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{32,}")


def personal_patterns():
    """Общие шаблоны плюс имя пользователя и компьютера, если проверка идёт на Windows."""
    patterns = list(PERSONAL)
    if os.name == "nt":
        for kind, value in (("Windows user name", os.environ.get("USERNAME", "")),
                            ("computer name", os.environ.get("COMPUTERNAME", ""))):
            if len(value) >= 4:
                patterns.append((kind, r"(?i)(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])"))
    return patterns


CHECKS = [(kind, re.compile(p), True) for kind, p in SECRETS] + \
         [(kind, re.compile(p), False) for kind, p in personal_patterns()]


def entropy(text):
    return -sum(n / len(text) * math.log2(n / len(text)) for n in (text.count(c) for c in set(text)))


def shown(value, secret):
    """Секрет в отчёте не печатается целиком."""
    return value[:4] + "..." if secret else value


def scan_line(label, line, findings):
    if ALLOW in line:
        return
    for kind, pattern, secret in CHECKS:
        for match in pattern.finditer(line):
            value = match.group(0)
            if kind == "e-mail" and value.lower().endswith(NOREPLY):
                continue
            findings.append(f"{label}: {kind}: {shown(value, secret)}")
    for token in TOKEN.findall(line):
        # Случайные ключи содержат и буквы, и цифры; длинные слова и пути через дефис — нет
        if re.search(r"\d", token) and re.search(r"[A-Za-z]", token) and entropy(token) > 4.5:
            findings.append(f"{label}: high-entropy string: {shown(token, True)}")


def scan_text(label, text, findings):
    for number, line in enumerate(text.splitlines(), 1):
        scan_line(f"{label}:{number}", line, findings)


def scan_binary(label, data, findings):
    for chunk in (b"tEXt", b"iTXt", b"zTXt", b"eXIf"):
        if chunk in data:
            findings.append(f"{label}: image metadata ({chunk.decode()} chunk)")
    if b"Exif\x00\x00" in data:
        findings.append(f"{label}: image metadata (EXIF)")
    # Пути, адреса и ключи могут сидеть в метаданных или ресурсах двоичного файла
    for run in re.findall(rb"[\x20-\x7e]{8,}", data):
        text = run.decode("ascii")
        for kind, pattern, secret in CHECKS:
            match = pattern.search(text)
            if match and not (kind == "e-mail" and match.group(0).lower().endswith(NOREPLY)):
                findings.append(f"{label}: {kind} inside binary: {shown(match.group(0), secret)}")


def check_path(path, label, findings):
    for pattern, reason in FORBIDDEN:
        if re.search(pattern, path, re.IGNORECASE):
            findings.append(f"{label}: file must not be published: {reason}")


def git(*args, data=None):
    return subprocess.run(["git", *args], input=data, capture_output=True, check=True).stdout


def worktree_files():
    for raw in filter(None, git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")):
        path = raw.decode("utf-8", "replace")
        try:
            with open(path, "rb") as f:
                yield path, path, f.read()
        except FileNotFoundError:
            continue  # удалён, но ещё в индексе


def staged_files():
    for raw in filter(None, git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split(b"\0")):
        path = raw.decode("utf-8", "replace")
        yield path, path, git("show", ":" + path)


def history_files():
    """Каждая версия каждого файла из всех веток и тегов."""
    paths = {}
    for line in git("rev-list", "--all", "--objects").decode("utf-8", "replace").splitlines():
        sha, _, path = line.partition(" ")
        if path:
            paths.setdefault(sha, path)
    out = git("cat-file", "--batch", data=("\n".join(paths) + "\n").encode())
    pos = 0
    while pos < len(out):
        end = out.index(b"\n", pos)
        header = out[pos:end].split()
        if len(header) != 3:  # объект не найден
            pos = end + 1
            continue
        sha, kind, size = header[0].decode(), header[1], int(header[2])
        data = out[end + 1:end + 1 + size]
        pos = end + 1 + size + 1
        if kind == b"blob":
            yield paths[sha], f"{paths[sha]}@{sha[:7]}", data


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"
    source = {"--staged": staged_files, "--history": history_files}.get(mode, worktree_files)
    findings, count = [], 0
    for path, label, data in source():
        count += 1
        check_path(path, label, findings)
        if b"\0" in data[:8192] or data.startswith(b"\x89PNG"):
            scan_binary(label, data, findings)
        else:
            scan_text(label, data.decode("utf-8", "replace"), findings)
    if findings:
        print(f"secret scan ({mode}): {len(findings)} problem(s) in {count} file(s)")
        for finding in findings:
            print("  " + finding)
        print(f"False positive? Add '{ALLOW}' to that line.")
        return 1
    print(f"secret scan ({mode}): clean, {count} file(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
