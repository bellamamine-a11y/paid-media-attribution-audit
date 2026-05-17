"""
assets/create_placeholder.py

Creates a placeholder dashboard screenshot for the README.
Replace with a real screenshot or GIF after deploying.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(__file__).parent / "README_dashboard.png"

W, H = 1280, 720
img = Image.new("RGB", (W, H), color="#0f172a")
draw = ImageDraw.Draw(img)

# Header bar
draw.rectangle([0, 0, W, 72], fill="#1e293b")
draw.text((32, 22), "Paid Media Attribution Audit | Marble & Co", fill="#f8fafc", font=None)

# KPI tiles
tile_labels = [
    ("Total Spend", "$263,400"),
    ("Revenue (attr.)", "$748,200"),
    ("Blended ROAS", "2.84x"),
    ("Cost / Purchase", "$38.20"),
    ("Purchases", "6,900"),
    ("Unattributed", "3,150"),
]
tile_w, tile_h = 180, 80
tile_y = 100
for i, (label, value) in enumerate(tile_labels):
    x = 32 + i * (tile_w + 16)
    draw.rectangle([x, tile_y, x + tile_w, tile_y + tile_h], fill="#1e3a5f")
    draw.text((x + 10, tile_y + 10), label, fill="#94a3b8", font=None)
    draw.text((x + 10, tile_y + 36), value, fill="#38bdf8", font=None)

# Fake chart area: channel performance
chart_y = 220
draw.rectangle([32, chart_y, W - 32, chart_y + 280], fill="#1e293b")
draw.text((48, chart_y + 12), "Channel Performance: ROAS vs ATC Rate", fill="#94a3b8", font=None)

bar_data = [
    ("Brand Search", 0.92, "#1a56db"),
    ("Non-Brand",    0.72, "#7e3af2"),
    ("Shopping",     0.82, "#0694a2"),
    ("Perf. Max",    0.28, "#e3a008"),
    ("Prospecting",  0.18, "#ff5a1f"),
    ("Retargeting",  0.70, "#31c48d"),
]
bar_max_h = 180
bar_w = 110
bar_base_y = chart_y + 260
for i, (name, pct, color) in enumerate(bar_data):
    bx = 80 + i * (bar_w + 20)
    bh = int(bar_max_h * pct)
    draw.rectangle([bx, bar_base_y - bh, bx + bar_w, bar_base_y], fill=color)
    draw.text((bx + 8, bar_base_y + 6), name, fill="#94a3b8", font=None)

# Annotation stripe
draw.rectangle([0, chart_y + 192, W, chart_y + 196], fill="#ef4444")
draw.text((500, chart_y + 200), "Tracking fix 2024-03-01", fill="#ef4444", font=None)

# Footer
draw.rectangle([0, H - 36, W, H], fill="#1e293b")
draw.text(
    (32, H - 22),
    "TODO: Replace this placeholder with a real GIF recording of the dashboard.",
    fill="#64748b",
    font=None,
)

img.save(OUT)
print(f"Placeholder saved to {OUT}")
