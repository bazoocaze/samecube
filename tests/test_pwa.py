#!/usr/bin/env python3
"""PWA checks — no browser needed, the criteria are static.

    uv run python tests/test_pwa.py

Checks the installability criteria Chromium requires (name, 192 + 512 icons,
start_url, display), that the icons on disk match the sizes the manifest
declares, that index.html references the manifest, and that the service worker
is registered only on a real origin (the game must still open from file://).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = []

def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)

html = (ROOT / "index.html").read_text()
manifest = json.loads((ROOT / "manifest.webmanifest").read_text())
sw = (ROOT / "sw.js").read_text()

print("manifest")
check(manifest.get("name") or manifest.get("short_name"), "name or short_name present")
check(manifest.get("start_url"), f"start_url ({manifest.get('start_url')})")
check(manifest.get("display") in ("standalone", "fullscreen", "minimal-ui"), f"display ({manifest.get('display')})")
check(not manifest.get("prefer_related_applications"), "prefer_related_applications absent")
check(manifest.get("scope", "./") in (".", "./"), f"scope covers the page ({manifest.get('scope')})")

sizes = {i.get("sizes") for i in manifest.get("icons", [])}
check("192x192" in sizes, "manifest declares a 192x192 icon")
check("512x512" in sizes, "manifest declares a 512x512 icon")
check(any(i.get("purpose") == "maskable" for i in manifest.get("icons", [])), "a maskable icon is declared")

print("\nicons on disk match the manifest")
try:
    from PIL import Image
    have_pil = True
except ImportError:
    have_pil = False
    print("  skip (Pillow not installed — run: uv pip install pillow)")

for icon in manifest.get("icons", []):
    p = ROOT / icon["src"]
    if not p.exists():
        check(False, f"{icon['src']} exists")
        continue
    check(True, f"{icon['src']} exists")
    if have_pil:
        w, h = Image.open(p).size
        check((w, h) == tuple(int(v) for v in icon["sizes"].split("x")), f"{icon['src']} is {icon['sizes']} (got {w}x{h})")

print("\nindex.html")
check('rel="manifest"' in html and 'href="manifest.webmanifest"' in html, "links the manifest")
check('rel="apple-touch-icon"' in html, "links an apple-touch-icon (iOS)")
check("theme-color" in html, "theme-color meta present")

print("\nservice worker")
check(bool(re.search(r"addEventListener\(['\"]install['\"]", sw)), "sw.js handles install")
check(bool(re.search(r"addEventListener\(['\"]activate['\"]", sw)), "sw.js handles activate")
check(bool(re.search(r"addEventListener\(['\"]fetch['\"]", sw)), "sw.js handles fetch (offline)")
check("Response.error()" in sw, "fetch never throws on a miss")
for u in re.findall(r"'(\./[^']*)'", sw):
    if u.endswith(".png"):
        check((ROOT / u).exists(), f"precached asset {u}")

# The test harness opens index.html over file://, where a service worker cannot
# be registered; the registration must be guarded so the game still runs.
check(re.search(r"location\.protocol === 'https:'", html), "service worker registered only on a real origin")
check("beforeinstallprompt" in html, "install prompt is captured for an in-page Install button")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED"))
sys.exit(1 if fails else 0)
