#!/usr/bin/env python3
"""Read-only network + DOM capture for the WinGo 1M page.

Captures all XHR/fetch traffic, console output, and DOM snapshots.
Never clicks betting controls. Saves bodies of JSON responses.
"""
import json, os, sys, time, hashlib
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

URL = "https://maanwin29.com/WinGo/WinGo_1M"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
NET = os.path.join(ROOT, "network", "bodies")
os.makedirs(NET, exist_ok=True)

def now():
    return datetime.now(timezone.utc).isoformat()

records = []
console = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        is_mobile=True,
        has_touch=True,
    )
    page = ctx.new_page()

    def on_request(req):
        try:
            if req.resource_type in ("xhr", "fetch", "websocket", "eventsource"):
                records.append({
                    "ts": now(), "event": "request",
                    "method": req.method,
                    "url": req.url,
                    "resource_type": req.resource_type,
                    "headers": dict(req.headers),
                    "post_data": (req.post_data or None),
                })
        except Exception as e:
            records.append({"ts": now(), "event": "request_error", "error": str(e)})

    def on_response(resp):
        try:
            req = resp.request
            if req.resource_type not in ("xhr", "fetch", "websocket", "eventsource"):
                return
            rec = {
                "ts": now(), "event": "response",
                "url": resp.url, "status": resp.status,
                "method": req.method,
                "resource_type": req.resource_type,
                "request_headers": dict(req.headers),
                "response_headers": dict(resp.headers),
                "post_data": (req.post_data or None),
            }
            body = None
            ct = (resp.headers.get("content-type") or "").lower()
            try:
                body = resp.text()
            except Exception:
                body = None
            if body is not None:
                rec["body_len"] = len(body)
                rec["body_preview"] = body[:1500]
                if ("json" in ct or body.strip()[:1] in "{["):
                    h = hashlib.sha256((resp.url + str(time.time())).encode()).hexdigest()[:12]
                    fn = f"{h}.json"
                    with open(os.path.join(NET, fn), "w", encoding="utf-8") as f:
                        f.write(body)
                    rec["saved_body"] = fn
            records.append(rec)
        except Exception as e:
            records.append({"ts": now(), "event": "response_error", "error": str(e)})

    page.on("request", on_request)
    page.on("response", on_response)
    page.on("console", lambda m: console.append({"ts": now(), "type": m.type, "text": m.text[:2000]}))
    page.on("pageerror", lambda e: console.append({"ts": now(), "type": "pageerror", "text": str(e)[:2000]}))

    print("navigating", URL, flush=True)
    page.goto(URL, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(12000)
    print("title:", page.title(), flush=True)
    page.screenshot(path=os.path.join(RAW, "wingo1m_initial.png"), full_page=False)
    with open(os.path.join(RAW, "wingo1m_dom_text_initial.txt"), "w", encoding="utf-8") as f:
        f.write(page.inner_text("body"))
    with open(os.path.join(RAW, "wingo1m_dom_initial.html"), "w", encoding="utf-8") as f:
        f.write(page.content())

    # Scroll to load lazy content (read-only)
    for i in range(6):
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(1200)
    page.wait_for_timeout(3000)
    page.screenshot(path=os.path.join(RAW, "wingo1m_scrolled.png"), full_page=True)
    with open(os.path.join(RAW, "wingo1m_dom_text_scrolled.txt"), "w", encoding="utf-8") as f:
        f.write(page.inner_text("body"))

    # Inspect candidate tabs/buttons (text only; no clicking yet)
    try:
        btns = page.eval_on_selector_all(
            "button, [role=button], .van-tab, [class*=tab]",
            "els => els.map(e => ({tag:e.tagName, cls:e.className, text:(e.innerText||'').trim().slice(0,80)})).filter(x=>x.text)"
        )
    except Exception as e:
        btns = [{"error": str(e)}]
    with open(os.path.join(RAW, "wingo1m_buttons.json"), "w", encoding="utf-8") as f:
        json.dump(btns, f, indent=2)
    print("buttons found:", len(btns), flush=True)

    page.wait_for_timeout(4000)
    browser.close()

out = os.path.join(ROOT, "network", "capture_initial.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"url": URL, "captured_at": now(), "records": records, "console": console}, f, indent=2)
print("saved", out, "records:", len(records), "console:", len(console))
