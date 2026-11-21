#!/usr/bin/env python3
"""Read-only secret scan of files that would be committed to Git.

Exits non-zero if a probable credential is found. Public client identifiers
(Firebase Web API key, Turnstile site key, RUM pid) are intentionally redacted
in the stored investigation config, so any remaining match is suspicious.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", "data", "logs"}
SKIP_SUFFIX = {".sqlite3", ".sqlite3-wal", ".sqlite3-shm", ".png", ".pyc"}

PATTERNS = {
    "firebase_api_key": r"AIza[0-9A-Za-z_\-]{35}",
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "jwt": r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}",
    "ga_measurement_secret": r"qplErd_[A-Za-z0-9_\-]{10,}",
    "bearer_value": r"(?i)authorization\s*[:=]\s*[\"']?Bearer\s+[A-Za-z0-9._\-]{12,}",
    "set_cookie_value": r"(?i)set-cookie\s*[:=]\s*[^\n]{0,20}(session|token|auth)",
    "password_assignment": r"(?i)(password|passwd)\s*[:=]\s*[\"'][^\"']{6,}[\"']",
}


def main() -> int:
    findings = []
    files = [p for p in ROOT.rglob("*")
             if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)
             and p.suffix.lower() not in SKIP_SUFFIX]
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pattern in PATTERNS.items():
            for m in re.finditer(pattern, text):
                line = text.count("\n", 0, m.start()) + 1
                findings.append({"file": str(path.relative_to(ROOT)),
                                 "line": line, "type": name,
                                 "match": m.group(0)[:20] + "...[REDACTED]"})
    print(f"scanned {len(files)} files; findings: {len(findings)}")
    for f in findings:
        print(f"  {f['file']}:{f['line']} {f['type']} {f['match']}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
