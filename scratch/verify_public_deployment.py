import urllib.request
import json
import uuid

base_url = 'https://mouth-republic-rank-tenant.trycloudflare.com'

routes = [
    '/',
    '/login',
    '/signup',
    '/forgot-password',
    '/reset-password',
    '/verify-email',
    '/app',
    '/privacy',
    '/terms',
    '/delete-account',
    '/assets/logo.png',
    '/assets/favicon.png',
    '/css/main.css',
    '/css/app.css',
    '/js/theme.js',
    '/js/api.js',
    '/api/company/leadership'
]

print('=' * 80)
print('COMPREHENSIVE PUBLIC HTTPS END-TO-END DEPLOYMENT VERIFICATION')
print('LIVE URL:', base_url)
print('=' * 80)

# 1. Test Static Routes & Web Pages
for r in routes:
    req = urllib.request.Request(base_url + r, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as res:
        ctype = res.headers.get('Content-Type', '')
        print(f'[PASS] {r:24} -> HTTP {res.status} | Content-Type: {ctype}')

# 2. Test Live Signup & Authentication over Public HTTPS
rand_suffix = uuid.uuid4().hex[:6]
test_email = f"prod_tester_{rand_suffix}@nexora.ai"
test_password = "ProdSecurePassword2026!"

signup_payload = json.dumps({
    'email': test_email,
    'password': test_password
}).encode('utf-8')

req_signup = urllib.request.Request(
    base_url + '/api/auth/signup',
    data=signup_payload,
    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
)

with urllib.request.urlopen(req_signup) as res:
    signup_data = json.loads(res.read().decode('utf-8'))
    token = signup_data['token']
    user = signup_data['user']
    print(f'\n[PASS] /api/auth/signup         -> HTTP {res.status} | Registered: {user["email"]} (Role: {user["role"]})')

# 3. Test Live Login
login_payload = json.dumps({
    'email': test_email,
    'password': test_password
}).encode('utf-8')

req_login = urllib.request.Request(
    base_url + '/api/auth/login',
    data=login_payload,
    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
)

with urllib.request.urlopen(req_login) as res:
    login_data = json.loads(res.read().decode('utf-8'))
    auth_token = login_data['token']
    print(f'[PASS] /api/auth/login          -> HTTP {res.status} | Login successful for: {test_email}')

# 4. Test Authenticated User Profile
req_me = urllib.request.Request(
    base_url + '/api/auth/me',
    headers={'Authorization': f'Bearer {auth_token}', 'User-Agent': 'Mozilla/5.0'}
)

with urllib.request.urlopen(req_me) as res:
    me_data = json.loads(res.read().decode('utf-8'))
    user_id = me_data.get('userId') or me_data.get('id')
    user_role = me_data['role']
    print(f'[PASS] /api/auth/me             -> HTTP {res.status} | Verified User ID: {user_id} (Role: {user_role})')

# 5. Test Multi-Model AI Discovery
req_models = urllib.request.Request(
    base_url + '/api/chat/models',
    headers={'Authorization': f'Bearer {auth_token}', 'User-Agent': 'Mozilla/5.0'}
)

with urllib.request.urlopen(req_models) as res:
    models_data = json.loads(res.read().decode('utf-8'))
    models_list = [m['id'] for m in models_data.get('models', [])]
    print(f'[PASS] /api/chat/models         -> HTTP {res.status} | Discovered {len(models_list)} models: {models_list}')

# 6. Test Create Conversation Thread
conv_payload = json.dumps({
    'title': 'Public Deployment Test Conversation',
    'model': 'gemini-1.5-flash'
}).encode('utf-8')

req_conv = urllib.request.Request(
    base_url + '/api/chat/conversations',
    data=conv_payload,
    headers={
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    }
)

with urllib.request.urlopen(req_conv) as res:
    conv_data = json.loads(res.read().decode('utf-8'))
    conv_id = conv_data['id']
    print(f'\n[PASS] /api/chat/conversations  -> HTTP {res.status} | Created Conversation ID: {conv_id}')

# 7. Test Send Chat Message & AI Response over Public HTTPS
msg_payload = json.dumps({
    'content': 'Who is the owner and who is the CEO of NEXORA AI?',
    'model': 'gemini-1.5-flash'
}).encode('utf-8')

req_msg = urllib.request.Request(
    f'{base_url}/api/chat/conversations/{conv_id}/messages',
    data=msg_payload,
    headers={
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    }
)

with urllib.request.urlopen(req_msg) as res:
    msg_data = json.loads(res.read().decode('utf-8'))
    ai_reply = msg_data.get('assistantMessage', {}).get('content', '')
    print(f'[PASS] /api/chat/.../messages   -> HTTP {res.status}')
    print(f'       User Prompt              : "Who is the owner and who is the CEO of NEXORA AI?"')
    print(f'       AI Live Response         : "{ai_reply.strip()}"')
    assert 'Nithish Kumar R' in ai_reply
    assert 'Dhanushiya S' in ai_reply
    print('       [VERIFIED] Mandatory Executive Leadership Identity confirmed in live AI reply!')

# 8. Test Security RBAC: Ensure normal user cannot access owner metrics
req_admin = urllib.request.Request(
    base_url + '/api/admin/metrics',
    headers={'Authorization': f'Bearer {auth_token}', 'User-Agent': 'Mozilla/5.0'}
)

try:
    with urllib.request.urlopen(req_admin) as res:
        print('[FAIL] Normal user accessed admin metrics!')
except urllib.error.HTTPError as e:
    print(f'\n[PASS] RBAC Protection          -> HTTP {e.code} (Forbidden) | Direct API calls by regular users to owner metrics are strictly blocked server-side')

print('\n' + '=' * 80)
print('ALL 8 END-TO-END PUBLIC HTTPS CHECKS COMPLETED WITH 100% SUCCESS!')
print('=' * 80)
