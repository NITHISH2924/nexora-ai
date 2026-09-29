import os
import math
from pathlib import Path
from PIL import Image, ImageDraw

def draw_myai_icon(size: int, round_icon: bool = False) -> Image.Image:
    # 4x supersampling for ultra crisp anti-aliasing
    scale = 4
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background gradient / dark rounded rect or circle
    r = canvas_size // 2 if round_icon else int(canvas_size * 0.22)
    # Draw background
    if round_icon:
        draw.ellipse([0, 0, canvas_size - 1, canvas_size - 1], fill=(11, 11, 18, 255))
    else:
        draw.rounded_rectangle([0, 0, canvas_size - 1, canvas_size - 1], radius=r, fill=(11, 11, 18, 255))

    # Outer border ring
    border_color = (139, 92, 246, 120)
    if round_icon:
        draw.ellipse([scale*2, scale*2, canvas_size - 1 - scale*2, canvas_size - 1 - scale*2], outline=border_color, width=scale*2)
    else:
        draw.rounded_rectangle([scale*2, scale*2, canvas_size - 1 - scale*2, canvas_size - 1 - scale*2], radius=r-scale*2, outline=border_color, width=scale*2)

    # 2. Glowing Neural Octagon
    cx, cy = canvas_size / 2, canvas_size / 2
    oct_r = canvas_size * 0.35
    oct_pts = []
    for i in range(8):
        angle = math.radians(i * 45 + 22.5)
        oct_pts.append((cx + oct_r * math.cos(angle), cy + oct_r * math.sin(angle)))
    oct_pts.append(oct_pts[0])
    draw.line(oct_pts, fill=(6, 182, 212, 180), width=scale*3)

    # 3. Four-point Spark / Star Core
    spark_len = canvas_size * 0.28
    spark_width = canvas_size * 0.08
    
    # Draw vertical & horizontal diamond lobes
    spark_poly = [
        (cx, cy - spark_len),
        (cx + spark_width, cy),
        (cx, cy + spark_len),
        (cx - spark_width, cy),
    ]
    draw.polygon(spark_poly, fill=(167, 139, 250, 255))

    spark_poly_h = [
        (cx - spark_len, cy),
        (cx, cy - spark_width),
        (cx + spark_len, cy),
        (cx, cy + spark_width),
    ]
    draw.polygon(spark_poly_h, fill=(139, 92, 246, 255))

    # Center white quantum pulse
    core_r = canvas_size * 0.08
    draw.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r], fill=(255, 255, 255, 255))
    inner_dot = canvas_size * 0.035
    draw.ellipse([cx - inner_dot, cy - inner_dot, cx + inner_dot, cy + inner_dot], fill=(167, 139, 250, 255))

    # Downsample with Lanczos for smooth antialiased output
    return img.resize((size, size), Image.Resampling.LANCZOS)

def generate_all_icons(base_res_dir: Path):
    densities = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192
    }
    for folder, size in densities.items():
        target_dir = base_res_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        icon = draw_myai_icon(size, round_icon=False)
        icon.save(target_dir / "ic_launcher.png", format="PNG")

        round_icon = draw_myai_icon(size, round_icon=True)
        round_icon.save(target_dir / "ic_launcher_round.png", format="PNG")
        print(f"[OK] Generated {folder} icons ({size}x{size}px)")

if __name__ == "__main__":
    res_dir = Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "res"
    generate_all_icons(res_dir)
