# Project Context

## Description

A SameGame (Clickomania) variant played on a **5×5×5 cube** instead of a 2D grid.
Single-file game (`index.html`, no dependencies, no build step), plus a Python/Playwright
test harness that drives the real page through an already-installed Chrome over CDP.

Live demo: [bazoocaze.github.io/samecube](https://bazoocaze.github.io/samecube/)

Game rules (the contract — do not change without being asked):

- Group = all orthogonally connected same-colour cubes (6 neighbours), **including hidden ones**.
- Only cubes with a visible face are clickable.
- Click 1 selects, click 2 on the same cube pops the group; minimum group size is 2.
- Gravity is world-down and runs **only after a destruction**. Rotation never compacts a column,
  so floating clusters persist until something pops in their column.
- Rotation is a 90° snap around the world X or Y axis (not free rotation), animated.
- Score `n × (n − 1) × chain`, chain multiplier `1.0 → 1.5 → 2.0 …` per consecutive pop;
  re-selecting a different group resets the chain. Clearing the board: `+2000`.
- Best score persists in `localStorage`. Undo, shuffle, sound, game-over detection included.

## Structure

```
index.html          # the whole game (IIFE, ~770 lines)
pyproject.toml      # playwright only
scripts/play.py     # automated playthrough, prints cube slices
scripts/screenshot.py
tests/browser_lib.py  # shared helpers (Chrome over CDP, visible tab)
tests/test_game.py    # black-box browser test
tests/logic_test.js   # deterministic logic test, no browser
```

## Conventions

- Keep `index.html` self-contained: no external libraries, no bundler, no assets.
- Keep the `window.cubegame` test hook in sync with anything the tests read
  (`state`, `cfg`, `PALETTE`, `FILL`, `pick`, `pickFace`, `render`, `screenPos`, `idx`, `xyz`,
  `findGroup`, `largestGroup`, `hasMove`, `cubesLeft`, `exposed`, `popGroup`, `gravity`,
  `rotate`, `commitRotation`, `undo`, `shuffle`, `pointsFor`, `chainMult`, `clickCube`,
  `checkOver`, `hud`).
- Tests are black-box: assert through the hook and through rendered pixels, not by re-implementing
  game logic in Python.
- Deterministic boards (`set_board`) are preferred over random ones for click/score assertions.
- The browser tab must stay **visible** during tests (user requirement).

## Invariants the tests enforce

1. After a pop, every column `(x, z)` is compact — no cube above a gap.
2. Rotation preserves the colour multiset and the cube count, and does **not** compact.
3. `rotIndex` (the permutation applied on commit) must match the animation matrix:
   `y` axis → `(x,y,z) → (z, y, N-1-x)`, `x` axis → `(x,y,z) → (x, z, N-1-y)`.
4. Score formula and chain growth; undo restores cells/score/chain.
5. Game over when no group ≥ 2 exists among **exposed** cubes.
6. The pixel at a cube's centre equals the fill the painter draws there (painter order =
   whole-cube depth, far first).
7. `pointInPoly` must use the **even-odd rule** (toggle `inside`), not "any crossing": picking at
   the centroid of every rendered face must return the cube that owns that face.
8. On a viewport narrower than 760px the panels stack (menus above the cube) and the projected
   cube must fit inside the canvas.

## Known harness gotchas (learned the hard way)

- `pick`/`pickFace` read `state.faces`, which is only refreshed by a render — helpers force a
  render (`refresh()`) before comparing with a pixel read.
- `screenPos` recomputes the camera matrix but does not update `state.faces`; both must be from
  the same state or picks disagree.
- Playwright dispatches integer CSS px for mouse events; rounding the point before clicking is
  required, otherwise a face-adjacent point resolves to a different cube.
- The canvas CSS height must fit the viewport (`min(560px, calc(100vh - 24px))`); a stale canvas
  size after a window resize makes clicks land outside the canvas. `refit()` dispatches a resize.
- Face shading multiplies all channels by one scalar, so "nearest palette colour" is unreliable —
  use `is_shade()` (channel ratios) instead.
- Input events only reach the active tab; helpers call `bring_to_front()`.
- A second click on a cube of the **already selected group** pops it. A per-cube click test must
  use one cube per group (or check for a pop) — otherwise it measures a pop, not a selection.

## Running

```bash
uv venv && uv pip install playwright
node tests/logic_test.js
uv run python tests/test_game.py
uv run python scripts/play.py --moves 40
uv run python scripts/screenshot.py --moves 14
```

Both suites must pass before publishing.
