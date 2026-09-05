# Blender asset pipeline

The game's sprites and field textures are 3D renders produced with Blender
(Cycles, CPU) and inlined into `index.html` as base64 data URIs, so the game
stays a single self-contained file.

## Files

- `blender_assets.py` — models and renders everything into `renders/`:
  - `ball_*.png` — the themed footballs (folded paper triangle, unicorn horn,
    rocket, lollipop, spiky dino ball)
  - `bump_*.png` — the themed bumpers (football, rainbow, ringed planet,
    wrapped candy, speckled egg)
  - `tok_pos.png` / `tok_neg.png` — floating-point coins
  - `trophy.png` — win-screen trophy
  - `field_*.jpg` — themed turf backgrounds
- `embed_assets.py` — quantizes/downscales the renders and rewrites the
  `ASSETS` block between the `__BLENDER_ASSETS__` markers in `index.html`.

## Regenerating

```sh
pip install bpy pillow          # Blender as a Python module + image optimizer
python3 assets/blender_assets.py            # render everything (~2 min on CPU)
ONLY=field python3 assets/blender_assets.py # or just a subset, by name match
python3 assets/embed_assets.py              # re-inline into index.html
```

`blender -b --factory-startup -P assets/blender_assets.py -- assets/renders`
works too if you have the Blender binary instead of the pip module.

The game falls back to the original CSS/emoji art for any asset missing from
the `ASSETS` object, so a partially regenerated set still runs.
