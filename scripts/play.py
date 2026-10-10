#!/usr/bin/env python3
"""Reusable playthrough script — plays the cube game in the browser and prints the board.

    uv run python scripts/play.py [--moves 40] [--delay 0.4]

Reuses tests/browser_lib.py (Chrome over CDP, visible tab).
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from browser_lib import (  # noqa: E402
    open_game, wait_idle, read_state, hud, click_cube, find_group, clickable, idx, N,
)

LETTERS = "RGBPOAW"   # palette order in the game


def show_layers(page, cells):
    """Print the cube as N front-to-back slices (y up, x right)."""
    for z in range(N - 1, -1, -1):
        print(f"  slice z={z}")
        for y in range(N - 1, -1, -1):
            row = []
            for x in range(N):
                c = cells[idx(page, x, y, z)]
                row.append("." if c is None else LETTERS[c])
            print("   " + " ".join(row))
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--moves", type=int, default=40)
    ap.add_argument("--delay", type=float, default=0.4, help="sleep between moves (seconds)")
    ap.add_argument("--name", default="cube-colors-play")
    args = ap.parse_args()

    page = open_game(name=args.name)
    s = wait_idle(page)

    for i in range(args.moves):
        cands = clickable(page)
        if not cands:
            break
        # play the biggest group that is actually clickable
        best = max(cands, key=lambda c: len(find_group(page, c)))
        g = find_group(page, best)
        if len(g) < 2:
            break
        click_cube(page, best)          # select
        time.sleep(args.delay)
        s = wait_idle(page)
        click_cube(page, best)          # pop
        time.sleep(args.delay)
        s = wait_idle(page)
        print(f"move {i + 1}: popped {len(g)} (cube {best}) -> score {s['score']}, cubes {s['cubes']}, chain {s['mult']:.1f}x")
        show_layers(page, s["cells"])

    print("final:", hud(page))
    return 0


if __name__ == "__main__":
    sys.exit(main())
