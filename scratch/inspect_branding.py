import re
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent

patterns = [
    re.compile(r"MY AI", re.IGNORECASE),
    re.compile(r"MYAI", re.IGNORECASE),
]

ignore_dirs = {".git", ".system_generated", "brain", "node_modules", ".pytest_cache", "__pycache__", "build", "intermediates"}

print("="*70)
print("SCANNING CODEBASE FOR ALL 'MY AI' / 'MYAI' OCCURRENCES")
print("="*70)

matches_by_file = {}

for p in base_dir.rglob("*"):
    if p.is_file():
        # Check if any parent is in ignore_dirs
        if any(part in ignore_dirs for part in p.parts):
            continue
        if p.suffix in [".png", ".jks", ".apk", ".zip", ".exe", ".dll", ".db", ".jar", ".dex"]:
            continue

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.splitlines(), start=1):
                if re.search(r"MY\s*AI", line, re.IGNORECASE):
                    rel_path = p.relative_to(base_dir).as_posix()
                    if rel_path not in matches_by_file:
                        matches_by_file[rel_path] = []
                    matches_by_file[rel_path].append((i, line))
        except Exception as e:
            pass

for fpath, lines in matches_by_file.items():
    print(f"\n[{fpath}] ({len(lines)} matches):")
    for lno, text in lines[:15]:
        safe_text = text.strip().encode('ascii', 'replace').decode('ascii')
        print(f"  Line {lno:4d}: {safe_text}")
    if len(lines) > 15:
        print(f"  ... and {len(lines) - 15} more lines")

print("\nTotal files with matches:", len(matches_by_file))

