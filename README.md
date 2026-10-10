# Cubes

SameGame played on a **5×5×5 cube** — a single HTML file, no dependencies.
MIT licensed — [live demo](https://bazoocaze.github.io/samecube/).

```
cube_colors/
├── index.html            # the game
├── pyproject.toml        # playwright (uv venv)
├── scripts/
│   ├── play.py           # automated playthrough (prints the cube slices)
│   └── screenshot.py     # screenshot of the game
└── tests/
    ├── browser_lib.py    # reusable helpers (Chrome over CDP, visible tab)
    ├── test_game.py      # black-box browser test
    ├── logic_test.js     # deterministic logic test (no browser)
    └── screenshot.png
```

## Rules

- **First click** selects the connected group of **2+ cubes** of the same colour
  (orthogonal adjacency, 6 neighbours — the group includes hidden cubes).
- **Second click** on the same group destroys it; cubes above fall down (gravity is
  world-down, applied only after a destruction).
- Only **visible** cubes can be clicked; a hidden cube joins the group when it becomes exposed.
- **Rotating** (left/right, up/down, 90° snap) **never** triggers gravity: floating clusters
  stay where they are until a destruction happens in their column.
- Score for a group of `n`: `n × (n − 1) × chain`, where `chain` grows `1.0 → 1.5 → 2.0 …`
  per consecutive destruction (re-selecting a different group resets the chain).
  Clearing the cube: `+2000` bonus.
- Best score is kept in `localStorage`.

Extras: undo, shuffle, sound (WebAudio), hover with a `n · points` badge, particles,
pop animations, keyboard `← → ↑ ↓` (rotate) and `N U S M`.

## Run

Open `index.html` in a browser.

## Tests

Uses the already-installed Chrome over CDP (the `browser-control` skill) — it does not
download a browser, and the tab is kept **visible**.

```bash
uv venv && uv pip install playwright

node tests/logic_test.js          # multiset, gravity, score/chain, undo, shuffle, game over
uv run python tests/test_game.py  # plays through the browser: pick, render, HUD, buttons, persistence
uv run python scripts/play.py --moves 40 --delay 0.4
uv run python scripts/screenshot.py --moves 14 --out tests/screenshot.png
```

Harness notes:
- `tests/browser_lib.py` exposes `open_game`, `read_state`, `hud`, `screen_pos`, `pick_face`,
  `pick_cube`, `click_cube`, `hover_cube`, `rotate`, `find_group`, `largest_group`,
  `compact_columns`, `multiset`, `clickable`, `wait_idle`.
- The game exposes `window.cubegame` (test hook) so state, picking and the drawn face fill can
  be read without sampling pixels.
- `pick` depends on `state.faces` (the last render), so `screen_pos`/`pick_face` force a render
  before comparing, and `refit()` re-applies the canvas fit if the window changed size.
- Click coordinates are rounded to whole CSS px, otherwise the exact cube-centre point can land
  on a neighbouring face.
- The tab must be foregrounded (`bring_to_front`), otherwise Chrome throttles
  `requestAnimationFrame` and the render loop stops.

Bugs found by the tests: inverted camera pitch sign (top faces were culled and bottom faces
drawn), canvas taller than the viewport (clicks landed outside it), fractional click
coordinates landing on the wrong face, and stale `state.faces` between pick and pixel read.

## License

[MIT](LICENSE) — the code is yours, use, modify and redistribute it freely.
