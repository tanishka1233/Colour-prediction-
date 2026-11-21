#!/usr/bin/env python3
"""Observe WinGo_1M period transitions and result publication timing (read-only)."""
import json, os, time, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "transition_samples.jsonl")
CUR = "https://draw.ar-lottery01.com/WinGo/WinGo_1M.json"
HIST = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
KV = "https://maanwin29.com/webapi/kv/issue/WinGo_1M"

def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
        "Accept": "application/json,*/*",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def ts(): return datetime.now(timezone.utc).isoformat()

start = time.time()
last_issue = None
last_hist_first = None
n = 0
with open(OUT, "w", encoding="utf-8") as f:
    while time.time() - start < 480:
        t0 = ts()
        try:
            cur = get(CUR)
            f.write(json.dumps({"ts": t0, "kind": "current", "data": cur}) + "\n"); f.flush()
            iss = cur.get("current", {}).get("issueNumber")
            if last_issue and iss != last_issue:
                f.write(json.dumps({"ts": ts(), "kind": "TRANSITION", "from": last_issue, "to": iss,
                                    "new_start_ms": cur.get("current", {}).get("startTime")}) + "\n"); f.flush()
                print("TRANSITION", last_issue, "->", iss, flush=True)
            last_issue = iss
        except Exception as e:
            f.write(json.dumps({"ts": t0, "kind": "error_current", "error": str(e)}) + "\n"); f.flush()
        if n % 3 == 0:
            try:
                h = get(HIST)
                f.write(json.dumps({"ts": ts(), "kind": "history", "data": h}) + "\n"); f.flush()
                first = h.get("data", {}).get("list", [{}])[0].get("issueNumber")
                if last_hist_first and first != last_hist_first:
                    f.write(json.dumps({"ts": ts(), "kind": "NEW_RESULT", "issue": first}) + "\n"); f.flush()
                    print("NEW_RESULT", first, flush=True)
                last_hist_first = first
            except Exception as e:
                f.write(json.dumps({"ts": ts(), "kind": "error_hist", "error": str(e)}) + "\n"); f.flush()
        if n % 12 == 0:
            try:
                kv = get(KV)
                f.write(json.dumps({"ts": ts(), "kind": "kv", "data": kv}) + "\n"); f.flush()
            except Exception as e:
                f.write(json.dumps({"ts": ts(), "kind": "error_kv", "error": str(e)}) + "\n"); f.flush()
        n += 1
        time.sleep(5)
print("done", n, "samples")
