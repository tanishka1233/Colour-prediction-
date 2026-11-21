#!/usr/bin/env python3
"""Backfill latest public snapshot and re-normalise all WinGo_1M records.

Colour rule is derived from the site's own `color` field and frontend code:
  odd 1,3,5,7,9 -> green ; even 0,2,4,6,8 -> red ; 0 adds violet ; 5 adds violet.
Size rule from frontend: number > 4 -> Big else Small.
Period timestamp is DERIVED from the verified period-ID schedule and labelled.
"""
import csv, json, os, urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
JSONF = os.path.join(DATA, "wingo_1m_history.json")
CSV = os.path.join(DATA, "wingo_1m_history.csv")
HIST = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
FIELDS = ["period_id", "result_number", "result_colour", "result_size",
          "result_timestamp", "source_url", "retrieved_at", "verification_status"]

def now_iso(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def derive(n):
    n = int(n)
    if n == 0: return "red,violet", "Small"
    if n == 5: return "green,violet", "Big"
    return ("green" if n % 2 else "red"), ("Big" if n > 4 else "Small")

def period_end(period_id):
    """YYYYMMDD + 1000 + 1 + SSSS ; SSSS = 0-based UTC minute index = endTime minute."""
    date_part = period_id[:8]
    seq = int(period_id[-4:])
    end = datetime.strptime(date_part, "%Y%m%d").replace(tzinfo=timezone.utc) + timedelta(minutes=seq)
    return end.isoformat().replace("+00:00", "Z")

def load():
    if os.path.exists(JSONF):
        data = json.load(open(JSONF, encoding="utf-8"))
        items = data.get("records", []) if isinstance(data, dict) else data
        return {r["period_id"]: r for r in items}
    return {}

def main():
    recs = load()
    # one-shot backfill of the current public snapshot
    req = urllib.request.Request(HIST, headers={"User-Agent": "HMXPredictor-Research/0.1"})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode())
    meta = {k: d["data"].get(k) for k in ("pageNo", "totalPage", "totalCount")}
    for it in d["data"]["list"]:
        pid = it["issueNumber"]
        rec = recs.setdefault(pid, {})
        rec.update({
            "period_id": pid,
            "result_number": int(it["number"]),
            "_server_colour": (it.get("color") or "").lower(),
            "_premium": it.get("premium"),
            "_sum": it.get("sum"),
            "source_url": HIST,
            "retrieved_at": rec.get("retrieved_at") or now_iso(),
        })
    # re-normalise everything
    for pid, rec in recs.items():
        num = rec["result_number"]
        colour, size = derive(num)
        rec["result_colour"] = colour
        rec["result_size"] = size
        rec["result_timestamp"] = period_end(pid)
        srv = rec.get("_server_colour", "")
        ok = (not srv) or srv == colour
        rec["verification_status"] = (
            "verified_public_feed; timestamp_derived_from_period_id" if ok
            else f"COLOUR_MISMATCH(server={srv}); timestamp_derived_from_period_id"
        )
    ordered = sorted(recs.values(), key=lambda r: r["period_id"])
    with open(JSONF, "w", encoding="utf-8") as f:
        json.dump({"meta": {"totalCount_metadata": meta.get("totalCount"),
                            "totalPage_metadata": meta.get("totalPage"),
                            "public_snapshot_size": len(d["data"]["list"]),
                            "note": "Only latest 10 are publicly retrievable; totalCount is authenticated-API metadata."},
                   "records": ordered}, f, indent=2)
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print("records:", len(ordered), "first:", ordered[0]["period_id"], "last:", ordered[-1]["period_id"])
    print("colour mismatches:", sum("MISMATCH" in r["verification_status"] for r in ordered))

if __name__ == "__main__":
    main()
