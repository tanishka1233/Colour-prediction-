#!/usr/bin/env python3
"""Read-only collector for WinGo_1M public result feed.

- Conditional GETs (ETag) of the public history snapshot (last 10 draws), every 30 s.
- Polls the public current-period snapshot every 15 s for transition timing.
- Upserts unique period records into CSV/JSON, preserving provenance.
- Never authenticates, never bets.
"""
import csv, json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)
CSV = os.path.join(DATA, "wingo_1m_history.csv")
JSONF = os.path.join(DATA, "wingo_1m_history.json")
OBS = os.path.join(DATA, "observation_log.jsonl")

HIST = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
CUR = "https://draw.ar-lottery01.com/WinGo/WinGo_1M.json"
UA = "HMXPredictor-Research/0.1 (read-only investigation; contact: local)"

FIELDS = ["period_id", "result_number", "result_colour", "result_size",
          "result_timestamp", "source_url", "retrieved_at", "verification_status"]

def now_iso(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def fetch(url, etag=None, timeout=20):
    h = {"User-Agent": UA, "Accept": "application/json,*/*"}
    if etag: h["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, b""

def derive(number):
    n = int(number)
    colours = []
    if n in (0, 5):
        colours = ["red", "violet"] if n == 0 else ["green", "violet"]
    elif n in (1, 2, 3, 4):
        colours = ["red"]
    else:
        colours = ["green"]
    return ",".join(colours), ("Big" if n > 4 else "Small")

def load_existing():
    recs = []
    if os.path.exists(JSONF):
        try: recs = json.load(open(JSONF, encoding="utf-8"))
        except Exception: recs = []
    return {r["period_id"]: r for r in recs}

def save(records):
    ordered = sorted(records.values(), key=lambda r: r["period_id"])
    with open(JSONF, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2)
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    return len(ordered)

def main(duration_s=1800):
    recs = load_existing()
    etag = None
    start = time.time()
    last_issue = None
    n = 0
    while time.time() - start < duration_s:
        started = time.time()
        # 1) history snapshot
        try:
            status, hdrs, body = fetch(HIST, etag=etag)
            obs = {"ts": now_iso(), "kind": "history", "http": status,
                   "etag": hdrs.get("ETag"), "last_modified": hdrs.get("Last-Modified")}
            if status == 200 and body:
                etag = hdrs.get("ETag") or etag
                d = json.loads(body.decode("utf-8"))
                items = d.get("data", {}).get("list", [])
                obs["count"] = len(items)
                obs["first"] = items[0]["issueNumber"] if items else None
                obs["meta"] = {k: d.get("data", {}).get(k) for k in ("pageNo", "totalPage", "totalCount")}
                for it in items:
                    pid = it["issueNumber"]
                    num = int(it["number"])
                    colour, size = derive(num)
                    # cross-check server colour against derived colour
                    srv = (it.get("color") or "").lower()
                    if srv and srv != colour:
                        status_v = f"COLOUR_MISMATCH(server={srv})"
                    else:
                        status_v = "verified_public_feed"
                    if pid not in recs:
                        recs[pid] = {
                            "period_id": pid,
                            "result_number": num,
                            "result_colour": colour,
                            "result_size": size,
                            "result_timestamp": "",
                            "source_url": HIST,
                            "retrieved_at": now_iso(),
                            "verification_status": status_v,
                            "_server_colour": srv,
                            "_premium": it.get("premium"),
                            "_sum": it.get("sum"),
                        }
                        print("NEW", pid, num, colour, size, flush=True)
            with open(OBS, "a", encoding="utf-8") as f:
                f.write(json.dumps(obs) + "\n")
        except Exception as e:
            with open(OBS, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": now_iso(), "kind": "history_error", "error": str(e)}) + "\n")
        # 2) current snapshot (transition observation)
        try:
            status, hdrs, body = fetch(CUR)
            if status == 200 and body:
                c = json.loads(body.decode("utf-8"))
                cur = c.get("current", {})
                obs = {"ts": now_iso(), "kind": "current", "http": status,
                       "issue": cur.get("issueNumber"), "start_ms": cur.get("startTime"),
                       "end_ms": cur.get("endTime"), "interval": c.get("intervalMinute"),
                       "last_modified": hdrs.get("Last-Modified")}
                if last_issue and cur.get("issueNumber") != last_issue:
                    obs["transition_from"] = last_issue
                    print("TRANSITION", last_issue, "->", cur.get("issueNumber"), flush=True)
                last_issue = cur.get("issueNumber")
                with open(OBS, "a", encoding="utf-8") as f:
                    f.write(json.dumps(obs) + "\n")
        except Exception as e:
            pass
        total = save(recs)
        n += 1
        elapsed = time.time() - started
        time.sleep(max(2, 30 - elapsed))
    print("done. total records:", save(recs), "cycles:", n)

if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
    main(dur)
