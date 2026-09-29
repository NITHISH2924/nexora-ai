import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.app.main import app

pages = [
    ('/', 'NEXORA AI — One AI. Everything you need.', 'One AI. Everything you need.'),
    ('/login', 'Sign In — NEXORA AI', 'NEXORA AI'),
    ('/signup', 'Create Account — NEXORA AI', 'NEXORA AI'),
    ('/forgot-password', 'Forgot Password — NEXORA AI', 'NEXORA AI'),
    ('/reset-password', 'Reset Password — NEXORA AI', 'NEXORA AI'),
    ('/verify-email', 'Verify Email — NEXORA AI', 'NEXORA AI'),
    ('/app', 'NEXORA AI — One AI. Everything you need.', 'NEXORA'),
    ('/admin', 'NEXORA AI — One AI. Everything you need.', 'Platform Owner Administration'),
    ('/privacy', 'Privacy Policy — NEXORA AI', 'NEXORA AI'),
    ('/terms', 'Terms of Service — NEXORA AI', 'NEXORA AI'),
    ('/delete-account', 'Delete Account — NEXORA AI', 'NEXORA AI')
]

print('='*70)
print('VERIFYING ALL LIVE HTTP PAGES FOR NEXORA AI BRANDING & ROUTING')
print('='*70)

with TestClient(app) as client:
    for path, expected_title, expected_content in pages:
        response = client.get(path)
        assert response.status_code == 200, f"Failed route {path} with status {response.status_code}"
        html = response.text
        assert expected_title in html, f'Title mismatch for {path}: expected {expected_title}'
        assert expected_content in html, f'Content mismatch for {path}: expected {expected_content}'
        
        # Check that no visible MY AI remains
        assert 'MY AI' not in html, f'Legacy MY AI found in {path}'
        print(f'[PASS] {path:20} -> 200 OK | Verified: "{expected_title}"')

print('='*70)
print('ALL 11 WEB ROUTES CONFIRMED 100% CLEAN OF LEGACY BRANDING & ACCESSIBLE!')
print('='*70)
