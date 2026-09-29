import re

def main():
    with open('frontend/css/app.css', 'r', encoding='utf-8') as f:
        css = f.read()

    # Replace hardcoded dark or light values with CSS variables
    replacements = [
        ('background: rgba(14, 14, 24, 0.6);', 'background: var(--bg-input);'),
        ('background: rgba(11, 11, 18, 0.5);', 'background: var(--bg-sidebar);'),
        ('background: rgba(11, 11, 18, 0.75);', 'background: var(--glass-bg);'),
        ('background: rgba(17, 17, 27, 0.85);', 'background: var(--bg-card);'),
        ('background: rgba(19, 19, 31, 0.6);', 'background: var(--bg-card-subtle);'),
        ('background: rgba(14, 14, 24, 0.4);', 'background: var(--bg-card-subtle);'),
        ('background: #08080E;', 'background: var(--bg-card-subtle);'),
        ('background: #0D0D17;', 'background: var(--bg-card-subtle);'),
        ('background: #11111C;', 'background: var(--bg-card-subtle);'),
        ('border: 1px solid rgba(255, 255, 255, 0.1);', 'border: 1px solid var(--color-border);'),
        ('border: 1px solid rgba(255, 255, 255, 0.08);', 'border: 1px solid var(--color-border);'),
        ('border: 1px solid rgba(255, 255, 255, 0.15);', 'border: 1px solid var(--color-border);'),
        ('background: rgba(255, 255, 255, 0.05);', 'background: var(--bg-card-subtle);'),
    ]

    for old, new in replacements:
        css = css.replace(old, new)

    # Truncate old light theme adaptations and replace with comprehensive light & dark theme adaptations
    light_sec_marker = '/* ==========================================================================\n   OFFICIAL LIGHT THEME'
    if light_sec_marker in css:
        css = css[:css.index(light_sec_marker)]

    adaptations = """/* ==========================================================================
   OFFICIAL THEME COMPONENT ADAPTATIONS (/app)
   ========================================================================== */

/* --- 1. WHITE THEME ADAPTATIONS (#FFFDF3 Ivory) --- */
[data-theme="light"] .app-layout {
  background-color: #FFFDF3;
}

[data-theme="light"] .app-sidebar {
  background-color: #F9F7EE;
  border-right: 1px solid #E5E7EB;
}

[data-theme="light"] .sidebar-header {
  border-bottom: 1px solid #E5E7EB;
}

[data-theme="light"] .sidebar-header .brand-title {
  color: #1F2937;
}

[data-theme="light"] .btn-new-chat {
  background: #1F2937;
  border: 1px solid #1F2937;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(31, 41, 55, 0.15);
}

[data-theme="light"] .btn-new-chat:hover {
  background: #111827;
  border-color: #111827;
  color: #FFFFFF;
}

[data-theme="light"] .sidebar-search-box input {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  color: #1F2937;
}

[data-theme="light"] .sidebar-search-box input::placeholder {
  color: #9CA3AF;
}

[data-theme="light"] .nav-section-title {
  color: #9CA3AF;
}

[data-theme="light"] .nav-item {
  color: #6B7280;
}

[data-theme="light"] .nav-item svg {
  color: #9CA3AF;
}

[data-theme="light"] .nav-item:hover {
  background-color: #EDE9DC;
  color: #1F2937;
}

[data-theme="light"] .nav-item:hover svg {
  color: #1F2937;
}

[data-theme="light"] .nav-item.active {
  background: #EDE9DC;
  color: #1F2937;
  border-color: #E5E7EB;
  font-weight: 600;
}

[data-theme="light"] .nav-item.active svg {
  color: #1F2937;
}

[data-theme="light"] .chat-history-item {
  color: #6B7280;
}

[data-theme="light"] .chat-history-item:hover {
  background-color: #EDE9DC;
  color: #1F2937;
}

[data-theme="light"] .chat-history-item.active {
  background: #EDE9DC;
  color: #1F2937;
  border-color: #E5E7EB;
}

[data-theme="light"] .chat-history-item.active .chat-item-title {
  color: #1F2937;
  font-weight: 600;
}

[data-theme="light"] .sidebar-footer {
  background: #F9F7EE;
  border-top: 1px solid #E5E7EB;
}

[data-theme="light"] .user-snippet:hover {
  background: #EDE9DC;
}

[data-theme="light"] .user-email-text {
  color: #1F2937;
}

[data-theme="light"] .app-topbar {
  background: rgba(255, 253, 243, 0.95);
  border-bottom: 1px solid #E5E7EB;
}

[data-theme="light"] .active-conversation-title {
  color: #1F2937;
}

[data-theme="light"] .model-select-btn {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  color: #1F2937;
}

[data-theme="light"] .model-select-btn:hover {
  background: #F8F6EB;
}

[data-theme="light"] .model-dropdown-menu {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  box-shadow: 0 10px 35px rgba(0, 0, 0, 0.08);
}

[data-theme="light"] .model-option-item:hover {
  background: #F8F6EB;
}

[data-theme="light"] .model-option-item.active {
  background: #F6F4E8;
  border-color: #E5E7EB;
}

[data-theme="light"] .view-header h2,
[data-theme="light"] .empty-state-title {
  color: #1F2937;
}

[data-theme="light"] .empty-state-subtitle {
  color: #6B7280;
}

[data-theme="light"] .prompt-starter-card {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

[data-theme="light"] .prompt-starter-card:hover {
  background: #FAF8F0;
  border-color: #D1D5DB;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
}

[data-theme="light"] .starter-title {
  color: #1F2937;
}

[data-theme="light"] .starter-desc {
  color: #6B7280;
}

[data-theme="light"] .message-sender-name {
  color: #1F2937;
}

[data-theme="light"] .message-time {
  color: #9CA3AF;
}

[data-theme="light"] .user-row .message-bubble {
  background: #F3F0E6;
  border: 1px solid #E5E7EB;
  color: #1F2937;
}

[data-theme="light"] .assistant-row .message-bubble {
  color: #1F2937;
}

[data-theme="light"] .assistant-row .message-bubble h1,
[data-theme="light"] .assistant-row .message-bubble h2,
[data-theme="light"] .assistant-row .message-bubble h3,
[data-theme="light"] .assistant-row .message-bubble h4 {
  color: #1F2937;
}

[data-theme="light"] .code-block-wrapper {
  background: #F8F6EB;
  border: 1px solid #E5E7EB;
}

[data-theme="light"] .code-block-header {
  background: #F1EFE3;
  border-bottom: 1px solid #E5E7EB;
  color: #6B7280;
}

[data-theme="light"] .chat-composer-container {
  background: linear-gradient(180deg, rgba(255, 253, 243, 0) 0%, rgba(255, 253, 243, 0.95) 40%, #FFFDF3 100%);
}

[data-theme="light"] .composer-card {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

[data-theme="light"] .composer-card:focus-within {
  border-color: #9CA3AF;
  box-shadow: 0 6px 25px rgba(0, 0, 0, 0.08);
}

[data-theme="light"] .composer-input-area textarea {
  color: #1F2937;
}

[data-theme="light"] .composer-input-area textarea::placeholder {
  color: #9CA3AF;
}

[data-theme="light"] .btn-send-message {
  background: #1F2937;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(31, 41, 55, 0.2);
}

[data-theme="light"] .btn-send-message:hover {
  background: #111827;
}

[data-theme="light"] .modal-card,
[data-theme="light"] .modal-card-large,
[data-theme="light"] .modal-content {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.1);
  color: #1F2937;
}

[data-theme="light"] .modal-title {
  color: #1F2937;
}

[data-theme="light"] .project-card,
[data-theme="light"] .image-preview-card,
[data-theme="light"] .vision-output-card,
[data-theme="light"] .settings-card,
[data-theme="light"] .stat-card,
[data-theme="light"] .owner-metric-card,
[data-theme="light"] .tool-studio-card {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
}

[data-theme="light"] .project-card:hover,
[data-theme="light"] .stat-card:hover {
  background: #FAF8F0;
  border-color: #D1D5DB;
}

[data-theme="light"] .project-title,
[data-theme="light"] .project-card-title,
[data-theme="light"] .project-note-title,
[data-theme="light"] .project-item-title,
[data-theme="light"] .search-source-title {
  color: #1F2937;
}

[data-theme="light"] .project-desc,
[data-theme="light"] .project-card-desc,
[data-theme="light"] .project-note-content {
  color: #6B7280;
}

[data-theme="light"] .search-large-input {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  color: #1F2937;
}

[data-theme="light"] .search-large-input::placeholder {
  color: #9CA3AF;
}

[data-theme="light"] .files-dropzone,
[data-theme="light"] .image-preview-stage,
[data-theme="light"] .vision-output-body,
[data-theme="light"] .image-gen-stage,
[data-theme="light"] .gen-gallery-card,
[data-theme="light"] .project-output-card {
  background: #F8F6EB;
  border: 1px solid #E5E7EB;
}

[data-theme="light"] .admin-table th {
  background: #F8F6EB;
  color: #4B5563;
  border-bottom: 1px solid #E5E7EB;
}

[data-theme="light"] .admin-table td {
  border-bottom: 1px solid #F1EFE3;
  color: #1F2937;
}


/* --- 2. DARK THEME ADAPTATIONS (#0B0B0B Black) --- */
[data-theme="dark"] .app-layout {
  background-color: #0B0B0B;
}

[data-theme="dark"] .app-sidebar {
  background-color: #0E0E0E;
  border-right: 1px solid #1F2937;
}

[data-theme="dark"] .sidebar-header {
  border-bottom: 1px solid #1F2937;
}

[data-theme="dark"] .sidebar-header .brand-title {
  color: #E5E7EB;
}

[data-theme="dark"] .btn-new-chat {
  background: #E5E7EB;
  border: 1px solid #E5E7EB;
  color: #0B0B0B;
  box-shadow: 0 2px 10px rgba(255, 255, 255, 0.08);
}

[data-theme="dark"] .btn-new-chat:hover {
  background: #FFFFFF;
  border-color: #FFFFFF;
  color: #0B0B0B;
}

[data-theme="dark"] .sidebar-search-box input {
  background: #161616;
  border: 1px solid #1F2937;
  color: #E5E7EB;
}

[data-theme="dark"] .sidebar-search-box input::placeholder {
  color: #6B7280;
}

[data-theme="dark"] .nav-section-title {
  color: #6B7280;
}

[data-theme="dark"] .nav-item {
  color: #9CA3AF;
}

[data-theme="dark"] .nav-item svg {
  color: #6B7280;
}

[data-theme="dark"] .nav-item:hover {
  background-color: #1A1A1A;
  color: #E5E7EB;
}

[data-theme="dark"] .nav-item:hover svg {
  color: #E5E7EB;
}

[data-theme="dark"] .nav-item.active {
  background: #1C1C1C;
  color: #E5E7EB;
  border-color: #1F2937;
  font-weight: 600;
}

[data-theme="dark"] .nav-item.active svg {
  color: #E5E7EB;
}

[data-theme="dark"] .chat-history-item {
  color: #9CA3AF;
}

[data-theme="dark"] .chat-history-item:hover {
  background-color: #1A1A1A;
  color: #E5E7EB;
}

[data-theme="dark"] .chat-history-item.active {
  background: #1C1C1C;
  color: #E5E7EB;
  border-color: #1F2937;
}

[data-theme="dark"] .chat-history-item.active .chat-item-title {
  color: #E5E7EB;
  font-weight: 600;
}

[data-theme="dark"] .sidebar-footer {
  background: #0E0E0E;
  border-top: 1px solid #1F2937;
}

[data-theme="dark"] .user-snippet:hover {
  background: #1A1A1A;
}

[data-theme="dark"] .user-email-text {
  color: #E5E7EB;
}

[data-theme="dark"] .app-topbar {
  background: rgba(11, 11, 11, 0.95);
  border-bottom: 1px solid #1F2937;
}

[data-theme="dark"] .active-conversation-title {
  color: #E5E7EB;
}

[data-theme="dark"] .model-select-btn {
  background: #161616;
  border: 1px solid #1F2937;
  color: #E5E7EB;
}

[data-theme="dark"] .model-select-btn:hover {
  background: #1C1C1C;
}

[data-theme="dark"] .model-dropdown-menu {
  background: #141414;
  border: 1px solid #1F2937;
  box-shadow: 0 10px 35px rgba(0, 0, 0, 0.7);
}

[data-theme="dark"] .model-option-item:hover {
  background: #1C1C1C;
}

[data-theme="dark"] .model-option-item.active {
  background: #222222;
  border-color: #374151;
}

[data-theme="dark"] .view-header h2,
[data-theme="dark"] .empty-state-title {
  color: #E5E7EB;
}

[data-theme="dark"] .empty-state-subtitle {
  color: #9CA3AF;
}

[data-theme="dark"] .prompt-starter-card {
  background: #141414;
  border: 1px solid #1F2937;
}

[data-theme="dark"] .prompt-starter-card:hover {
  background: #1A1A1A;
  border-color: #374151;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}

[data-theme="dark"] .starter-title {
  color: #E5E7EB;
}

[data-theme="dark"] .starter-desc {
  color: #9CA3AF;
}

[data-theme="dark"] .message-sender-name {
  color: #E5E7EB;
}

[data-theme="dark"] .message-time {
  color: #6B7280;
}

[data-theme="dark"] .user-row .message-bubble {
  background: #1C1C1C;
  border: 1px solid #1F2937;
  color: #E5E7EB;
}

[data-theme="dark"] .assistant-row .message-bubble {
  color: #E5E7EB;
}

[data-theme="dark"] .assistant-row .message-bubble h1,
[data-theme="dark"] .assistant-row .message-bubble h2,
[data-theme="dark"] .assistant-row .message-bubble h3,
[data-theme="dark"] .assistant-row .message-bubble h4 {
  color: #E5E7EB;
}

[data-theme="dark"] .code-block-wrapper {
  background: #121212;
  border: 1px solid #1F2937;
}

[data-theme="dark"] .code-block-header {
  background: #181818;
  border-bottom: 1px solid #1F2937;
  color: #9CA3AF;
}

[data-theme="dark"] .chat-composer-container {
  background: linear-gradient(180deg, rgba(11, 11, 11, 0) 0%, rgba(11, 11, 11, 0.95) 40%, #0B0B0B 100%);
}

[data-theme="dark"] .composer-card {
  background: #161616;
  border: 1px solid #1F2937;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
}

[data-theme="dark"] .composer-card:focus-within {
  border-color: #374151;
  box-shadow: 0 6px 25px rgba(0, 0, 0, 0.8);
}

[data-theme="dark"] .composer-input-area textarea {
  color: #E5E7EB;
}

[data-theme="dark"] .composer-input-area textarea::placeholder {
  color: #6B7280;
}

[data-theme="dark"] .btn-send-message {
  background: #E5E7EB;
  color: #0B0B0B;
  box-shadow: 0 2px 10px rgba(255, 255, 255, 0.1);
}

[data-theme="dark"] .btn-send-message:hover {
  background: #FFFFFF;
}

[data-theme="dark"] .modal-card,
[data-theme="dark"] .modal-card-large,
[data-theme="dark"] .modal-content {
  background: #141414;
  border: 1px solid #1F2937;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
  color: #E5E7EB;
}

[data-theme="dark"] .modal-title {
  color: #E5E7EB;
}

[data-theme="dark"] .project-card,
[data-theme="dark"] .image-preview-card,
[data-theme="dark"] .vision-output-card,
[data-theme="dark"] .settings-card,
[data-theme="dark"] .stat-card,
[data-theme="dark"] .owner-metric-card,
[data-theme="dark"] .tool-studio-card {
  background: #141414;
  border: 1px solid #1F2937;
}

[data-theme="dark"] .project-card:hover,
[data-theme="dark"] .stat-card:hover {
  background: #1A1A1A;
  border-color: #374151;
}

[data-theme="dark"] .project-title,
[data-theme="dark"] .project-card-title,
[data-theme="dark"] .project-note-title,
[data-theme="dark"] .project-item-title,
[data-theme="dark"] .search-source-title {
  color: #E5E7EB;
}

[data-theme="dark"] .project-desc,
[data-theme="dark"] .project-card-desc,
[data-theme="dark"] .project-note-content {
  color: #9CA3AF;
}

[data-theme="dark"] .search-large-input {
  background: #161616;
  border: 1px solid #1F2937;
  color: #E5E7EB;
}

[data-theme="dark"] .search-large-input::placeholder {
  color: #6B7280;
}

[data-theme="dark"] .files-dropzone,
[data-theme="dark"] .image-preview-stage,
[data-theme="dark"] .vision-output-body,
[data-theme="dark"] .image-gen-stage,
[data-theme="dark"] .gen-gallery-card,
[data-theme="dark"] .project-output-card {
  background: #121212;
  border: 1px solid #1F2937;
}

[data-theme="dark"] .admin-table th {
  background: #161616;
  color: #9CA3AF;
  border-bottom: 1px solid #1F2937;
}

[data-theme="dark"] .admin-table td {
  border-bottom: 1px solid #1F2937;
  color: #E5E7EB;
}
"""

    full_css = css.rstrip() + '\n\n' + adaptations

    with open('frontend/css/app.css', 'w', encoding='utf-8') as f:
        f.write(full_css)

    print('[SUCCESS] Successfully updated frontend/css/app.css')

if __name__ == '__main__':
    main()
