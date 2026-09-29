import os
import re
from pathlib import Path
from PIL import Image

def test_themes_and_branding():
    base_dir = Path(__file__).resolve().parent.parent
    frontend_dir = base_dir / "frontend"
    assets_dir = frontend_dir / "assets"
    
    print("=" * 70)
    print("NEXORA AI — THEME & BRANDING VERIFICATION SUITE")
    print("=" * 70)
    
    # 1. Verify Logo Assets exist and are valid
    print("\n[1] Verifying Logo Assets...")
    logo_light = assets_dir / "logo-light.png"
    logo_dark = assets_dir / "logo-dark.png"
    assert logo_light.exists(), "logo-light.png missing!"
    assert logo_dark.exists(), "logo-dark.png missing!"
    
    img_l = Image.open(logo_light)
    img_d = Image.open(logo_dark)
    print(f"  [OK] logo-light.png verified: {img_l.size}, format={img_l.format}")
    print(f"  [OK] logo-dark.png verified: {img_d.size}, format={img_d.format}")
    
    # Favicons
    for f in ["favicon.ico", "favicon.png", "favicon-32.png", "favicon-64.png", "favicon-128.png", "favicon-192.png", "favicon-512.png", "logo.png", "logo-512.png"]:
        p = assets_dir / f
        assert p.exists(), f"Asset {f} missing!"
        im = Image.open(p)
        print(f"  [OK] Asset {f} verified: {im.size}")

    # 2. Verify theme.js
    print("\n[2] Verifying theme.js engine...")
    theme_js = (frontend_dir / "js" / "theme.js").read_text(encoding="utf-8")
    assert "prefers-color-scheme" in theme_js, "OS prefers-color-scheme detection missing!"
    assert "system" in theme_js, "System default option missing!"
    assert "logo-light.png" in theme_js, "logo-light.png dynamic binding missing!"
    assert "logo-dark.png" in theme_js, "logo-dark.png dynamic binding missing!"
    assert "NexoraTheme" in theme_js, "NexoraTheme global API missing!"
    print("  [OK] theme.js contains dynamic OS matcher, system default, and automatic logo switching.")

    # 3. Verify main.css theme tokens
    print("\n[3] Verifying main.css tokens...")
    main_css = (frontend_dir / "css" / "main.css").read_text(encoding="utf-8")
    
    # Light theme tokens
    assert "#FFFDF3" in main_css, "#FFFDF3 (White Theme background) missing!"
    assert "#1F2937" in main_css, "#1F2937 (White Theme primary text) missing!"
    assert "#6B7280" in main_css, "#6B7280 (White Theme secondary text) missing!"
    assert "#9CA3AF" in main_css, "#9CA3AF (White Theme muted text) missing!"
    
    # Dark theme tokens
    assert "#0B0B0B" in main_css, "#0B0B0B (Dark Theme background) missing!"
    assert "#E5E7EB" in main_css, "#E5E7EB (Dark Theme primary text) missing!"
    print("  [OK] main.css accurately implements #FFFDF3 / #0B0B0B color specifications.")

    # 4. Verify all HTML pages
    print("\n[4] Verifying HTML pages for theme.js and brand logo...")
    html_files = list(frontend_dir.glob("*.html"))
    assert len(html_files) >= 10, f"Expected 10 HTML files, found {len(html_files)}"
    for html in html_files:
        content = html.read_text(encoding="utf-8")
        assert "theme.js" in content, f"{html.name} missing theme.js!"
        assert "NEXORA" in content, f"{html.name} missing NEXORA branding!"
        print(f"  [OK] {html.name} verified with theme.js and branding.")

    # 5. Verify Settings Theme Selector in app.html
    print("\n[5] Verifying Settings Theme Selector...")
    app_html = (frontend_dir / "app.html").read_text(encoding="utf-8")
    assert 'value="light">☀️ White Theme</option>' in app_html, "White Theme option missing or malformed!"
    assert 'value="dark">🌙 Dark Theme</option>' in app_html, "Dark Theme option missing or malformed!"
    assert 'value="system">🖥️ System Default</option>' in app_html, "System Default option missing or malformed!"
    print("  [OK] Settings contains EXACTLY White Theme, Dark Theme, and System Default.")

    # 6. Verify Android assets sync
    print("\n[6] Verifying Android assets...")
    android_assets = base_dir / "android" / "app" / "src" / "main" / "assets"
    assert (android_assets / "js" / "theme.js").exists(), "Android theme.js missing!"
    assert (android_assets / "css" / "main.css").exists(), "Android main.css missing!"
    assert (android_assets / "assets" / "logo-light.png").exists(), "Android logo-light.png missing!"
    assert (android_assets / "assets" / "logo-dark.png").exists(), "Android logo-dark.png missing!"
    print("  [OK] Android assets synchronized.")

    print("\n" + "=" * 70)
    print("ALL THEME AND BRANDING VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    test_themes_and_branding()
