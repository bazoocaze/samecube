#!/usr/bin/env python3
"""Black-box browser test for the Cubes clone (Chrome over CDP, visible tab).

    uv run python tests/test_game.py

Checks: test hook, picking, pixel render, two-click select/pop through the real
UI, gravity, rotation (never triggers gravity), undo, game over, HUD, localStorage.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_lib import (  # noqa: E402
    open_game, wait_idle, read_state, hud, screen_pos, pick_face, pick_cube, topmost_cube,
    pixel_at, parse_rgb, nearest_palette, is_shade, largest_group, find_group, idx, xyz, click_cube,
    hover_cube, rotate, compact_columns, multiset, clickable, N,
)

fails = []
def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)

def set_board(page, js_fn):
    """js_fn is a JS source string like '(x, y, z) => ...' applied to the live board."""
    page.evaluate(
        """(src) => {
          const g = window.cubegame, N = g.cfg.N, fn = eval(src);
          for (let x = 0; x < N; x++) for (let y = 0; y < N; y++) for (let z = 0; z < N; z++)
            g.state.cells[g.idx(x, y, z)] = fn(x, y, z);
          g.state.sel = []; g.state.hover = -1; g.state.over = false; g.state.chain = 0; g.state.dirty = true;
        }""",
        js_fn,
    )

def click_until(page, i, cond, tries=3):
    """Click until the condition holds (input events can be dropped by CDP)."""
    for _ in range(tries):
        c = click_cube(page, i)
        if cond(read_state(page)):
            return c
    return c


page = open_game()
s = wait_idle(page)

print("hook + initial board")
check(s["phase"] == "idle", f"phase is idle ({s['phase']})")
check(s["cubes"] == N ** 3, f"125 cubes at start ({s['cubes']})")
check(hud(page)["left"] == str(s["cubes"]), f"HUD 'left' matches state ({hud(page)['left']})")

print("\npicking + render (painter order)")
cands = clickable(page, min_group=0)
check(len(cands) > 0, f"some cubes are clickable ({len(cands)} of {s['cubes']})")
if cands:
    i = cands[0]
    p = screen_pos(page, i)
    f = pick_face(page, p["x"], p["y"])
    check(f is not None and f["cube"] == i, f"pick at cube {i} returns cube {i} (got {f and f['cube']})")
    if f:
        px = pixel_at(page, p["x"], p["y"])
        want = parse_rgb(f["fill"])
        d = sum((a - b) ** 2 for a, b in zip(px, want))
        check(d < 900, f"pixel at cube {i} equals the face fill the painter draws there {want} vs {px} (d={d})")
        pal, dist = nearest_palette(px)
        check(is_shade(px, s["cells"][i]), f"that pixel is the cube's palette colour scaled by the face shade ({s['cells'][i]}, nearest reads {pal} d={dist})")

print("\ntwo-click select / pop through the UI (deterministic board)")
set_board(page, "(x, y, z) => (x >= N - 2 && y >= N - 2 && z >= N - 2) ? 0 : 1")   # 8-block at the corner nearest the camera
wait_idle(page)
s = read_state(page)
check(s["cubes"] == N ** 3, f"board set: {s['cubes']} cubes")
cands = [i for i in clickable(page) if len(find_group(page, i)) == 8]
check(len(cands) > 0, f"a cube of the 8-block is clickable ({len(cands)})")
if cands:
    target = cands[0]
    g = find_group(page, target)
    p = screen_pos(page, target)
    check(pick_cube(page, p["x"], p["y"]) == target, f"the target cube is clickable (pick returns {target})")
    hover_cube(page, target)
    page.wait_for_timeout(200)
    check(read_state(page)["hover"] == target, f"hover tracks the cube under the cursor ({read_state(page)['hover']})")
    click_until(page, target, lambda s: len(s["sel"]) == 8)
    s = read_state(page)
    check(sorted(s["sel"]) == sorted(g), f"click 1 selected the whole group ({len(s['sel'])} of {len(g)})")
    check(s["phase"] == "idle" and s["score"] == 0, "click 1 only selects, it does not pop")
    check("8 selected" in hud(page)["hintline"], f"HUD hint shows the selection ({hud(page)['hintline']})")
    click_until(page, target, lambda s: s["cubes"] == N ** 3 - 8)
    s = read_state(page)
    check(s["score"] == 8 * 7, f"click 2 popped: score {s['score']} (expected 56)")
    check(s["cubes"] == N ** 3 - 8, f"cubes left {s['cubes']} == {N**3 - 8}")
    check(s["mult"] == 1.5, f"chain grew to {s['mult']:.1f}x")
    check(hud(page)["score"] == str(s["score"]), f"HUD score matches state ({hud(page)['score']})")
    check(hud(page)["chain"] == "1.5×", f"HUD chain shows the multiplier ({hud(page)['chain']})")
    check(hud(page)["left"] == str(s["cubes"]), f"HUD 'left' matches state ({hud(page)['left']})")
    compact_columns(page, "after pop")
    check(True, "gravity: every column is compact after a pop")

print("\nrotation must not trigger gravity")
set_board(page, "(x, y, z) => (x === 0 && z === 0) ? (y === 0 ? null : 0) : 1")   # hole at the floor, cubes floating above it
bag = multiset(page)
float_i = idx(page, 0, 3, 0)
color = read_state(page)["cells"][float_i]
rotate(page, "y", 1)
wait_idle(page)
s = read_state(page)
check(multiset(page) == bag, "rotation preserved the colour multiset")
check(s["cubes"] == len(bag), f"rotation preserved the cube count ({s['cubes']})")
check(s["cells"][idx(page, 0, 3, N - 1)] == color, f"floating cube moved with the column to (0,3,{N - 1})")
check(s["cells"][idx(page, 0, 0, N - 1)] is None, "rotation did NOT compact the column (no gravity)")

print("\nundo")
set_board(page, "(x, y, z) => 0")
wait_idle(page)
page.evaluate("() => window.cubegame.state.chain = 3")
score_before, cubes_before = read_state(page)["score"], read_state(page)["cubes"]
c = clickable(page)[0]
click_until(page, c, lambda s: len(s["sel"]) == N ** 3)
click_until(page, c, lambda s: s["cubes"] < cubes_before)
after = read_state(page)
check(after["cubes"] < cubes_before, f"popped a group for the undo test ({cubes_before} -> {after['cubes']})")
page.evaluate("() => window.cubegame.undo()")
wait_idle(page)
s = read_state(page)
check(s["cubes"] == cubes_before, f"undo restored the cubes ({s['cubes']})")
check(s["score"] == score_before, f"undo restored the score ({s['score']})")
check(s["chain"] == 3, f"undo restored the chain ({s['chain']})")
compact_columns(page, "undo")
check(True, "gravity invariant holds after undo")

print("\ncontrols")
page.evaluate("() => window.cubegame.newGame()")
wait_idle(page)
bag = multiset(page)
page.evaluate("() => document.getElementById('rotR').click()")
wait_idle(page)
check(multiset(page) == bag, "rotation button preserves the multiset")
page.evaluate("() => document.getElementById('btnShuffle').click()")
wait_idle(page)
check(multiset(page) == bag, "shuffle button preserves the multiset")
page.evaluate("() => document.getElementById('btnSound').click()")
check("off" in page.evaluate("() => document.getElementById('btnSound').textContent"), "sound toggle turns off")
page.evaluate("() => document.getElementById('btnSound').click()")
check("on" in page.evaluate("() => document.getElementById('btnSound').textContent"), "sound toggle turns back on")
page.evaluate("() => document.getElementById('btnNew').click()")
wait_idle(page)
s = read_state(page)
check(s["cubes"] == N ** 3 and s["score"] == 0, f"new game button resets the board ({s['cubes']} cubes, score {s['score']})")
page.evaluate("() => window.cubegame.state.cells[window.cubegame.idx(0, 0, 0)] = null")
bag = multiset(page)
page.keyboard.press("ArrowRight")
wait_idle(page)
check(multiset(page) == bag, "keyboard rotation preserves the multiset")
check(read_state(page)["cells"][idx(page, 0, 0, N - 1)] is None, "keyboard rotation kept the gap (no gravity)")
c = clickable(page)
if c:
    click_until(page, c[0], lambda s: len(s["sel"]) > 0)
    before = read_state(page)["cubes"]
    click_until(page, c[0], lambda s: s["cubes"] < before)
    page.evaluate("() => document.getElementById('btnUndo').click()")
    wait_idle(page)
    check(read_state(page)["cubes"] == before, f"undo button restored the popped cubes ({before} -> {read_state(page)['cubes']})")

print("\ngame over")
set_board(page, "(x, y, z) => (x + y + z) % 2")   # every group is a single cube
page.evaluate("() => window.cubegame.checkOver()")
s = read_state(page)
check(s["over"], "checkerboard (all groups of 1) is detected as game over")
check("No moves left" in hud(page)["hintline"], f"HUD reports game over ({hud(page)['hintline']})")

print("\npersistence")
page.evaluate("() => { const g = window.cubegame; g.state.score = 4242; g.state.best = 0; g.state.over = false; g.checkOver(); }")
page.reload(); page.bring_to_front(); page.wait_for_timeout(900)
s = read_state(page)
check(s["best"] == 4242, f"best survives a reload ({s['best']})")

print()
if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("ALL CHECKS PASSED")
