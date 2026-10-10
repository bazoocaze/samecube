"""Reusable browser helpers for the Cubes clone.

Connects to the already-installed Chrome over CDP through the browser-control
skill (no Playwright browser download needed), opens index.html, and exposes
black-box helpers that read the cube from the game itself (window.cubegame) and
sample canvas pixels.

    from tests.browser_lib import open_game
    page = open_game()
    s = read_state(page)

The browser is forced visible (BROWSER_CONTROL_HEADLESS=false): a hidden tab
throttles requestAnimationFrame and the render loop stalls, so pixel checks
would read a stale canvas.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("BROWSER_CONTROL_HEADLESS", "false")

ROOT = Path(__file__).resolve().parent.parent
URL = f"file://{ROOT / 'index.html'}"
TAB = "cube-colors"

sys.path.insert(0, str(Path.home() / ".agents/skills/browser-control"))
from lib import generic_open  # noqa: E402

N = 5
PALETTE = ["#e8434f", "#45c86a", "#3f7ee6", "#f2b8d0", "#eef2f6", "#f7a13b"]

STATE = """() => {
  const g = window.cubegame;
  return {
    cells: g.state.cells, phase: g.state.phase, score: g.state.score, best: g.state.best,
    moves: g.state.moves, chain: g.state.chain, over: g.state.over,
    sel: g.state.sel, hover: g.state.hover, cubes: g.cubesLeft(), mult: g.chainMult(),
  };
}"""

HUD = """() => ({
  score: document.getElementById('score').textContent,
  best: document.getElementById('best').textContent,
  chain: document.getElementById('chain').textContent,
  left: document.getElementById('left').textContent,
  hintline: document.getElementById('hintline').textContent,
})"""

PICK_FACE = """([x, y]) => {
  const f = window.cubegame.pickFace(x, y);
  return f ? { cube: f.cube, fill: f.fill, depth: f.depth } : null;
}"""

PIXEL = """([x, y]) => {
  const c = document.getElementById('board');
  const ctx = c.getContext('2d');
  const dpr = c.width / (c.clientWidth || 1);
  const d = ctx.getImageData(Math.round(x * dpr), Math.round(y * dpr), 1, 1).data;
  return [d[0], d[1], d[2]];
}"""


def open_game(name=TAB, fresh=True):
    """Open (or reuse) the game tab in a visible browser and foreground it."""
    page = generic_open(URL, name=name)
    page.bring_to_front()
    page.wait_for_selector("#board")
    if fresh:
        page.reload()
        page.bring_to_front()
    page.wait_for_timeout(900)
    return page


def wait_idle(page, timeout_ms=6000, poll_ms=120):
    """Wait until the game reaches its idle phase (animations applied).
    Polls sparsely so it does not spin the CPU."""
    deadline = timeout_ms
    while deadline > 0:
        s = read_state(page)
        if s["phase"] == "idle":
            return s
        page.wait_for_timeout(poll_ms)
        deadline -= poll_ms
    return read_state(page)


def read_state(page):
    return page.evaluate(STATE)


def hud(page):
    return page.evaluate(HUD)


def refit(page):
    """Re-run the game's canvas fit (the window may have resized after load)."""
    page.evaluate("() => window.dispatchEvent(new Event('resize'))")


def canvas_rect(page):
    refit(page)
    return page.evaluate(
        "() => { const r = document.getElementById('board').getBoundingClientRect();"
        " return { left: r.left, top: r.top, width: r.width, height: r.height }; }"
    )


def refresh(page):
    """Force a render so state.faces is current (picking depends on it)."""
    page.evaluate("() => { const g = window.cubegame; g.state.dirty = true; g.render(performance.now()); }")


def screen_pos(page, i):
    """Cube centre on the canvas: canvas-relative CSS px + absolute page px."""
    refit(page)
    refresh(page)
    p = page.evaluate(f"window.cubegame.screenPos({i})")
    r = canvas_rect(page)
    return {"x": p["x"], "y": p["y"], "depth": p["depth"], "absX": round(r["left"] + p["x"]), "absY": round(r["top"] + p["y"])}


def click_cube(page, i):
    """Click a cube. Coordinates are rounded to whole CSS px so the game's pick
    sees exactly the point we verified, and the tab is foregrounded first
    (CDP input events only reach the active tab). Returns the cube the game
    actually picked at that point — a cube is only clickable when its own face
    is topmost there.
    """
    page.bring_to_front()
    p = screen_pos(page, i)
    c = pick_cube(page, p["x"], p["y"])
    for _ in range(3):                      # make sure events reach the page
        page.mouse.move(p["absX"], p["absY"])
        page.wait_for_timeout(120)
        if read_state(page)["hover"] == c:
            break
    page.mouse.click(p["absX"], p["absY"])
    page.wait_for_timeout(150)
    return c


def hover_cube(page, i):
    page.bring_to_front()
    p = screen_pos(page, i)
    page.mouse.move(p["absX"], p["absY"])
    return page


