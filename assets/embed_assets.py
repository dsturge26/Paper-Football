#!/usr/bin/env python3
"""Inline the Blender renders into index.html as base64 data URIs.

The game stays a single self-contained file: this script replaces the block
between the ASSETS markers in index.html with a fresh `const ASSETS = {...}`
built from assets/renders/.

Usage:  python3 assets/embed_assets.py
"""
import base64
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDERS = os.path.join(ROOT, "assets", "renders")
HTML = os.path.join(ROOT, "index.html")

START = "/* __BLENDER_ASSETS_START__ */"
END = "/* __BLENDER_ASSETS_END__ */"

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}

# on-screen sizes are small, so sprites can shed pixels before embedding
MAX_SIZE = {"bump": 256, "tok": 192, "trophy": 256}


def optimize_png(stem, data):
    """Downscale to in-game size and palette-quantize (needs Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        return data
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    limit = next((v for k, v in MAX_SIZE.items() if stem.startswith(k)), None)
    if limit and max(im.size) > limit:
        im.thumbnail((limit, limit), Image.LANCZOS)
    q = im.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    buf = io.BytesIO()
    q.save(buf, "PNG", optimize=True)
    out = buf.getvalue()
    return out if len(out) < len(data) else data


def main():
    entries = []
    total = 0
    for fn in sorted(os.listdir(RENDERS)):
        stem, ext = os.path.splitext(fn)
        if ext not in MIME:
            continue
        with open(os.path.join(RENDERS, fn), "rb") as f:
            data = f.read()
        if ext == ".png":
            data = optimize_png(stem, data)
        total += len(data)
        b64 = base64.b64encode(data).decode("ascii")
        entries.append(f'{stem}:"data:{MIME[ext]};base64,{b64}"')
        print(f"  {fn}: {len(data)//1024} KB")
    print(f"total embedded: {total//1024} KB from {len(entries)} files")

    block = START + "\nconst ASSETS={" + ",\n".join(entries) + "};\n" + END

    with open(HTML, "r", encoding="utf-8") as f:
        html = f.read()
    if START not in html or END not in html:
        sys.exit("markers not found in index.html — add them before running")
    html = re.sub(
        re.escape(START) + ".*?" + re.escape(END),
        lambda _: block,
        html,
        flags=re.S,
    )
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html updated")


if __name__ == "__main__":
    main()
