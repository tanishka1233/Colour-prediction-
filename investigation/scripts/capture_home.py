#!/usr/bin/env python3
"""Capture homepage lottery traffic + storage keys (names only)."""
import json, os, time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
NETB = os.path.join(ROOT, "network", "bodies")
os.makedirs(NETB, exist_ok=True)

def now(): return datetime.now(timezone.utc).isoformat()

recs = []
cons = []
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = b.new_context(
        user_agent="Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        viewport={"width": 390, "height": 844}, locale="en-IN", timezone_id="Asia/Kolkata",
        is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    def on_resp(r):
        try:
            if r.request.resource_type not in ("xhr", "fetch", "websocket", "eventsource"): return
            body = None
            try: body = r.text()
            except Exception: pass
            recs.append({"ts": now(), "url": r.url, "status": r.status, "method": r.request.method,
                         "rtype": r.request.resource_type,
                         "post_data": r.request.post_data,
                         "body": body[:20000] if body else None})
        except Exception as e:
            recs.append({"error": str(e)})
    pg.on("response", on_resp)
    pg.on("console", lambda m: cons.append({"t": m.type, "x": m.text[:500]}))
    pg.goto("https://maanwin29.com/", wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(12000)
    for _ in range(4):
        pg.mouse.wheel(0, 800); pg.wait_for_timeout(1000)
    pg.wait_for_timeout(3000)
    pg.screenshot(path=os.path.join(RAW, "home_initial.png"), full_page=False)
    with open(os.path.join(RAW, "home_dom_text.txt"), "w", encoding="utf-8") as f:
        f.write(pg.inner_text("body"))
    storage = pg.evaluate("""() => {
        const out = {localStorage:{}, sessionStorage:{}, cookies: []};
        for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i);out.localStorage[k]='['+ (localStorage.getItem(k)||'').length +' chars]';}
        for (let i=0;i<sessionStorage.length;i++){const k=sessionStorage.key(i);out.sessionStorage[k]='['+ (sessionStorage.getItem(k)||'').length +' chars]';}
        out.cookies = document.cookie.split(';').map(c=>c.split('=')[0].trim()).filter(Boolean);
        return out;
    }""")
    final_url = pg.url
    # inspect links to game
    links = pg.eval_on_selector_all("a[href]", "els=>els.map(e=>e.getAttribute('href')).filter(h=>h&&/wingo|game/i.test(h)).slice(0,30)")
    b.close()

out = os.path.join(ROOT, "network", "capture_home.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"final_url": final_url, "captured_at": now(), "requests": recs,
               "storage_keys": storage, "game_links": links, "console": cons[:80]}, f, indent=2)

# Save individual lottery bodies
for r in recs:
    if r.get("url") and ("Lottery" in r["url"] or ".json" in r["url"] or "kv/" in r["url"]):
        print("LOTTERY-CALL", r["method"], r["url"], r["status"])
print("final_url:", final_url)
print("saved", out)
