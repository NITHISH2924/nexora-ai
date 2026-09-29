import os
import shutil
from pathlib import Path

def sync_assets():
    base_dir = Path(__file__).resolve().parent.parent
    frontend_dir = base_dir / "frontend"
    android_assets = base_dir / "android" / "app" / "src" / "main" / "assets"

    android_assets.mkdir(parents=True, exist_ok=True)

    # Copy CSS
    shutil.copytree(frontend_dir / "css", android_assets / "css", dirs_exist_ok=True)

    # Copy JS
    shutil.copytree(frontend_dir / "js", android_assets / "js", dirs_exist_ok=True)

    # Copy Assets (images, logos, favicons)
    if (frontend_dir / "assets").exists():
        shutil.copytree(frontend_dir / "assets", android_assets / "assets", dirs_exist_ok=True)

    # Copy HTML files
    for html_file in frontend_dir.glob("*.html"):
        shutil.copy2(html_file, android_assets / html_file.name)

    print("[PASS] Synchronized frontend files and assets to Android assets folder.")

if __name__ == "__main__":
    sync_assets()