def face_probe(page, min_group=2):
    """A point provably on a clickable cube's own face: the centroid of a rendered face
    that pickFace attributes to that cube. Cube centres are often occluded on a full
    board, so they are not a reliable click point.
    """
    return page.evaluate("""(minGroup) => {
      const g = window.cubegame; g.render(performance.now());
      const r = document.getElementById('board').getBoundingClientRect();
      for (const f of g.state.faces) {
        if (g.findGroup(f.cube).length < minGroup) continue;
        const p = f.pts;
        const x = (p[0].x + p[2].x) / 2, y = (p[0].y + p[2].y) / 2;
        const top = g.pickFace(x, y);
        if (top && top.cube === f.cube) return { cube: f.cube, x, y, absX: r.left + x, absY: r.top + y };
      }
      return null;
    }""", min_group)


def drag_at(page, x, y, dx, dy, touch=False, steps=6):
    """Press at (x, y), move by (dx, dy) CSS px, release — the game's tap/swipe split.
    Touch goes through CDP because Playwright's touchscreen API has no drag gesture.
    """
    page.bring_to_front()
    x, y = round(x), round(y)
    if touch:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        for k in range(1, steps + 1):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints":
                  [{"x": x + dx * k // steps, "y": y + dy * k // steps}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    else:
        page.mouse.move(x, y)
        page.mouse.down()
        for k in range(1, steps + 1):
            page.mouse.move(x + dx * k // steps, y + dy * k // steps)
        page.mouse.up()
    page.wait_for_timeout(150)


def drag(page, i, dx, dy, touch=False):
    p = screen_pos(page, i)
    return drag_at(page, p["absX"], p["absY"], dx, dy, touch=touch)


def pick_face(page, x, y):
    """Topmost face at canvas-relative CSS px (painter order)."""
    refresh(page)
    return page.evaluate(PICK_FACE, [x, y])


def pick_cube(page, x, y):
    """Cube actually under a canvas-relative point (what a click would hit)."""
    refresh(page)
    return page.evaluate("([x, y]) => window.cubegame.pickFace(x, y)?.cube ?? -1", [x, y])


def topmost_cube(page, i):
    """Cube i is only clickable when its own face is topmost at its centre."""
    p = screen_pos(page, i)
    return pick_cube(page, p["x"], p["y"])


def pixel_at(page, x, y):
    """Sample one canvas pixel at canvas-relative CSS px."""
    return page.evaluate(PIXEL, [x, y])


def parse_rgb(s):
    parts = s.replace("rgb(", "").replace(")", "").split(",")
    return [int(v) for v in parts]


def nearest_palette(rgb):
    best, bd = -1, 1e9
    for i, p in enumerate(PALETTE):
        pr, pg, pb = int(p[1:3], 16), int(p[3:5], 16), int(p[5:7], 16)
        d = (pr - rgb[0]) ** 2 + (pg - rgb[1]) ** 2 + (pb - rgb[2]) ** 2
        if d < bd:
            bd, best = d, i
    return best, bd


def is_shade(rgb, color):
    """True if rgb is the palette colour scaled by one shade factor (face shading
    multiplies all channels by the same scalar, so nearest-palette is unreliable)."""
    p = PALETTE[color]
    pr, pg, pb = int(p[1:3], 16), int(p[3:5], 16), int(p[5:7], 16)
    s = (pr * rgb[0] + pg * rgb[1] + pb * rgb[2]) / (pr * pr + pg * pg + pb * pb)
    res = sum((rgb[i] - c) ** 2 for i, c in enumerate((pr * s, pg * s, pb * s))) ** 0.5
    return s > 0.05 and res < 12


def exposed(page, i):
    return page.evaluate(f"window.cubegame.exposed({i})")


def largest_group(page):
    return page.evaluate("() => window.cubegame.largestGroup()")


def find_group(page, i):
    return page.evaluate(f"() => window.cubegame.findGroup({i})")


def idx(page, x, y, z):
    return page.evaluate(f"window.cubegame.idx({x},{y},{z})")


def xyz(page, i):
    return page.evaluate(f"() => window.cubegame.xyz({i})")


def compact_columns(page, tag="board"):
    """After gravity, every column is compact: a cube rests on the floor or on
    another cube. Rotation alone must never enforce this."""
    cells = read_state(page)["cells"]
    for x in range(N):
        for z in range(N):
            expect = 0
            for y in range(N):
                if cells[idx(page, x, y, z)] is None:
                    continue
                if y != expect:
                    raise AssertionError(f"{tag}: floating cube at ({x},{y},{z})")
                expect += 1
    return True


def multiset(page):
    return sorted(c for c in read_state(page)["cells"] if c is not None)


def rotate(page, axis, direction):
    key = {"y": {-1: "ArrowLeft", 1: "ArrowRight"}, "x": {-1: "ArrowDown", 1: "ArrowUp"}}[axis][direction]
    page.keyboard.press(key)
    return page


def show_cube(page):
    """ASCII slice: one block per z layer, rows = y (top first), cols = x."""
    cells = read_state(page)["cells"]
    for z in range(N - 1, -1, -1):
        for y in range(N - 1, -1, -1):
            print(" ".join("." if cells[idx(page, x, y, z)] is None else str(cells[idx(page, x, y, z)]) for x in range(N)))
        print()


def clickable(page, min_group=2):
    """Cubes whose own face is topmost at their centre (i.e. actually clickable)."""
    s = read_state(page)
    out = []
    for i in range(N ** 3):
        if s["cells"][i] is None:
            continue
        p = screen_pos(page, i)
        if pick_cube(page, p["x"], p["y"]) == i and (min_group <= 0 or len(find_group(page, i)) >= min_group):
            out.append(i)
    return out
