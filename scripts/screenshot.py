#!/usr/bin/env python3
"""Screenshot the Cubes clone in a visible Chrome tab.

    uv run python scripts/screenshot.py [--out tests/screenshot.png] [--moves 12]

Reuses tests/browser_lib.py (Chrome over CDP via the browser-control skill).
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from browser_lib import open_game, wait_idle, read_state, clickable, find_group, click_cube, hover_cube  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "tests" / "screenshot.png"))
    ap.add_argument("--moves", type=int, default=12)
    ap.add_argument("--delay", type=float, default=0.35)
    ap.add_argument("--name", default="cube-colors-shot")
    args = ap.parse_args()

    page = open_game(name=args.name)
    s = wait_idle(page)

    for _ in range(args.moves):
        cands = clickable(page)
        if not cands:
            break
        i = max(cands, key=lambda c: len(find_group(page, c)))
        click_cube(page, i)          # select
        time.sleep(args.delay)
        s = wait_idle(page)
        click_cube(page, i)          # pop
        time.sleep(args.delay)
        s = wait_idle(page)

    # hover + select the biggest clickable group so the highlight shows in the shot
    cands = clickable(page)
    if cands:
        i = max(cands, key=lambda c: len(find_group(page, c)))
        hover_cube(page, i)
        time.sleep(0.2)
        click_cube(page, i)
        time.sleep(0.3)

    page.screenshot(path=args.out)
    print(f"saved {args.out} (score {s['score']}, cubes {s['cubes']}, chain {s['mult']:.1f}x)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
