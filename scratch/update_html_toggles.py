import glob
import re

html_files = glob.glob('frontend/*.html')
for f in html_files:
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    
    # Replace old toggle titles
    content = content.replace('Switch to Black & White Theme', 'Switch to Black Theme')
    content = content.replace('Toggle Dark / Light Theme', 'Switch to Black Theme')
    
    # Ensure default icon state matches White theme (showing Moon icon to switch to Black theme)
    content = re.sub(
        r'<span class="theme-icon-dark"\s*(style="[^"]*")?>🌙</span>\s*<span class="theme-icon-light"\s*(style="[^"]*")?>☀️</span>',
        '<span class="theme-icon-dark">🌙</span>\n      <span class="theme-icon-light" style="display:none;">☀️</span>',
        content
    )

    with open(f, 'w', encoding='utf-8') as fh:
        fh.write(content)
    print(f'Updated {f}')
