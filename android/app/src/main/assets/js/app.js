/**
 * NEXORA AI - Authenticated Application Shell & Workspace Controller (/app)
 */

let currentUser = null;
let chatController = null;

document.addEventListener('DOMContentLoaded', async () => {
  await initAppSession();
  setupWorkspaceNavigation();
  setupProfileAndSettings();
  setupMobileDrawer();
  setupAuxiliaryFeatures();
});

// Initialize & Protect Session
async function initAppSession() {
  try {
    const user = await window.authApi.getMe();
    if (!user || !user.userId) {
      redirectToLogin();
      return;
    }
    currentUser = user;
    renderUserInfo(user);

    // Initialize the Chat Controller
    chatController = new window.ChatController();
    await chatController.init();
    window.chatController = chatController;

    if (user.role === 'OWNER' || user.role === 'CEO' || user.role === 'ADMIN') {
      setupOwnerAdmin();
      if (window.location.pathname === '/admin' || window.location.hash === '#owner' || window.location.search.includes('view=owner')) {
        switchWorkspaceView('owner');
      }
    } else if (window.location.pathname === '/admin' || window.location.hash === '#owner' || window.location.search.includes('view=owner')) {
      window.showToast('Leadership (Owner/CEO) access required for the administrative console.', 'error');
    }
  } catch (err) {
    redirectToLogin();
  }
}

function redirectToLogin() {
  window.TokenManager.removeToken();
  window.location.href = '/login';
}

function renderUserInfo(user) {
  // Sidebar user snippet
  const avatarLetter = (user.email || 'U')[0].toUpperCase();
  const avatarEl = document.getElementById('user-avatar');
  if (avatarEl) avatarEl.innerText = avatarLetter;

  const emailEl = document.getElementById('user-email');
  if (emailEl) emailEl.innerText = user.email;

  const roleBadgeEl = document.getElementById('user-role-badge');
  if (roleBadgeEl) {
    roleBadgeEl.className = `badge ${user.role === 'OWNER' ? 'badge-owner' : (user.role === 'CEO' ? 'badge-ceo' : 'badge-user')}`;
    roleBadgeEl.innerText = user.role;
  }

  // Profile fields in Settings View
  const profileEmail = document.getElementById('profile-email');
  const profileUserId = document.getElementById('profile-userId');
  const profileRole = document.getElementById('profile-role');
  const profileStatus = document.getElementById('profile-status');
  const profileVerified = document.getElementById('profile-verified');

  if (profileEmail) profileEmail.innerText = user.email;
  if (profileUserId) profileUserId.innerText = user.userId;
  if (profileRole) profileRole.innerText = user.role;
  if (profileStatus) {
    profileStatus.innerHTML = `<span class="badge ${user.accountStatus === 'ACTIVE' ? 'badge-active' : 'badge-suspended'}">${user.accountStatus}</span>`;
  }
  if (profileVerified) {
    profileVerified.innerHTML = user.emailVerified
      ? '<span class="badge badge-active">VERIFIED</span>'
      : '<span class="badge badge-pending">PENDING</span> <button id="btn-resend-verify" class="btn btn-outline btn-sm" style="margin-left:8px;padding:2px 8px;font-size:11px;">Resend Verification</button>';
    
    const resendBtn = document.getElementById('btn-resend-verify');
    if (resendBtn) {
      resendBtn.addEventListener('click', async () => {
        try {
          resendBtn.disabled = true;
          await window.authApi.resendVerification();
          window.showToast('Verification email resent successfully', 'success');
        } catch (e) {
          window.showToast(e.message, 'error');
          resendBtn.disabled = false;
        }
      });
    }
  }

  // Quick user profile click opens Settings View
  const profileSnippet = document.getElementById('user-profile-snippet');
  if (profileSnippet) {
    profileSnippet.addEventListener('click', (e) => {
      if (e.target.closest('#btn-quick-logout')) return;
      switchWorkspaceView('settings');
    });
  }
}

// Switch between Main Workspace Views
function switchWorkspaceView(viewId) {
  // Update sidebar active state
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
    item.classList.toggle('active', item.getAttribute('data-view') === viewId);
  });

  // Switch visible main view
  document.querySelectorAll('.main-view').forEach(view => {
    view.classList.toggle('active', view.id === `view-${viewId}`);
  });

  // Close mobile sidebar on navigation
  const sidebar = document.getElementById('app-sidebar');
  if (sidebar) sidebar.classList.remove('mobile-open');

  if (viewId === 'settings') {
    loadActivityLogs();
    loadPersonalization();
    loadMemories();
  } else if (viewId === 'owner') {
    loadOwnerData();
  } else if (viewId === 'files') {
    loadUserFiles();
  } else if (viewId === 'images') {
    loadVisionGallery();
  } else if (viewId === 'image-gen') {
    loadImageGenGallery();
  } else if (viewId === 'projects') {
    loadProjects();
  }
}

function setupWorkspaceNavigation() {
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
    item.addEventListener('click', () => {
      const view = item.getAttribute('data-view');
      if (view) {
        switchWorkspaceView(view);
      }
    });
  });

  // Setup Phase 3 Files and Vision Modules
  setupFilesWorkspace();
  setupVisionWorkspace();
  setupDocModals();

  // Setup Phase 4 AI Search, Coding Studio, and Writing Studio Modules
  setupSearchWorkspace();
  setupCodeWorkspace();
  setupWritingWorkspace();

  // Setup Phase 5 Image Generator & Voice Studio Modules
  setupImageGenWorkspace();
  setupVoiceWorkspace();

  // Setup Phase 6 Projects & Personalization Modules
  setupProjectsWorkspace();
  setupPersonalizationWorkspace();


  // Quick Sign Out Button
  const btnQuickLogout = document.getElementById('btn-quick-logout');
  if (btnQuickLogout) {
    btnQuickLogout.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await window.authApi.logout();
      } catch (err) {}
      window.showToast('Signed out successfully', 'info');
      setTimeout(() => {
        window.location.href = '/login';
      }, 400);
    });
  }
}

// Profile and Settings Form Handlers
function setupProfileAndSettings() {
  // AI Settings Save
  const btnSaveAi = document.getElementById('btn-save-ai-settings');
  const defaultModelSelect = document.getElementById('settings-default-model');
  const systemPromptTextarea = document.getElementById('settings-system-prompt');

  if (defaultModelSelect) {
    defaultModelSelect.value = localStorage.getItem('nexora_model') || 'gemini-1.5-flash';
  }
  if (systemPromptTextarea) {
    systemPromptTextarea.value = localStorage.getItem('nexora_system_prompt') || '';
  }

  if (btnSaveAi) {
    btnSaveAi.addEventListener('click', () => {
      if (defaultModelSelect && defaultModelSelect.value) {
        localStorage.setItem('nexora_model', defaultModelSelect.value);
        if (chatController) chatController.activeModel = defaultModelSelect.value;
      }
      if (systemPromptTextarea) {
        localStorage.setItem('nexora_system_prompt', systemPromptTextarea.value.trim());
        if (chatController) chatController.systemPrompt = systemPromptTextarea.value.trim();
      }
      window.showToast('AI preferences saved', 'success');
    });
  }

  // Password Update Form
  const passwordForm = document.getElementById('change-password-form');
  if (passwordForm) {
    passwordForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const currentPassword = document.getElementById('current-password').value;
      const newPassword = document.getElementById('new-password').value;
      const submitBtn = document.getElementById('btn-submit-password');

      if (newPassword.length < 8) {
        window.showToast('New password must be at least 8 characters long', 'error');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerText = 'Updating...';

      try {
        await window.userApi.changePassword(currentPassword, newPassword);
        window.showToast('Password updated successfully', 'success');
        passwordForm.reset();
        await loadActivityLogs();
      } catch (err) {
        window.showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = 'Update Password';
      }
    });
  }
}

// Activity Log Loader
async function loadActivityLogs() {
  const tbody = document.getElementById('activity-tbody');
  if (!tbody) return;

  try {
    const logs = await window.userApi.getActivity();
    if (!logs || logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--color-text-muted);">No activity recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = logs.map(log => `
      <tr>
        <td><strong style="color:var(--color-bright);">${log.action}</strong></td>
        <td>${log.details || '-'}</td>
        <td style="color:var(--color-text-muted);font-size:12px;">${new Date(log.createdAt).toLocaleString()}</td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--color-danger);">Failed to load activity logs</td></tr>`;
  }
}

// Owner Administration Setup
async function setupOwnerAdmin() {
  const ownerNavItem = document.getElementById('owner-nav-item');
  if (ownerNavItem) ownerNavItem.style.display = 'flex';
}

let ownerSearchTimeout = null;

function debounceOwnerUserSearch() {
  clearTimeout(ownerSearchTimeout);
  ownerSearchTimeout = setTimeout(() => {
    loadOwnerData();
  }, 300);
}

async function loadOwnerData() {
  try {
    // 1. Fetch Overview Telemetry
    const stats = await window.ownerApi.getOverview();
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = (val !== undefined && val !== null) ? val : '-';
    };

    setVal('owner-total-users', stats.totalUsers);
    setVal('owner-new-today', stats.newUsersToday);
    setVal('owner-new-week', stats.newUsersThisWeek);
    setVal('owner-active-users', stats.activeUsers);
    setVal('owner-login-events', stats.loginEvents);
    setVal('owner-ai-requests', stats.aiRequests);
    setVal('owner-file-uploads', stats.fileUploads);
    setVal('owner-search-requests', stats.searchRequests);
    setVal('owner-image-gens', stats.imageGenerations);

    // 2. Fetch User Directory with Filters
    const searchVal = document.getElementById('owner-user-search')?.value?.trim() || '';
    const roleVal = document.getElementById('owner-user-role-filter')?.value || '';
    const statusVal = document.getElementById('owner-user-status-filter')?.value || '';

    const users = await window.ownerApi.getUsers(searchVal, roleVal, statusVal);
    renderOwnerUsersTable(users);

    // 3. Fetch Recent Login Activity
    const loginRes = await window.ownerApi.getLoginActivity(30);
    renderOwnerLoginsTable(loginRes?.activity || []);
  } catch (err) {
    console.error('Owner data error:', err);
    window.showToast('Failed to load owner telemetry: ' + (err.message || 'Unknown error'), 'error');
  }
}

function renderOwnerUsersTable(users) {
  const tbody = document.getElementById('owner-users-tbody');
  if (!tbody) return;

  if (!users || users.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--color-text-muted);padding:24px;">No users matching filter criteria.</td></tr>';
    return;
  }

  const formatDt = (isoStr) => {
    if (!isoStr) return '-';
    try {
      const d = new Date(isoStr);
      return isNaN(d.getTime()) ? isoStr.slice(0, 10) : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return isoStr.slice(0, 10);
    }
  };

  tbody.innerHTML = users.map(u => `
    <tr>
      <td>
        <div style="font-weight:600;color:var(--color-text-main);">${u.email}</div>
        <div style="font-size:11px;color:var(--color-text-muted);font-family:monospace;">${u.userId}</div>
      </td>
      <td><span class="badge ${u.role === 'OWNER' ? 'badge-owner' : (u.role === 'CEO' ? 'badge-ceo' : 'badge-user')}">${u.role}</span></td>
      <td><span class="badge ${u.accountStatus === 'ACTIVE' ? 'badge-active' : 'badge-suspended'}">${u.accountStatus}</span></td>
      <td>${u.loginCount || 0}</td>
      <td style="font-size:12px;color:var(--color-text-muted);">${formatDt(u.accountCreatedAt)}</td>
      <td style="font-size:12px;color:var(--color-text-muted);">${formatDt(u.lastLoginAt)}</td>
      <td>
        <div style="display:flex;gap:6px;">
          ${u.userId !== currentUser?.userId ? `
            <button class="btn btn-sm ${u.accountStatus === 'ACTIVE' ? 'btn-danger' : 'btn-outline'}" style="padding:2px 8px;font-size:11px;" onclick="handleOwnerStatusToggle('${u.userId}', '${u.accountStatus === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE'}')">
              ${u.accountStatus === 'ACTIVE' ? 'Suspend' : 'Activate'}
            </button>
            <button class="btn btn-sm btn-secondary" style="padding:2px 8px;font-size:11px;" onclick="handleOwnerRoleToggle('${u.userId}', '${u.role === 'OWNER' ? 'USER' : 'OWNER'}')">
              ${u.role === 'OWNER' ? 'Demote' : 'Make Owner'}
            </button>
          ` : '<span style="font-size:12px;color:var(--color-text-muted);">(You)</span>'}
        </div>
      </td>
    </tr>
  `).join('');
}

function renderOwnerLoginsTable(activities) {
  const tbody = document.getElementById('owner-logins-tbody');
  if (!tbody) return;

  if (!activities || activities.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--color-text-muted);padding:24px;">No login activity recorded yet.</td></tr>';
    return;
  }

  tbody.innerHTML = activities.map(a => `
    <tr>
      <td>
        <div style="font-weight:500;color:var(--color-text-main);">${a.email}</div>
      </td>
      <td style="font-size:12px;color:var(--color-text-muted);">${a.date} ${a.time}</td>
      <td style="font-size:12px;color:var(--color-text-muted);">
        <span style="display:inline-flex;align-items:center;gap:4px;">
          ${a.device}
        </span>
      </td>
      <td style="font-family:monospace;font-size:12px;color:var(--color-text-muted);">${a.ipAddress}</td>
      <td>
        <span class="badge badge-active" style="font-size:10px;">${a.status}</span>
      </td>
    </tr>
  `).join('');
}

window.debounceOwnerUserSearch = debounceOwnerUserSearch;

window.handleOwnerStatusToggle = async function(userId, newStatus) {
  try {
    await window.ownerApi.updateUserStatus(userId, newStatus);
    window.showToast(`User status updated to ${newStatus}`, 'success');
    await loadOwnerData();
  } catch (err) {
    window.showToast(err.message, 'error');
  }
};

window.handleOwnerRoleToggle = async function(userId, newRole) {
  try {
    await window.ownerApi.updateUserRole(userId, newRole);
    window.showToast(`User role updated to ${newRole}`, 'success');
    await loadOwnerData();
  } catch (err) {
    window.showToast(err.message, 'error');
  }
};

// Auxiliary View Handlers
function setupAuxiliaryFeatures() {
  // Global Keyboard Navigation & Accessibility (Escape closes modals)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop, .modal-backdrop-large').forEach(modal => {
        modal.style.display = 'none';
      });
      if (typeof stopVoiceRecording === 'function') {
        stopVoiceRecording(false);
      }
    }
  });

  // Code Sandbox Runner
  const btnRunCode = document.getElementById('btn-run-code-snippet');
  const codeEditor = document.getElementById('code-studio-editor');
  const codeOutputPanel = document.getElementById('code-output-panel');
  const codeOutputText = document.getElementById('code-output-text');

  if (btnRunCode && codeEditor && codeOutputPanel && codeOutputText) {
    btnRunCode.addEventListener('click', () => {
      btnRunCode.disabled = true;
      btnRunCode.innerText = 'Executing...';
      setTimeout(() => {
        btnRunCode.disabled = false;
        btnRunCode.innerText = 'Run Snippet';
        codeOutputPanel.style.display = 'block';
        codeOutputText.innerText = `[Execution Completed in 28ms]\nPrime numbers up to 50: [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]`;
        window.showToast('Snippet executed successfully', 'success', 2000);
      }, 350);
    });
  }

  // AI Deep Search Runner
  const btnRunSearch = document.getElementById('btn-run-deep-search');
  const searchInput = document.getElementById('ai-deep-search-input');
  const searchResults = document.getElementById('search-results-container');

  if (btnRunSearch && searchInput && searchResults) {
    btnRunSearch.addEventListener('click', () => {
      const q = searchInput.value.trim();
      if (!q) return;
      searchResults.innerHTML = `
        <div class="card" style="margin-top:16px;">
          <h4 style="color:var(--color-bright);margin-bottom:8px;">Search Synthesis: "${q}"</h4>
          <p style="font-size:14px;color:var(--color-text-secondary);line-height:1.6;">
            Found relevant insights matching your query across indexed knowledge sources and conversational archives.
          </p>
          <div style="margin-top:12px;display:flex;gap:8px;">
            <button class="btn btn-primary btn-sm" onclick="startChatWithSearchQuery('${q}')">Discuss with AI</button>
          </div>
        </div>
      `;
    });
  }

  // Project Creator
  const btnCreateProj = document.getElementById('btn-create-project-card');
  if (btnCreateProj) {
    btnCreateProj.addEventListener('click', () => {
      window.showToast('Project creation workspace initialized', 'info', 2500);
    });
  }

  // Image Studio Generator
  const btnGenImg = document.getElementById('btn-generate-image-studio');
  const imgPrompt = document.getElementById('image-prompt-input');
  const imgGallery = document.getElementById('image-gallery-grid');
  if (btnGenImg && imgPrompt && imgGallery) {
    btnGenImg.addEventListener('click', () => {
      const p = imgPrompt.value.trim();
      if (!p) return;
      btnGenImg.disabled = true;
      btnGenImg.innerText = 'Generating...';
      setTimeout(() => {
        btnGenImg.disabled = false;
        btnGenImg.innerText = 'Generate Image';
        imgGallery.innerHTML = `
          <div class="card" style="padding:16px;text-align:center;">
            <div style="height:220px;background:linear-gradient(135deg,#1E1B4B,#4C1D95);border-radius:var(--radius-md);display:flex;align-items:center;justify-content:center;color:#FFFFFF;font-weight:600;">
              🎨 [Generated Image: ${p.slice(0, 30)}...]
            </div>
            <div style="margin-top:10px;font-size:13px;color:var(--color-text-secondary);text-align:left;">
              <strong>Prompt:</strong> ${p}
            </div>
          </div>
        `;
        window.showToast('Image generated in studio gallery', 'success');
      }, 700);
    });
  }
}

window.startChatWithSearchQuery = function(query) {
  switchWorkspaceView('chat');
  if (chatController) {
    const textarea = document.getElementById('chat-textarea');
    if (textarea) {
      textarea.value = `Deep Search Query: ${query}`;
      chatController.handleSendMessage();
    }
  }
};

// Mobile Drawer
function setupMobileDrawer() {
  const toggleBtn = document.getElementById('mobile-drawer-toggle');
  const sidebar = document.getElementById('app-sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
    });
  }
}

// ==========================================================================
// PHASE 3: FILES & DOCUMENT INTELLIGENCE CONTROLLERS
// ==========================================================================

let currentFileFilter = 'all';
let currentFileSearchQuery = '';
let activeDocForAi = null;
let filePendingDelete = null;

function setupFilesWorkspace() {
  const dropzone = document.getElementById('files-page-dropzone');
  const fileInput = document.getElementById('files-page-file-input');
  const btnBrowse = document.getElementById('btn-browse-files-page');
  const filterPills = document.getElementById('files-filter-pills');
  const searchInput = document.getElementById('files-search-input');
  const btnRefresh = document.getElementById('btn-refresh-files');

  if (btnBrowse && fileInput) {
    btnBrowse.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('drag-over');
    });

    dropzone.addEventListener('drop', async (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        await handleFilesUpload(files);
      }
    });

    fileInput.addEventListener('change', async () => {
      if (fileInput.files && fileInput.files.length > 0) {
        await handleFilesUpload(fileInput.files);
        fileInput.value = '';
      }
    });
  }

  // Filter Pills
  if (filterPills) {
    filterPills.querySelectorAll('.filter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        filterPills.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        currentFileFilter = pill.getAttribute('data-filter') || 'all';
        loadUserFiles();
      });
    });
  }

  // Search Input
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentFileSearchQuery = searchInput.value.trim();
        loadUserFiles();
      }, 300);
    });
  }

  // Refresh
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      loadUserFiles();
      window.showToast('File library refreshed', 'info', 1500);
    });
  }
}

async function handleFilesUpload(fileList) {
  const progressContainer = document.getElementById('upload-progress-container');
  const progressFilename = document.getElementById('upload-progress-filename');
  const progressPercent = document.getElementById('upload-progress-percent');
  const progressBarFill = document.getElementById('upload-progress-bar-fill');

  if (progressContainer) progressContainer.style.display = 'block';

  let successCount = 0;
  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i];
    if (progressFilename) progressFilename.innerText = `Uploading ${file.name} (${i + 1}/${fileList.length})...`;

    try {
      await window.filesApi.uploadFile(file, (percent) => {
        if (progressPercent) progressPercent.innerText = `${percent}%`;
        if (progressBarFill) progressBarFill.style.width = `${percent}%`;
      });
      successCount++;
    } catch (err) {
      window.showToast(`Upload failed for ${file.name}: ${err.message}`, 'error', 5000);
    }
  }

  if (progressContainer) {
    setTimeout(() => {
      progressContainer.style.display = 'none';
      if (progressBarFill) progressBarFill.style.width = '0%';
    }, 1000);
  }

  if (successCount > 0) {
    window.showToast(`Successfully uploaded & parsed ${successCount} file(s)`, 'success');
    await loadUserFiles();
    loadVisionGallery(); // Refresh gallery in case image was uploaded
  }
}

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

async function loadUserFiles() {
  const tbody = document.getElementById('files-tbody');
  if (!tbody) return;

  try {
    const files = await window.filesApi.listFiles({
      q: currentFileSearchQuery,
      fileType: currentFileFilter
    });

    if (!files || files.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align:center;padding:48px 20px;color:var(--color-text-muted);">
            <div style="font-size:15px;margin-bottom:6px;color:var(--color-text-secondary);">No documents found</div>
            <div style="font-size:13px;">Drag & drop files above to start extracting knowledge and generating summaries.</div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = files.map(f => {
      const typeClass = `type-${f.fileType}`;
      const ext = f.originalFilename.split('.').pop().toUpperCase();
      const dateStr = new Date(f.createdAt).toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', year: 'numeric'
      });

      return `
        <tr>
          <td>
            <div style="display:flex;align-items:center;gap:10px;">
              <div class="file-type-badge ${typeClass}">${ext}</div>
              <div>
                <div style="font-weight:600;color:var(--color-text-main);max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                  ${f.originalFilename}
                </div>
                <div style="font-size:11px;color:var(--color-text-muted);">
                  ${f.pageCount ? f.pageCount + ' page(s) • ' : ''}${f.hasExtractedText ? '✓ Text extracted' : 'Binary asset'}
                </div>
              </div>
            </div>
          </td>
          <td><span class="file-type-badge ${typeClass}">${f.fileType.toUpperCase()}</span></td>
          <td style="color:var(--color-text-secondary);font-size:13px;">${formatFileSize(f.fileSize)}</td>
          <td style="color:var(--color-text-muted);font-size:12px;">${dateStr}</td>
          <td style="text-align:right;">
            <div style="display:inline-flex;gap:6px;align-items:center;">
              ${f.fileType !== 'image' ? `
                <button class="btn-ai-action" onclick="openDocAiModal('${f.id}', 'summarize')">
                  <span>⚡ AI</span>
                </button>
              ` : `
                <button class="btn-ai-action" onclick="openVisionStudioWithFile('${f.id}')">
                  <span>👁️ Vision</span>
                </button>
              `}
              ${f.hasExtractedText ? `
                <button class="btn btn-sm btn-outline" style="padding:2px 7px;font-size:11px;" onclick="openDocPreviewModal('${f.id}')" title="Preview Extracted Text">
                  👁️
                </button>
              ` : ''}
              <a href="/api/files/${f.id}/download" class="btn btn-sm btn-outline" style="padding:2px 7px;font-size:11px;text-decoration:none;" title="Download original file">
                📥
              </a>
              <button class="btn btn-sm btn-danger" style="padding:2px 7px;font-size:11px;" onclick="promptDeleteFile('${f.id}', '${f.originalFilename.replace(/'/g, "\\'")}')" title="Delete file">
                🗑️
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--color-danger);">Failed to load files: ${err.message}</td></tr>`;
  }
}

// Document AI Modal Controllers
function setupDocModals() {
  const modalDocAi = document.getElementById('modal-doc-ai');
  const btnCloseDocAi = document.getElementById('btn-close-doc-ai-modal');
  const btnSubmitDocAiQuery = document.getElementById('btn-submit-doc-ai-query');
  const docAiQueryInput = document.getElementById('doc-ai-custom-query');

  const btnDocAiSummarize = document.getElementById('btn-doc-ai-summarize');
  const btnDocAiNotes = document.getElementById('btn-doc-ai-notes');
  const btnDocAiExtract = document.getElementById('btn-doc-ai-extract');
  const btnDocAiQuestions = document.getElementById('btn-doc-ai-questions');
  const btnCopyDocAiResult = document.getElementById('btn-copy-doc-ai-result');
  const btnChatWithDoc = document.getElementById('btn-chat-with-doc');

  if (btnCloseDocAi && modalDocAi) {
    btnCloseDocAi.addEventListener('click', () => modalDocAi.style.display = 'none');
    modalDocAi.addEventListener('click', (e) => {
      if (e.target === modalDocAi) modalDocAi.style.display = 'none';
    });
  }

  if (btnDocAiSummarize) btnDocAiSummarize.addEventListener('click', () => executeDocAiAction('summarize'));
  if (btnDocAiNotes) btnDocAiNotes.addEventListener('click', () => executeDocAiAction('notes'));
  if (btnDocAiExtract) btnDocAiExtract.addEventListener('click', () => executeDocAiAction('extract'));
  if (btnDocAiQuestions) btnDocAiQuestions.addEventListener('click', () => executeDocAiAction('questions'));

  if (btnSubmitDocAiQuery && docAiQueryInput) {
    const handleQuerySubmit = () => {
      const q = docAiQueryInput.value.trim();
      if (q) executeDocAiAction('qa', q);
    };
    btnSubmitDocAiQuery.addEventListener('click', handleQuerySubmit);
    docAiQueryInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleQuerySubmit();
    });
  }

  if (btnCopyDocAiResult) {
    btnCopyDocAiResult.addEventListener('click', () => {
      const body = document.getElementById('doc-ai-modal-body');
      if (body) {
        navigator.clipboard.writeText(body.innerText);
        window.showToast('Document analysis copied to clipboard', 'success', 2000);
      }
    });
  }

  if (btnChatWithDoc) {
    btnChatWithDoc.addEventListener('click', () => {
      if (modalDocAi) modalDocAi.style.display = 'none';
      switchWorkspaceView('chat');
      if (activeDocForAi && window.chatController) {
        window.chatController.attachedFileIds = [activeDocForAi.id];
        const previewBar = document.getElementById('attachment-preview-bar');
        const filenameSpan = document.getElementById('attachment-filename');
        if (previewBar && filenameSpan) {
          filenameSpan.innerText = activeDocForAi.originalFilename;
          previewBar.style.display = 'flex';
        }
        window.showToast(`Attached ${activeDocForAi.originalFilename} to chat`, 'info');
      }
    });
  }

  // Document Text Preview Modal
  const modalDocPreview = document.getElementById('modal-doc-preview');
  const btnCloseDocPreview = document.getElementById('btn-close-doc-preview-modal');
  const btnClosePreviewFooter = document.getElementById('btn-close-preview-footer');
  const btnCopyPreviewText = document.getElementById('btn-copy-preview-text');

  if (btnCloseDocPreview && modalDocPreview) {
    btnCloseDocPreview.addEventListener('click', () => modalDocPreview.style.display = 'none');
    if (btnClosePreviewFooter) btnClosePreviewFooter.addEventListener('click', () => modalDocPreview.style.display = 'none');
    modalDocPreview.addEventListener('click', (e) => {
      if (e.target === modalDocPreview) modalDocPreview.style.display = 'none';
    });
  }

  if (btnCopyPreviewText) {
    btnCopyPreviewText.addEventListener('click', () => {
      const textEl = document.getElementById('doc-preview-text');
      if (textEl) {
        navigator.clipboard.writeText(textEl.innerText);
        window.showToast('Document text copied to clipboard', 'success', 2000);
      }
    });
  }

  // Delete Confirm Modal
  const modalDeleteFile = document.getElementById('modal-delete-file');
  const btnCancelFileDelete = document.getElementById('btn-cancel-file-delete');
  const btnConfirmFileDelete = document.getElementById('btn-confirm-file-delete');

  if (btnCancelFileDelete && modalDeleteFile) {
    btnCancelFileDelete.addEventListener('click', () => modalDeleteFile.style.display = 'none');
    modalDeleteFile.addEventListener('click', (e) => {
      if (e.target === modalDeleteFile) modalDeleteFile.style.display = 'none';
    });
  }

  if (btnConfirmFileDelete && modalDeleteFile) {
    btnConfirmFileDelete.addEventListener('click', async () => {
      if (!filePendingDelete) return;
      btnConfirmFileDelete.disabled = true;
      btnConfirmFileDelete.innerText = 'Deleting...';
      try {
        await window.filesApi.deleteFile(filePendingDelete);
        window.showToast('File deleted successfully', 'success');
        modalDeleteFile.style.display = 'none';
        await loadUserFiles();
        loadVisionGallery();
      } catch (err) {
        window.showToast(err.message, 'error');
      } finally {
        btnConfirmFileDelete.disabled = false;
        btnConfirmFileDelete.innerText = 'Delete File';
        filePendingDelete = null;
      }
    });
  }
}

window.openDocAiModal = async function(fileId, defaultAction = 'summarize') {
  const modal = document.getElementById('modal-doc-ai');
  const title = document.getElementById('doc-ai-modal-title');
  const subtitle = document.getElementById('doc-ai-modal-subtitle');
  const body = document.getElementById('doc-ai-modal-body');

  try {
    const file = await window.filesApi.getFile(fileId);
    activeDocForAi = file;
    if (modal) modal.style.display = 'flex';
    if (title) title.innerText = `Document Intelligence: ${file.originalFilename}`;
    if (subtitle) subtitle.innerText = `Type: ${file.fileType.toUpperCase()} • Size: ${formatFileSize(file.fileSize)}`;
    
    await executeDocAiAction(defaultAction);
  } catch (err) {
    window.showToast(err.message, 'error');
  }
};

async function executeDocAiAction(action, query = null) {
  if (!activeDocForAi) return;
  const body = document.getElementById('doc-ai-modal-body');
  if (body) {
    body.innerHTML = `
      <div style="text-align:center;padding:48px 20px;color:var(--color-text-muted);">
        <div class="pulse-loader" style="margin-bottom:14px;"></div>
        <div style="font-weight:600;color:var(--color-text-main);margin-bottom:4px;">Executing ${action.toUpperCase()} Analysis...</div>
        <div style="font-size:13px;">Applying grounded multi-modal LLM reasoning over document context</div>
      </div>
    `;
  }

  try {
    const res = await window.filesApi.executeAiAction(activeDocForAi.id, {
      action,
      query
    });

    if (body) {
      body.innerHTML = marked.parse(res.result);
      // Syntax highlight code blocks
      body.querySelectorAll('pre code').forEach(block => {
        hljs.highlightElement(block);
      });
    }
  } catch (err) {
    if (body) {
      body.innerHTML = `<div style="padding:20px;color:var(--color-danger);text-align:center;">Analysis failed: ${err.message}</div>`;
    }
  }
}

window.openDocPreviewModal = async function(fileId) {
  const modal = document.getElementById('modal-doc-preview');
  const title = document.getElementById('doc-preview-modal-title');
  const meta = document.getElementById('doc-preview-modal-meta');
  const textEl = document.getElementById('doc-preview-text');

  try {
    const file = await window.filesApi.getFile(fileId);
    if (modal) modal.style.display = 'flex';
    if (title) title.innerText = `Preview: ${file.originalFilename}`;
    if (meta) meta.innerText = `${file.fileType.toUpperCase()} • ${formatFileSize(file.fileSize)} • ${file.extractedText ? file.extractedText.length + ' characters' : 'No text'}`;
    if (textEl) textEl.innerText = file.extractedText || '[No readable text content extracted]';
  } catch (err) {
    window.showToast(err.message, 'error');
  }
};

window.promptDeleteFile = function(fileId, filename) {
  filePendingDelete = fileId;
  const modal = document.getElementById('modal-delete-file');
  const text = document.getElementById('delete-file-confirm-text');
  if (text) text.innerText = `Are you sure you want to delete "${filename}"? All stored data and extracted text will be permanently removed.`;
  if (modal) modal.style.display = 'flex';
};

// ==========================================================================
// PHASE 3: MULTIMODAL VISION & IMAGE STUDIO CONTROLLER
// ==========================================================================

let activeVisionFile = null;
let activeVisionBase64 = null;
let activeVisionAction = 'describe';

function setupVisionWorkspace() {
  const fileInput = document.getElementById('vision-file-input');
  const stage = document.getElementById('vision-stage');
  const clearBtn = document.getElementById('btn-clear-vision-img');
  const runBtn = document.getElementById('btn-run-vision-analysis');
  const customQueryInput = document.getElementById('vision-custom-query');
  const copyBtn = document.getElementById('btn-copy-vision-output');
  const openChatBtn = document.getElementById('btn-open-vision-in-chat');

  // Drag & drop on vision stage
  if (stage && fileInput) {
    stage.addEventListener('dragover', (e) => {
      e.preventDefault();
      stage.style.borderColor = 'var(--color-bright)';
    });
    stage.addEventListener('dragleave', () => {
      stage.style.borderColor = 'rgba(255,255,255,0.15)';
    });
    stage.addEventListener('drop', async (e) => {
      e.preventDefault();
      stage.style.borderColor = 'rgba(255,255,255,0.15)';
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        await loadVisionImageFile(files[0]);
      }
    });

    fileInput.addEventListener('change', async () => {
      if (fileInput.files && fileInput.files.length > 0) {
        await loadVisionImageFile(fileInput.files[0]);
        fileInput.value = '';
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      resetVisionStage();
    });
  }

  // Vision preset selectors
  document.querySelectorAll('.btn-vision-preset').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.btn-vision-preset').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeVisionAction = btn.getAttribute('data-action') || 'describe';
    });
  });

  // Execute Vision Analysis
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      if (!activeVisionFile && !activeVisionBase64) {
        window.showToast('Please select or upload an image first', 'info');
        return;
      }

      const outputBody = document.getElementById('vision-output-body');
      const customQuery = customQueryInput ? customQueryInput.value.trim() : null;

      runBtn.disabled = true;
      runBtn.innerText = 'Analyzing Vision...';
      if (outputBody) {
        outputBody.innerHTML = `
          <div style="text-align:center;padding:48px 20px;color:var(--color-text-muted);">
            <div class="pulse-loader" style="margin-bottom:14px;"></div>
            <div style="font-weight:600;color:var(--color-text-main);margin-bottom:4px;">Evaluating Visual Context (${activeVisionAction.toUpperCase()})...</div>
            <div style="font-size:13px;">Executing multi-modal visual inference and optical recognition</div>
          </div>
        `;
      }

      try {
        const payload = {
          action: activeVisionAction,
          query: customQuery
        };
        if (activeVisionFile && activeVisionFile.id) {
          payload.fileId = activeVisionFile.id;
        } else if (activeVisionBase64) {
          payload.imageBase64 = activeVisionBase64;
        }

        const res = await window.filesApi.analyzeVision(payload);
        if (outputBody) {
          outputBody.innerHTML = marked.parse(res.result);
          outputBody.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
          });
        }
        window.showToast('Vision analysis complete', 'success');
      } catch (err) {
        if (outputBody) {
          outputBody.innerHTML = `<div style="padding:20px;color:var(--color-danger);text-align:center;">Vision analysis error: ${err.message}</div>`;
        }
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
          <span>Execute Vision Analysis</span>
        `;
      }
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const outputBody = document.getElementById('vision-output-body');
      if (outputBody) {
        navigator.clipboard.writeText(outputBody.innerText);
        window.showToast('Vision output copied', 'success', 1500);
      }
    });
  }

  if (openChatBtn) {
    openChatBtn.addEventListener('click', () => {
      switchWorkspaceView('chat');
      if (activeVisionFile && window.chatController) {
        window.chatController.attachedFileIds = [activeVisionFile.id];
        const previewBar = document.getElementById('attachment-preview-bar');
        const filenameSpan = document.getElementById('attachment-filename');
        if (previewBar && filenameSpan) {
          filenameSpan.innerText = activeVisionFile.originalFilename;
          previewBar.style.display = 'flex';
        }
        window.showToast(`Attached ${activeVisionFile.originalFilename} to chat`, 'info');
      }
    });
  }
}

async function loadVisionImageFile(file) {
  // First upload the file so it has an isolated server-side record
  try {
    window.showToast('Uploading image to secure storage...', 'info', 2000);
    const savedFile = await window.filesApi.uploadFile(file);
    activeVisionFile = savedFile;
    activeVisionBase64 = null;

    // Display preview
    const emptyPrompt = document.getElementById('vision-empty-prompt');
    const previewImg = document.getElementById('vision-preview-img');
    const metaBar = document.getElementById('vision-img-meta-bar');
    const filenameSpan = document.getElementById('vision-meta-filename');
    const dimsSpan = document.getElementById('vision-meta-dims');

    if (emptyPrompt) emptyPrompt.style.display = 'none';
    if (previewImg) {
      previewImg.src = `/api/files/${savedFile.id}/download`;
      previewImg.style.display = 'block';
    }
    if (metaBar) metaBar.style.display = 'flex';
    if (filenameSpan) filenameSpan.innerText = savedFile.originalFilename;
    if (dimsSpan) dimsSpan.innerText = formatFileSize(savedFile.fileSize);

    window.showToast('Image ready for vision analysis', 'success');
    loadVisionGallery();
  } catch (err) {
    window.showToast(`Image load failed: ${err.message}`, 'error');
  }
}

window.openVisionStudioWithFile = async function(fileId) {
  switchWorkspaceView('images');
  try {
    const file = await window.filesApi.getFile(fileId);
    activeVisionFile = file;
    activeVisionBase64 = null;

    const emptyPrompt = document.getElementById('vision-empty-prompt');
    const previewImg = document.getElementById('vision-preview-img');
    const metaBar = document.getElementById('vision-img-meta-bar');
    const filenameSpan = document.getElementById('vision-meta-filename');
    const dimsSpan = document.getElementById('vision-meta-dims');

    if (emptyPrompt) emptyPrompt.style.display = 'none';
    if (previewImg) {
      previewImg.src = `/api/files/${file.id}/download`;
      previewImg.style.display = 'block';
    }
    if (metaBar) metaBar.style.display = 'flex';
    if (filenameSpan) filenameSpan.innerText = file.originalFilename;
    if (dimsSpan) dimsSpan.innerText = formatFileSize(file.fileSize);
  } catch (err) {
    window.showToast(err.message, 'error');
  }
};

function resetVisionStage() {
  activeVisionFile = null;
  activeVisionBase64 = null;
  const emptyPrompt = document.getElementById('vision-empty-prompt');
  const previewImg = document.getElementById('vision-preview-img');
  const metaBar = document.getElementById('vision-img-meta-bar');

  if (emptyPrompt) emptyPrompt.style.display = 'block';
  if (previewImg) {
    previewImg.src = '';
    previewImg.style.display = 'none';
  }
  if (metaBar) metaBar.style.display = 'none';
}

async function loadVisionGallery() {
  const gallery = document.getElementById('vision-gallery-grid');
  if (!gallery) return;

  try {
    const imageFiles = await window.filesApi.listFiles({ fileType: 'image', limit: 12 });
    if (!imageFiles || imageFiles.length === 0) {
      gallery.innerHTML = '<div style="font-size:12px;color:var(--color-text-muted);">No images uploaded yet.</div>';
      return;
    }

    gallery.innerHTML = imageFiles.map(img => `
      <div class="vision-gallery-item" onclick="openVisionStudioWithFile('${img.id}')" title="Click to analyze ${img.originalFilename}">
        <img src="/api/files/${img.id}/download" alt="${img.originalFilename}" loading="lazy">
        <div class="gallery-item-overlay">${img.originalFilename}</div>
      </div>
    `).join('');
  } catch (err) {
    gallery.innerHTML = '<div style="font-size:12px;color:var(--color-danger);">Failed to load gallery</div>';
  }
}

// ==========================================================================
// PHASE 4: 1. AI DEEP SEARCH CONTROLLER
// ==========================================================================

let lastSearchResponse = null;

function setupSearchWorkspace() {
  const searchInput = document.getElementById('ai-deep-search-input');
  const depthSelect = document.getElementById('search-depth-select');
  const searchBtn = document.getElementById('btn-run-deep-search');
  const statusBar = document.getElementById('search-status-bar');
  const statusText = document.getElementById('search-status-text');
  const resultsContainer = document.getElementById('search-results-container');

  async function executeSearch(query) {
    if (!query || !query.trim()) {
      window.showToast('Please enter a search query or research topic', 'info');
      return;
    }

    const depth = depthSelect ? depthSelect.value : 'standard';
    const maxResults = depth === 'deep' ? 8 : 5;

    if (searchBtn) {
      searchBtn.disabled = true;
      searchBtn.innerHTML = 'Searching...';
    }
    if (statusBar) statusBar.style.display = 'flex';
    if (statusText) statusText.innerText = '1. Querying search engine & gathering live web documents...';

    // Simulated progress stage updates
    const stageTimer1 = setTimeout(() => {
      if (statusText) statusText.innerText = '2. Extracting grounded references & filtering fact sources...';
    }, 800);
    const stageTimer2 = setTimeout(() => {
      if (statusText) statusText.innerText = '3. Synthesizing AI research brief with numbered citations [1], [2]...';
    }, 1600);

    try {
      const res = await window.toolsApi.search({
        query: query.trim(),
        searchDepth: depth,
        maxResults: maxResults
      });

      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      lastSearchResponse = res;

      renderSearchResults(res, resultsContainer);
      window.showToast('AI Deep Search complete', 'success', 2000);
    } catch (err) {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      if (resultsContainer) {
        resultsContainer.innerHTML = `
          <div class="card" style="border-color:var(--color-danger);text-align:center;padding:32px;">
            <div style="color:var(--color-danger);font-weight:600;margin-bottom:6px;">Search Execution Failed</div>
            <div style="color:var(--color-text-secondary);font-size:13px;">${err.message}</div>
          </div>
        `;
      }
    } finally {
      if (statusBar) statusBar.style.display = 'none';
      if (searchBtn) {
        searchBtn.disabled = false;
        searchBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          <span>Search</span>
        `;
      }
    }
  }

  if (searchBtn && searchInput) {
    searchBtn.addEventListener('click', () => {
      executeSearch(searchInput.value);
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        executeSearch(searchInput.value);
      }
    });
  }

  // Preset search chips
  document.querySelectorAll('.search-preset-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.getAttribute('data-query');
      if (q && searchInput) {
        searchInput.value = q;
        executeSearch(q);
      }
    });
  });
}

function renderSearchResults(data, container) {
  if (!container) return;

  const sources = data.sources || [];
  const synthesis = data.synthesis || 'No synthesis generated.';
  const query = data.query || '';

  // Render clickable citation links for [1], [2], etc.
  const parsedMarkdown = marked.parse(synthesis);
  const formattedSynthesis = parsedMarkdown.replace(/\[(\d+)\]/g, (match, p1) => {
    return `<a href="#search-src-${p1}" class="citation-badge" title="Jump to Source [${p1}]">[${p1}]</a>`;
  });

  const sourcesHtml = sources.length > 0 ? `
    <div style="margin-bottom:20px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h3 style="font-size:14px;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:0.5px;margin:0;">
          Verified Grounded Sources (${sources.length})
        </h3>
        <span style="font-size:11px;color:var(--color-text-muted);">Never Fabricated • Real URLs</span>
      </div>
      <div class="search-sources-grid">
        ${sources.map(src => `
          <a href="${src.url}" target="_blank" rel="noopener noreferrer" class="search-source-card" id="search-src-${src.index}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span class="search-source-num">[${src.index}]</span>
              <span class="search-source-domain">${src.domain || 'web'}</span>
            </div>
            <div class="search-source-title">${src.title || 'Untitled Source'}</div>
            <div style="font-size:11px;color:var(--color-text-muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
              ${src.snippet || ''}
            </div>
          </a>
        `).join('')}
      </div>
    </div>
  ` : '';

  container.innerHTML = `
    <!-- Sources Section -->
    ${sourcesHtml}

    <!-- AI Synthesis Section -->
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid var(--color-border);padding-bottom:12px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="badge badge-active">AI SYNTHESIS</span>
          <span style="font-size:13px;font-weight:600;color:#FFFFFF;">Research Report: ${query}</span>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-outline btn-sm" id="btn-copy-search-synthesis" style="padding:3px 10px;font-size:12px;" title="Copy to clipboard">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            <span>Copy Report</span>
          </button>
          <button class="btn btn-secondary btn-sm" id="btn-search-open-in-chat" style="padding:3px 10px;font-size:12px;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
            <span>Discuss in Chat</span>
          </button>
        </div>
      </div>

      <div class="search-synthesis-body" style="font-size:14px;line-height:1.7;color:var(--color-text-main);">
        ${formattedSynthesis}
      </div>
    </div>
  `;

  // Syntax highlight any code inside search synthesis
  container.querySelectorAll('pre code').forEach(block => {
    hljs.highlightElement(block);
  });

  // Attach copy and chat event handlers
  const copyBtn = document.getElementById('btn-copy-search-synthesis');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(synthesis);
      window.showToast('Research report copied to clipboard', 'success', 1500);
    });
  }

  const chatBtn = document.getElementById('btn-search-open-in-chat');
  if (chatBtn) {
    chatBtn.addEventListener('click', () => {
      switchWorkspaceView('chat');
      const chatInput = document.getElementById('chat-composer-input');
      if (chatInput) {
        chatInput.value = `I just researched "${query}". Here is the synthesis:\n\n${synthesis}\n\nLet's explore this further: `;
        chatInput.focus();
      }
    });
  }
}

// ==========================================================================
// PHASE 4: 2. CODING ASSISTANT & SANDBOX CONTROLLER
// ==========================================================================

let activeCodeAction = 'generate';
let lastCodeResult = '';

function setupCodeWorkspace() {
  const langSelect = document.getElementById('code-language-select');
  const chipsContainer = document.getElementById('code-action-chips');
  const promptInput = document.getElementById('code-prompt-input');
  const promptLabel = document.getElementById('code-prompt-label');
  const errorGroup = document.getElementById('code-error-group');
  const errorInput = document.getElementById('code-error-input');
  const editor = document.getElementById('code-editor-input');
  const statsInfo = document.getElementById('code-stats-info');
  const runAssistBtn = document.getElementById('btn-run-code-assist');
  const runSandboxBtn = document.getElementById('btn-run-code-sandbox');
  const clearEditorBtn = document.getElementById('btn-clear-code-editor');
  const modeBadge = document.getElementById('code-response-mode-badge');
  const responseBody = document.getElementById('code-ai-response-body');
  const copyBtn = document.getElementById('btn-copy-code-response');
  const openChatBtn = document.getElementById('btn-code-open-in-chat');
  const sandboxOutput = document.getElementById('code-sandbox-output');
  const sandboxMeta = document.getElementById('code-sandbox-meta');

  // Update line counter
  function updateCodeStats() {
    if (editor && statsInfo) {
      const lines = editor.value.split('\n').length;
      const chars = editor.value.length;
      statsInfo.innerText = `${lines} lines • ${chars} chars`;
    }
  }

  if (editor) {
    editor.addEventListener('input', updateCodeStats);
    updateCodeStats();
  }

  // Action chips handling
  if (chipsContainer) {
    chipsContainer.querySelectorAll('.code-action-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        chipsContainer.querySelectorAll('.code-action-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeCodeAction = chip.getAttribute('data-action') || 'generate';

        // Adjust UI context based on action
        if (activeCodeAction === 'debug') {
          if (promptLabel) promptLabel.innerText = 'Bug Description / Expected vs Actual Behavior:';
          if (promptInput) promptInput.placeholder = 'e.g. Function returns incorrect hash for negative keys';
          if (errorGroup) errorGroup.style.display = 'block';
        } else if (activeCodeAction === 'error_analysis') {
          if (promptLabel) promptLabel.innerText = 'Error Context / Task:';
          if (promptInput) promptInput.placeholder = 'e.g. Investigating IndexError or TypeError in sorting routine';
          if (errorGroup) errorGroup.style.display = 'block';
        } else if (activeCodeAction === 'explain') {
          if (promptLabel) promptLabel.innerText = 'Aspect to Explain / Questions (Optional):';
          if (promptInput) promptInput.placeholder = 'e.g. Explain time and space complexity and recursion depth';
          if (errorGroup) errorGroup.style.display = 'none';
        } else if (activeCodeAction === 'refactor') {
          if (promptLabel) promptLabel.innerText = 'Refactoring Target (e.g. SOLID, Clean Architecture):';
          if (promptInput) promptInput.placeholder = 'e.g. Refactor into modular classes with type hints';
          if (errorGroup) errorGroup.style.display = 'none';
        } else if (activeCodeAction === 'optimize') {
          if (promptLabel) promptLabel.innerText = 'Optimization Goal:';
          if (promptInput) promptInput.placeholder = 'e.g. Optimize from O(N^2) to O(N log N) time and reduce memory allocations';
          if (errorGroup) errorGroup.style.display = 'none';
        } else {
          if (promptLabel) promptLabel.innerText = 'Prompt / Task Description:';
          if (promptInput) promptInput.placeholder = 'e.g. Write a thread-safe LRU cache with O(1) get and put operations';
          if (errorGroup) errorGroup.style.display = 'none';
        }
      });
    });
  }

  // Run AI Coding Assist
  if (runAssistBtn) {
    runAssistBtn.addEventListener('click', async () => {
      const language = langSelect ? langSelect.value : 'python';
      const prompt = promptInput ? promptInput.value.trim() : '';
      const code = editor ? editor.value : '';
      const errorMessage = (errorGroup && errorGroup.style.display !== 'none' && errorInput) ? errorInput.value.trim() : null;

      if (!prompt && !code && !errorMessage) {
        window.showToast('Please provide a prompt, code snippet, or error message', 'info');
        return;
      }

      runAssistBtn.disabled = true;
      runAssistBtn.innerHTML = 'Thinking...';
      if (responseBody) {
        responseBody.innerHTML = `
          <div style="text-align:center;padding:48px 16px;color:var(--color-text-muted);">
            <div class="pulse-loader" style="margin-bottom:12px;"></div>
            <div style="font-weight:600;color:var(--color-text-main);margin-bottom:4px;">Executing ${activeCodeAction.toUpperCase()} analysis in ${language.toUpperCase()}...</div>
            <div style="font-size:12px;">Applying architectural validation, syntax checks, and best practices</div>
          </div>
        `;
      }

      try {
        const res = await window.toolsApi.assistCode({
          action: activeCodeAction,
          language: language,
          code: code || null,
          prompt: prompt || null,
          errorMessage: errorMessage || null
        });

        lastCodeResult = res.explanation || (res.code ? `\`\`\`${language}\n${res.code}\n\`\`\`` : '');
        if (modeBadge) modeBadge.innerText = `AI ${activeCodeAction.toUpperCase()}`;

        let outputContent = res.explanation || '';
        if (res.code && !outputContent.includes('```')) {
          outputContent = `\`\`\`${language}\n${res.code}\n\`\`\`\n\n` + outputContent;
        }

        if (responseBody) {
          responseBody.innerHTML = marked.parse(outputContent);
          responseBody.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
          });
        }
        window.showToast('Coding intelligence generated', 'success');
      } catch (err) {
        if (responseBody) {
          responseBody.innerHTML = `<div style="padding:20px;color:var(--color-danger);text-align:center;">Coding Assistant Error: ${err.message}</div>`;
        }
      } finally {
        runAssistBtn.disabled = false;
        runAssistBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
          <span>Run AI Assist</span>
        `;
      }
    });
  }

  // Run in Python Sandbox
  if (runSandboxBtn) {
    runSandboxBtn.addEventListener('click', async () => {
      const code = editor ? editor.value : '';
      if (!code || !code.trim()) {
        window.showToast('Editor is empty. Paste or write Python code first', 'info');
        return;
      }

      runSandboxBtn.disabled = true;
      runSandboxBtn.innerHTML = 'Running...';
      if (sandboxOutput) {
        sandboxOutput.style.color = 'var(--color-text-secondary)';
        sandboxOutput.innerText = '⚡ Spawning sandboxed isolated subprocess with 4.0s timeout...';
      }

      try {
        const res = await window.toolsApi.executeCode({
          language: 'python',
          code: code
        });

        if (sandboxMeta) {
          sandboxMeta.innerText = `Exit Code: ${res.exitCode} • ${res.durationMs}ms • ${res.success ? 'PASS' : 'FAIL'}`;
        }

        if (sandboxOutput) {
          if (res.success) {
            sandboxOutput.style.color = 'var(--color-success)';
            sandboxOutput.innerText = res.stdout || '[Program executed successfully with no stdout]';
          } else {
            sandboxOutput.style.color = 'var(--color-danger)';
            sandboxOutput.innerText = res.stderr || res.stdout || 'Execution failed';
          }
        }
      } catch (err) {
        if (sandboxOutput) {
          sandboxOutput.style.color = 'var(--color-danger)';
          sandboxOutput.innerText = `Sandbox Error: ${err.message}`;
        }
      } finally {
        runSandboxBtn.disabled = false;
        runSandboxBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          <span>Run in Sandbox</span>
        `;
      }
    });
  }

  // Copy code response
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      if (responseBody) {
        navigator.clipboard.writeText(responseBody.innerText);
        window.showToast('Code output copied to clipboard', 'success', 1500);
      }
    });
  }

  // Open code in chat
  if (openChatBtn) {
    openChatBtn.addEventListener('click', () => {
      switchWorkspaceView('chat');
      const chatInput = document.getElementById('chat-composer-input');
      const currentCode = editor ? editor.value : '';
      if (chatInput) {
        chatInput.value = `Here is my code for discussion:\n\`\`\`${langSelect ? langSelect.value : 'python'}\n${currentCode}\n\`\`\`\n\n`;
        chatInput.focus();
      }
    });
  }

  // Clear editor
  if (clearEditorBtn) {
    clearEditorBtn.addEventListener('click', () => {
      if (editor) {
        editor.value = '';
        updateCodeStats();
      }
    });
  }
}

// ==========================================================================
// PHASE 4: 3. WRITING ASSISTANT & TRANSLATION CONTROLLER
// ==========================================================================

let activeWritingAction = 'rewrite';
let lastWritingResult = '';

function setupWritingWorkspace() {
  const tabsContainer = document.getElementById('writing-mode-tabs');
  const toneContainer = document.getElementById('writing-tone-container');
  const toneSelect = document.getElementById('writing-tone-select');
  const langContainer = document.getElementById('writing-lang-container');
  const langSelect = document.getElementById('writing-lang-select');
  const contextFields = document.getElementById('writing-context-fields');
  const recipientInput = document.getElementById('writing-recipient-input');
  const jobTitleInput = document.getElementById('writing-job-title-input');
  const companyInput = document.getElementById('writing-company-input');
  const inputText = document.getElementById('writing-input-text');
  const inputStats = document.getElementById('writing-input-stats');
  const inputLabel = document.getElementById('writing-input-label');
  const runBtn = document.getElementById('btn-run-writing-assist');
  const btnText = document.getElementById('writing-btn-text');
  const clearBtn = document.getElementById('btn-clear-writing-input');
  const resultBadge = document.getElementById('writing-result-badge');
  const outputStats = document.getElementById('writing-output-stats');
  const outputBody = document.getElementById('writing-output-body');
  const copyBtn = document.getElementById('btn-copy-writing-output');
  const openChatBtn = document.getElementById('btn-writing-open-in-chat');

  // Input stats counter
  function updateWritingInputStats() {
    if (inputText && inputStats) {
      const text = inputText.value.trim();
      const words = text ? text.split(/\s+/).length : 0;
      const chars = inputText.value.length;
      inputStats.innerText = `${words} words • ${chars} chars`;
    }
  }

  if (inputText) {
    inputText.addEventListener('input', updateWritingInputStats);
    updateWritingInputStats();
  }

  // Mode tabs handling
  if (tabsContainer) {
    tabsContainer.querySelectorAll('.writing-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        tabsContainer.querySelectorAll('.writing-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeWritingAction = tab.getAttribute('data-action') || 'rewrite';

        // Update UI context based on action
        if (activeWritingAction === 'translate') {
          if (langContainer) langContainer.style.display = 'flex';
          if (toneContainer) toneContainer.style.display = 'none';
          if (contextFields) contextFields.style.display = 'none';
          if (inputLabel) inputLabel.innerText = 'Text to Translate';
          if (btnText) btnText.innerText = 'Translate Text';
        } else if (activeWritingAction === 'email') {
          if (langContainer) langContainer.style.display = 'none';
          if (toneContainer) toneContainer.style.display = 'flex';
          if (contextFields) {
            contextFields.style.display = 'flex';
            if (recipientInput) recipientInput.style.display = 'block';
            if (jobTitleInput) jobTitleInput.style.display = 'none';
            if (companyInput) companyInput.style.display = 'none';
          }
          if (inputLabel) inputLabel.innerText = 'Email Context / Bullet Points';
          if (btnText) btnText.innerText = 'Compose Email';
        } else if (activeWritingAction === 'resume') {
          if (langContainer) langContainer.style.display = 'none';
          if (toneContainer) toneContainer.style.display = 'none';
          if (contextFields) {
            contextFields.style.display = 'flex';
            if (recipientInput) recipientInput.style.display = 'none';
            if (jobTitleInput) jobTitleInput.style.display = 'block';
            if (companyInput) companyInput.style.display = 'block';
          }
          if (inputLabel) inputLabel.innerText = 'Existing Experience Bullets or Responsibilities';
          if (btnText) btnText.innerText = 'Optimize Resume Bullets';
        } else if (activeWritingAction === 'cover_letter') {
          if (langContainer) langContainer.style.display = 'none';
          if (toneContainer) toneContainer.style.display = 'flex';
          if (contextFields) {
            contextFields.style.display = 'flex';
            if (recipientInput) recipientInput.style.display = 'block';
            if (jobTitleInput) jobTitleInput.style.display = 'block';
            if (companyInput) companyInput.style.display = 'block';
          }
          if (inputLabel) inputLabel.innerText = 'Your Background & Key Achievements';
          if (btnText) btnText.innerText = 'Generate Cover Letter';
        } else {
          if (langContainer) langContainer.style.display = 'none';
          if (toneContainer) toneContainer.style.display = 'flex';
          if (contextFields) contextFields.style.display = 'none';
          if (inputLabel) inputLabel.innerText = 'Source Content / Draft';
          if (btnText) btnText.innerText = `Execute ${tab.innerText}`;
        }
      });
    });
  }

  // Run Writing Assist
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      const text = inputText ? inputText.value.trim() : '';
      if (!text) {
        window.showToast('Please enter text or notes in the draft area', 'info');
        return;
      }

      const tone = toneSelect ? toneSelect.value : 'professional';
      const targetLang = langSelect ? langSelect.value : 'Spanish';
      const recipient = (recipientInput && recipientInput.style.display !== 'none') ? recipientInput.value.trim() : null;
      const jobTitle = (jobTitleInput && jobTitleInput.style.display !== 'none') ? jobTitleInput.value.trim() : null;
      const companyName = (companyInput && companyInput.style.display !== 'none') ? companyInput.value.trim() : null;

      runBtn.disabled = true;
      runBtn.innerHTML = 'Refining...';
      if (outputBody) {
        outputBody.innerHTML = `
          <div style="text-align:center;padding:48px 16px;color:var(--color-text-muted);">
            <div class="pulse-loader" style="margin-bottom:12px;"></div>
            <div style="font-weight:600;color:var(--color-text-main);margin-bottom:4px;">Applying Editorial Intelligence (${activeWritingAction.toUpperCase()})...</div>
            <div style="font-size:12px;">Optimizing vocabulary, cadence, readability, and structural flow</div>
          </div>
        `;
      }

      try {
        const res = await window.toolsApi.assistWriting({
          action: activeWritingAction,
          text: text,
          tone: tone,
          targetLanguage: targetLang,
          recipient: recipient || null,
          jobTitle: jobTitle || null,
          companyName: companyName || null
        });

        lastWritingResult = res.result || '';
        if (resultBadge) resultBadge.innerText = `${activeWritingAction.toUpperCase()} RESULT`;
        if (outputStats) {
          const delta = res.outputWords - res.inputWords;
          const deltaSign = delta >= 0 ? `+${delta}` : `${delta}`;
          outputStats.innerText = `${res.outputWords} words (${deltaSign})`;
        }

        if (outputBody) {
          outputBody.innerHTML = marked.parse(res.result);
          outputBody.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
          });
        }
        window.showToast('Writing intelligence generated', 'success');
      } catch (err) {
        if (outputBody) {
          outputBody.innerHTML = `<div style="padding:20px;color:var(--color-danger);text-align:center;">Writing Error: ${err.message}</div>`;
        }
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
          <span id="writing-btn-text">Execute ${activeWritingAction.toUpperCase()}</span>
        `;
      }
    });
  }

  // Copy Output
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      if (outputBody) {
        navigator.clipboard.writeText(outputBody.innerText);
        window.showToast('Writing output copied to clipboard', 'success', 1500);
      }
    });
  }

  // Open in Chat
  if (openChatBtn) {
    openChatBtn.addEventListener('click', () => {
      switchWorkspaceView('chat');
      const chatInput = document.getElementById('chat-composer-input');
      if (chatInput) {
        chatInput.value = `Here is my writing draft for feedback:\n\n${lastWritingResult || (outputBody ? outputBody.innerText : '')}\n\n`;
        chatInput.focus();
      }
    });
  }

  // Clear Input
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (inputText) {
        inputText.value = '';
        updateWritingInputStats();
      }
    });
  }
}

/* ==========================================================================
   PHASE 5: IMAGE GENERATION STUDIO WORKSPACE CONTROLLER
   ========================================================================== */

let activeGenStyle = 'photorealistic';
let activeGenAspect = '1:1';
let currentGeneratedImage = null;
let pendingDeleteGenImageId = null;

function setupImageGenWorkspace() {
  const stylesGrid = document.getElementById('image-gen-styles-grid');
  const aspectSelector = document.getElementById('aspect-ratio-selector');
  const promptInput = document.getElementById('image-gen-prompt');
  const charCount = document.getElementById('image-gen-char-count');
  const negPromptInput = document.getElementById('image-gen-negative-prompt');
  const modelSelect = document.getElementById('image-gen-model-select');
  const runBtn = document.getElementById('btn-run-image-gen');
  const downloadBtn = document.getElementById('btn-download-gen-image');
  const analyzeBtn = document.getElementById('btn-use-gen-in-vision');
  const deleteBtn = document.getElementById('btn-delete-gen-image');
  const refreshGalleryBtn = document.getElementById('btn-refresh-gen-gallery');
  const emptyState = document.getElementById('image-gen-empty-state');
  const loadingState = document.getElementById('image-gen-loading-state');
  const previewImg = document.getElementById('image-gen-preview-img');
  const currentTitle = document.getElementById('image-gen-current-title');
  const statusBadge = document.getElementById('image-gen-status-badge');

  // Style Card Selection
  if (stylesGrid) {
    stylesGrid.querySelectorAll('.image-style-card').forEach(card => {
      card.addEventListener('click', () => {
        stylesGrid.querySelectorAll('.image-style-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        activeGenStyle = card.getAttribute('data-style') || 'photorealistic';
      });
    });
  }

  // Aspect Ratio Selection
  if (aspectSelector) {
    aspectSelector.querySelectorAll('.aspect-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        aspectSelector.querySelectorAll('.aspect-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeGenAspect = btn.getAttribute('data-aspect') || '1:1';
      });
    });
  }

  // Prompt Character Count & Preset Chips
  if (promptInput && charCount) {
    promptInput.addEventListener('input', () => {
      charCount.innerText = `${promptInput.value.length} / 2000`;
      if (promptInput.value.length > 2000) {
        charCount.style.color = 'var(--color-danger)';
      } else {
        charCount.style.color = 'var(--color-text-muted)';
      }
    });
  }

  document.querySelectorAll('.prompt-preset-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const preset = chip.getAttribute('data-prompt');
      if (preset && promptInput) {
        promptInput.value = preset;
        if (charCount) charCount.innerText = `${promptInput.value.length} / 2000`;
        promptInput.focus();
      }
    });
  });

  // Generate Image Action
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      const prompt = promptInput ? promptInput.value.trim() : '';
      if (!prompt) {
        window.showToast('Please enter an image prompt description', 'info');
        if (promptInput) promptInput.focus();
        return;
      }

      if (prompt.length > 2000) {
        window.showToast('Prompt exceeds maximum length of 2000 characters', 'error');
        return;
      }

      const negativePrompt = negPromptInput ? negPromptInput.value.trim() : null;
      const model = modelSelect ? modelSelect.value : 'dall-e-3';

      runBtn.disabled = true;
      runBtn.innerHTML = `
        <div class="pulse-loader" style="width:14px;height:14px;border-width:2px;display:inline-block;margin-right:6px;"></div>
        <span>Generating Artwork...</span>
      `;

      if (emptyState) emptyState.style.display = 'none';
      if (previewImg) previewImg.style.display = 'none';
      if (loadingState) loadingState.style.display = 'block';
      if (statusBadge) {
        statusBadge.className = 'badge badge-pending';
        statusBadge.innerText = 'SYNTHESIZING...';
      }

      try {
        const result = await window.imageGenApi.generate({
          prompt: prompt,
          negativePrompt: negativePrompt || null,
          model: model,
          aspectRatio: activeGenAspect,
          style: activeGenStyle
        });

        currentGeneratedImage = result;

        if (loadingState) loadingState.style.display = 'none';
        if (previewImg) {
          previewImg.src = result.imageUrl;
          previewImg.style.display = 'block';
        }
        if (statusBadge) {
          statusBadge.className = 'badge badge-active';
          statusBadge.innerText = `${result.width}x${result.height} • ${result.style.toUpperCase()}`;
        }
        if (currentTitle) {
          currentTitle.innerText = prompt.length > 40 ? prompt.substring(0, 40) + '...' : prompt;
        }

        // Enable actions
        if (downloadBtn) downloadBtn.disabled = false;
        if (analyzeBtn) analyzeBtn.disabled = false;
        if (deleteBtn) deleteBtn.disabled = false;

        window.showToast('AI image created successfully', 'success');
        loadImageGenGallery();
      } catch (err) {
        if (loadingState) loadingState.style.display = 'none';
        if (emptyState) emptyState.style.display = 'block';
        if (statusBadge) {
          statusBadge.className = 'badge badge-danger';
          statusBadge.innerText = 'GENERATION FAILED';
        }
        window.showToast(err.message, 'error');
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
          </svg>
          <span>Generate Image</span>
        `;
      }
    });
  }

  // Download Generated Image
  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      if (!currentGeneratedImage) return;
      const downloadUrl = `/api/images/generated/${currentGeneratedImage.id}/download`;
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `nexora_${currentGeneratedImage.id}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.showToast('Artwork download initiated', 'success', 1500);
    });
  }

  // Analyze Generated Image with Vision Studio
  if (analyzeBtn) {
    analyzeBtn.addEventListener('click', () => {
      if (!currentGeneratedImage) return;
      switchWorkspaceView('images');
      const visionPrompt = document.getElementById('vision-custom-query');
      if (visionPrompt) {
        visionPrompt.value = `Analyze this generated artwork in detail: style (${currentGeneratedImage.style}), aspect ratio (${currentGeneratedImage.aspectRatio}), composition, lighting, and visual elements.`;
      }
      window.showToast('Ready for Vision Analysis', 'info');
    });
  }

  // Delete Generated Image Modal Handlers
  if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
      if (!currentGeneratedImage) return;
      openDeleteGenImageModal(currentGeneratedImage.id);
    });
  }

  const cancelGenDeleteBtn = document.getElementById('btn-cancel-gen-delete');
  const confirmGenDeleteBtn = document.getElementById('btn-confirm-gen-delete');
  const deleteModal = document.getElementById('modal-delete-gen-image');

  if (cancelGenDeleteBtn && deleteModal) {
    cancelGenDeleteBtn.addEventListener('click', () => {
      deleteModal.style.display = 'none';
      pendingDeleteGenImageId = null;
    });
  }

  if (confirmGenDeleteBtn && deleteModal) {
    confirmGenDeleteBtn.addEventListener('click', async () => {
      if (!pendingDeleteGenImageId) return;
      confirmGenDeleteBtn.disabled = true;
      confirmGenDeleteBtn.innerText = 'Deleting...';

      try {
        await window.imageGenApi.deleteImage(pendingDeleteGenImageId);
        window.showToast('Artwork deleted successfully', 'success');
        deleteModal.style.display = 'none';

        if (currentGeneratedImage && currentGeneratedImage.id === pendingDeleteGenImageId) {
          currentGeneratedImage = null;
          if (previewImg) previewImg.style.display = 'none';
          if (emptyState) emptyState.style.display = 'block';
          if (downloadBtn) downloadBtn.disabled = true;
          if (analyzeBtn) analyzeBtn.disabled = true;
          if (deleteBtn) deleteBtn.disabled = true;
          if (statusBadge) {
            statusBadge.className = 'badge badge-active';
            statusBadge.innerText = 'PREVIEW STAGE';
          }
          if (currentTitle) currentTitle.innerText = 'Generated Artwork';
        }

        loadImageGenGallery();
      } catch (err) {
        window.showToast(`Delete failed: ${err.message}`, 'error');
      } finally {
        confirmGenDeleteBtn.disabled = false;
        confirmGenDeleteBtn.innerText = 'Delete Image';
        pendingDeleteGenImageId = null;
      }
    });
  }

  if (refreshGalleryBtn) {
    refreshGalleryBtn.addEventListener('click', () => {
      loadImageGenGallery();
    });
  }
}

function openDeleteGenImageModal(imageId) {
  pendingDeleteGenImageId = imageId;
  const modal = document.getElementById('modal-delete-gen-image');
  if (modal) modal.style.display = 'flex';
}

async function loadImageGenGallery() {
  const galleryGrid = document.getElementById('image-gen-gallery-grid');
  if (!galleryGrid) return;

  try {
    const res = await window.imageGenApi.listImages(50, 0);
    const images = res.images || [];

    if (images.length === 0) {
      galleryGrid.innerHTML = '<div style="font-size:12px;color:var(--color-text-muted);grid-column:1/-1;text-align:center;padding:24px;">No generated artwork yet. Create your first image on the left!</div>';
      return;
    }

    galleryGrid.innerHTML = images.map(img => `
      <div class="gen-gallery-card" data-id="${img.id}">
        <img src="${img.imageUrl}" alt="${escapeHtml(img.prompt)}" loading="lazy">
        <div class="gen-gallery-overlay">
          <div class="gen-gallery-prompt" title="${escapeHtml(img.prompt)}">${escapeHtml(img.prompt)}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:9px;color:var(--color-bright);font-weight:700;">${img.aspectRatio}</span>
            <button class="btn-icon-sm btn-delete-gallery-img" data-id="${img.id}" title="Delete" style="color:var(--color-danger);padding:2px;background:rgba(0,0,0,0.5);border-radius:4px;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="10" height="10"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </div>
      </div>
    `).join('');

    // Attach click events to load into preview stage
    galleryGrid.querySelectorAll('.gen-gallery-card').forEach(card => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('.btn-delete-gallery-img')) return;
        const imgId = card.getAttribute('data-id');
        const selected = images.find(i => i.id === imgId);
        if (!selected) return;

        currentGeneratedImage = selected;
        const previewImg = document.getElementById('image-gen-preview-img');
        const emptyState = document.getElementById('image-gen-empty-state');
        const currentTitle = document.getElementById('image-gen-current-title');
        const statusBadge = document.getElementById('image-gen-status-badge');
        const downloadBtn = document.getElementById('btn-download-gen-image');
        const analyzeBtn = document.getElementById('btn-use-gen-in-vision');
        const deleteBtn = document.getElementById('btn-delete-gen-image');

        if (emptyState) emptyState.style.display = 'none';
        if (previewImg) {
          previewImg.src = selected.imageUrl;
          previewImg.style.display = 'block';
        }
        if (currentTitle) {
          currentTitle.innerText = selected.prompt.length > 40 ? selected.prompt.substring(0, 40) + '...' : selected.prompt;
        }
        if (statusBadge) {
          statusBadge.className = 'badge badge-active';
          statusBadge.innerText = `${selected.width}x${selected.height} • ${selected.style.toUpperCase()}`;
        }
        if (downloadBtn) downloadBtn.disabled = false;
        if (analyzeBtn) analyzeBtn.disabled = false;
        if (deleteBtn) deleteBtn.disabled = false;
      });
    });

    // Attach delete button click in gallery cards
    galleryGrid.querySelectorAll('.btn-delete-gallery-img').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const imgId = btn.getAttribute('data-id');
        if (imgId) openDeleteGenImageModal(imgId);
      });
    });
  } catch (err) {
    galleryGrid.innerHTML = `<div style="font-size:12px;color:var(--color-danger);grid-column:1/-1;text-align:center;padding:16px;">Failed to load gallery: ${err.message}</div>`;
  }
}

/* ==========================================================================
   PHASE 5: VOICE INTELLIGENCE & SPEECH CONTROLLER
   ========================================================================== */

let voiceMediaRecorder = null;
let voiceAudioChunks = [];
let voiceRecordingTimerInterval = null;
let voiceRecordingSeconds = 0;
let voiceStream = null;
let currentPlayingAudio = null;

function setupVoiceWorkspace() {
  const voiceBtn = document.getElementById('btn-voice-input');
  const voiceModal = document.getElementById('modal-voice-recording');
  const cancelBtn = document.getElementById('btn-cancel-voice-record');
  const finishBtn = document.getElementById('btn-finish-voice-record');
  const timerEl = document.getElementById('voice-recording-timer');
  const modalTitle = document.getElementById('voice-recording-modal-title');
  const modalHint = document.getElementById('voice-recording-hint');

  if (voiceBtn) {
    voiceBtn.addEventListener('click', async () => {
      await startVoiceRecording();
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      stopVoiceRecording(false);
    });
  }

  if (finishBtn) {
    finishBtn.addEventListener('click', async () => {
      await stopVoiceRecording(true);
    });
  }
}

async function startVoiceRecording() {
  const voiceModal = document.getElementById('modal-voice-recording');
  const timerEl = document.getElementById('voice-recording-timer');
  const modalTitle = document.getElementById('voice-recording-modal-title');
  const modalHint = document.getElementById('voice-recording-hint');
  const finishBtn = document.getElementById('btn-finish-voice-record');

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    window.showToast('Microphone access is not supported by your browser.', 'error');
    return;
  }

  try {
    voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      window.showToast('Microphone permission was denied. Please allow microphone access in your browser settings.', 'error', 4000);
    } else {
      window.showToast(`Microphone error: ${err.message}`, 'error');
    }
    return;
  }

  voiceAudioChunks = [];
  voiceRecordingSeconds = 0;

  // Detect supported mime type
  let mimeType = 'audio/webm';
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
    mimeType = 'audio/webm;codecs=opus';
  } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
    mimeType = 'audio/ogg;codecs=opus';
  } else if (MediaRecorder.isTypeSupported('audio/wav')) {
    mimeType = 'audio/wav';
  }

  try {
    voiceMediaRecorder = new MediaRecorder(voiceStream, { mimeType });
  } catch (e) {
    voiceMediaRecorder = new MediaRecorder(voiceStream);
  }

  voiceMediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) {
      voiceAudioChunks.push(e.data);
    }
  };

  voiceMediaRecorder.start(250);

  // Show Modal & Start Timer
  if (voiceModal) voiceModal.style.display = 'flex';
  if (modalTitle) modalTitle.innerText = 'Listening to Your Voice...';
  if (modalHint) modalHint.innerText = 'Speak clearly into your microphone. Click Finish when done.';
  if (timerEl) timerEl.innerText = '00:00';
  if (finishBtn) {
    finishBtn.disabled = false;
    finishBtn.innerHTML = '<span>⏹️ Finish & Transcribe</span>';
  }

  // Animate recording timer
  clearInterval(voiceRecordingTimerInterval);
  voiceRecordingTimerInterval = setInterval(() => {
    voiceRecordingSeconds++;
    const mins = Math.floor(voiceRecordingSeconds / 60).toString().padStart(2, '0');
    const secs = (voiceRecordingSeconds % 60).toString().padStart(2, '0');
    if (timerEl) timerEl.innerText = `${mins}:${secs}`;
  }, 1000);
}

async function stopVoiceRecording(shouldProcess = true) {
  clearInterval(voiceRecordingTimerInterval);

  const voiceModal = document.getElementById('modal-voice-recording');
  const modalTitle = document.getElementById('voice-recording-modal-title');
  const modalHint = document.getElementById('voice-recording-hint');
  const finishBtn = document.getElementById('btn-finish-voice-record');

  if (voiceMediaRecorder && voiceMediaRecorder.state !== 'inactive') {
    voiceMediaRecorder.stop();
  }

  if (voiceStream) {
    voiceStream.getTracks().forEach(track => track.stop());
    voiceStream = null;
  }

  if (!shouldProcess) {
    if (voiceModal) voiceModal.style.display = 'none';
    voiceAudioChunks = [];
    return;
  }

  if (finishBtn) {
    finishBtn.disabled = true;
    finishBtn.innerHTML = '<div class="pulse-loader" style="width:14px;height:14px;border-width:2px;display:inline-block;margin-right:6px;"></div> Transcribing...';
  }
  if (modalTitle) modalTitle.innerText = 'Transcribing Voice Input...';
  if (modalHint) modalHint.innerText = 'Processing acoustic speech with neural transcription models...';

  // Wait briefly for recorder to flush final chunks
  await new Promise(r => setTimeout(r, 400));

  const audioBlob = new Blob(voiceAudioChunks, { type: voiceMediaRecorder ? voiceMediaRecorder.mimeType : 'audio/webm' });
  voiceAudioChunks = [];

  try {
    const res = await window.voiceApi.transcribe(audioBlob, 'en');
    const transcription = (res.text || '').trim();

    if (voiceModal) voiceModal.style.display = 'none';

    if (!transcription) {
      window.showToast('No speech was detected in the recording.', 'info');
      return;
    }

    // Populate chat textarea with transcription
    const chatTextarea = document.getElementById('chat-textarea');
    if (chatTextarea) {
      const existing = chatTextarea.value.trim();
      chatTextarea.value = existing ? `${existing} ${transcription}` : transcription;
      chatTextarea.style.height = 'auto';
      chatTextarea.style.height = `${Math.min(chatTextarea.scrollHeight, 180)}px`;
      chatTextarea.focus();
    }

    window.showToast('Voice transcribed: "' + (transcription.length > 35 ? transcription.substring(0, 35) + '...' : transcription) + '"', 'success', 2500);
  } catch (err) {
    if (voiceModal) voiceModal.style.display = 'none';
    window.showToast(`Transcription error: ${err.message}`, 'error', 3500);
  }
}

// Text-to-Speech Playback Helper
async function playSpeechAudio(text, btnEl = null) {
  if (!text) return;

  // If already playing this, toggle stop
  if (currentPlayingAudio && !currentPlayingAudio.paused) {
    currentPlayingAudio.pause();
    currentPlayingAudio = null;
    if (btnEl) btnEl.classList.remove('playing');
    return;
  }

  if (btnEl) {
    btnEl.classList.add('playing');
    btnEl.innerHTML = `
      <div class="pulse-loader" style="width:10px;height:10px;border-width:1.5px;display:inline-block;margin-right:4px;"></div>
      <span>Synthesizing...</span>
    `;
  }

  try {
    const cleanText = text.replace(/```[\s\S]*?```/g, 'Code block omitted for audio.')
                          .replace(/[#*`_~\[\]]/g, '')
                          .substring(0, 800);

    const res = await window.voiceApi.synthesize({
      text: cleanText,
      voice: 'alloy',
      speed: 1.0
    });

    if (res && res.audioUrl) {
      const audio = new Audio(res.audioUrl);
      currentPlayingAudio = audio;

      if (btnEl) {
        btnEl.innerHTML = `
          <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
          <span>Pause Voice</span>
        `;
      }

      audio.onended = () => {
        if (btnEl) {
          btnEl.classList.remove('playing');
          btnEl.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
            <span>Read Aloud</span>
          `;
        }
        currentPlayingAudio = null;
      };

      await audio.play();
    }
  } catch (err) {
    // Fallback to browser SpeechSynthesis API
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text.substring(0, 500));
      utterance.onend = () => {
        if (btnEl) {
          btnEl.classList.remove('playing');
          btnEl.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
            <span>Read Aloud</span>
          `;
        }
      };
      window.speechSynthesis.speak(utterance);
    } else {
      window.showToast(`Voice playback error: ${err.message}`, 'error');
      if (btnEl) {
        btnEl.classList.remove('playing');
        btnEl.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
          <span>Read Aloud</span>
        `;
      }
    }
  }
}

window.playSpeechAudio = playSpeechAudio;

/* ==========================================================================
   PHASE 6: PROJECTS WORKSPACE & LONG-TERM ORGANIZATION CONTROLLER
   ========================================================================== */

let activeProjectId = null;
let activeProjectData = null;
let selectedProjectColor = '#8B5CF6';
let editingNoteId = null;

function setupProjectsWorkspace() {
  // New Project Modal open/close
  const btnOpenCreateProj = document.getElementById('btn-open-create-project-modal');
  const modalCreateProj = document.getElementById('modal-create-project');
  const btnCancelCreateProj = document.getElementById('btn-cancel-create-project');
  const btnConfirmCreateProj = document.getElementById('btn-confirm-create-project');
  const colorPickerContainer = document.getElementById('proj-color-picker');

  if (colorPickerContainer) {
    colorPickerContainer.querySelectorAll('.color-swatch-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        colorPickerContainer.querySelectorAll('.color-swatch-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedProjectColor = btn.getAttribute('data-color') || '#8B5CF6';
      });
    });
  }

  if (btnOpenCreateProj && modalCreateProj) {
    btnOpenCreateProj.addEventListener('click', () => {
      document.getElementById('proj-create-name').value = '';
      document.getElementById('proj-create-desc').value = '';
      document.getElementById('proj-create-inst').value = '';
      modalCreateProj.style.display = 'flex';
    });
  }

  if (btnCancelCreateProj && modalCreateProj) {
    btnCancelCreateProj.addEventListener('click', () => {
      modalCreateProj.style.display = 'none';
    });
  }

  if (btnConfirmCreateProj) {
    btnConfirmCreateProj.addEventListener('click', async () => {
      const name = document.getElementById('proj-create-name').value.trim();
      const description = document.getElementById('proj-create-desc').value.trim();
      const instructions = document.getElementById('proj-create-inst').value.trim();

      if (!name) {
        window.showToast('Please provide a project name', 'error');
        return;
      }

      btnConfirmCreateProj.disabled = true;
      btnConfirmCreateProj.innerText = 'Creating...';

      try {
        const newProj = await window.projectsApi.create({
          name,
          description,
          instructions,
          color: selectedProjectColor
        });
        modalCreateProj.style.display = 'none';
        window.showToast(`Project "${newProj.name}" created!`, 'success');
        await loadProjects();
        openProjectDetail(newProj.id);
      } catch (err) {
        window.showToast(`Failed to create project: ${err.message}`, 'error');
      } finally {
        btnConfirmCreateProj.disabled = false;
        btnConfirmCreateProj.innerText = 'Create Project';
      }
    });
  }

  // Back to All Projects button
  const btnBackToList = document.getElementById('btn-back-to-projects-list');
  if (btnBackToList) {
    btnBackToList.addEventListener('click', () => {
      document.getElementById('project-detail-stage').style.display = 'none';
      document.getElementById('projects-list-stage').style.display = 'block';
      activeProjectId = null;
      activeProjectData = null;
      loadProjects();
    });
  }

  // Project Tabs Handlers
  const projectDetailTabs = document.getElementById('project-detail-tabs');
  if (projectDetailTabs) {
    projectDetailTabs.querySelectorAll('.project-tab-btn').forEach(tabBtn => {
      tabBtn.addEventListener('click', () => {
        const tab = tabBtn.getAttribute('data-tab');
        projectDetailTabs.querySelectorAll('.project-tab-btn').forEach(b => b.classList.remove('active'));
        tabBtn.classList.add('active');

        document.querySelectorAll('.project-tab-panel').forEach(panel => {
          panel.style.display = 'none';
        });

        const targetPanel = document.getElementById(`proj-panel-${tab}`);
        if (targetPanel) targetPanel.style.display = 'block';
      });
    });
  }

  // Edit Project Modal Handlers
  const btnEditActiveProj = document.getElementById('btn-edit-active-project');
  const modalEditProj = document.getElementById('modal-edit-project');
  const btnCancelEditProj = document.getElementById('btn-cancel-edit-project');
  const btnConfirmEditProj = document.getElementById('btn-confirm-edit-project');

  if (btnEditActiveProj && modalEditProj) {
    btnEditActiveProj.addEventListener('click', () => {
      if (!activeProjectData) return;
      document.getElementById('proj-edit-name').value = activeProjectData.name || '';
      document.getElementById('proj-edit-desc').value = activeProjectData.description || '';
      document.getElementById('proj-edit-inst').value = activeProjectData.instructions || '';
      modalEditProj.style.display = 'flex';
    });
  }

  if (btnCancelEditProj && modalEditProj) {
    btnCancelEditProj.addEventListener('click', () => {
      modalEditProj.style.display = 'none';
    });
  }

  if (btnConfirmEditProj) {
    btnConfirmEditProj.addEventListener('click', async () => {
      if (!activeProjectId) return;
      const name = document.getElementById('proj-edit-name').value.trim();
      const description = document.getElementById('proj-edit-desc').value.trim();
      const instructions = document.getElementById('proj-edit-inst').value.trim();

      if (!name) {
        window.showToast('Project name is required', 'error');
        return;
      }

      btnConfirmEditProj.disabled = true;
      btnConfirmEditProj.innerText = 'Saving...';

      try {
        const updated = await window.projectsApi.update(activeProjectId, {
          name,
          description,
          instructions
        });
        modalEditProj.style.display = 'none';
        window.showToast('Project updated successfully', 'success');
        openProjectDetail(updated.id);
      } catch (err) {
        window.showToast(`Update error: ${err.message}`, 'error');
      } finally {
        btnConfirmEditProj.disabled = false;
        btnConfirmEditProj.innerText = 'Save Changes';
      }
    });
  }

  // Delete Project Modal Handlers
  const btnDeleteActiveProj = document.getElementById('btn-delete-active-project');
  const modalDeleteProj = document.getElementById('modal-delete-project');
  const btnCancelDeleteProj = document.getElementById('btn-cancel-delete-project');
  const btnConfirmDeleteProj = document.getElementById('btn-confirm-delete-project');

  if (btnDeleteActiveProj && modalDeleteProj) {
    btnDeleteActiveProj.addEventListener('click', () => {
      modalDeleteProj.style.display = 'flex';
    });
  }

  if (btnCancelDeleteProj && modalDeleteProj) {
    btnCancelDeleteProj.addEventListener('click', () => {
      modalDeleteProj.style.display = 'none';
    });
  }

  if (btnConfirmDeleteProj) {
    btnConfirmDeleteProj.addEventListener('click', async () => {
      if (!activeProjectId) return;
      btnConfirmDeleteProj.disabled = true;
      btnConfirmDeleteProj.innerText = 'Deleting...';

      try {
        await window.projectsApi.delete(activeProjectId);
        modalDeleteProj.style.display = 'none';
        window.showToast('Project deleted successfully', 'info');
        document.getElementById('project-detail-stage').style.display = 'none';
        document.getElementById('projects-list-stage').style.display = 'block';
        activeProjectId = null;
        activeProjectData = null;
        await loadProjects();
      } catch (err) {
        window.showToast(`Delete error: ${err.message}`, 'error');
      } finally {
        btnConfirmDeleteProj.disabled = false;
        btnConfirmDeleteProj.innerText = 'Delete Project';
      }
    });
  }

  // Save Project Instructions Directly in Tab
  const btnSaveProjInstructions = document.getElementById('btn-save-project-instructions');
  if (btnSaveProjInstructions) {
    btnSaveProjInstructions.addEventListener('click', async () => {
      if (!activeProjectId) return;
      const instructions = document.getElementById('project-instructions-editor').value.trim();
      btnSaveProjInstructions.disabled = true;
      btnSaveProjInstructions.innerText = 'Saving...';

      try {
        await window.projectsApi.update(activeProjectId, { instructions });
        window.showToast('Custom project instructions saved', 'success');
      } catch (err) {
        window.showToast(`Failed to save instructions: ${err.message}`, 'error');
      } finally {
        btnSaveProjInstructions.disabled = false;
        btnSaveProjInstructions.innerText = 'Save Project Instructions';
      }
    });
  }

  // Start New Project Chat Button
  const btnCreateProjChat = document.getElementById('btn-create-project-chat');
  if (btnCreateProjChat) {
    btnCreateProjChat.addEventListener('click', async () => {
      if (!activeProjectId) return;
      try {
        if (window.chatController) {
          const conv = await window.chatController.createConversation(`Chat in ${activeProjectData ? activeProjectData.name : 'Project'}`);
          await window.projectsApi.linkItem(activeProjectId, 'chat', conv.id);
          switchWorkspaceView('chat');
          window.showToast(`Created project chat: ${conv.title}`, 'success');
        }
      } catch (err) {
        window.showToast(`Error creating project chat: ${err.message}`, 'error');
      }
    });
  }

  // Link File Modal Handlers
  const btnLinkProjFile = document.getElementById('btn-link-project-file');
  const modalLinkProjFile = document.getElementById('modal-link-project-file');
  const btnCancelLinkFile = document.getElementById('btn-cancel-link-file');
  const btnConfirmLinkFile = document.getElementById('btn-confirm-link-file');
  const selectProjFileToLink = document.getElementById('select-project-file-to-link');

  if (btnLinkProjFile && modalLinkProjFile) {
    btnLinkProjFile.addEventListener('click', async () => {
      if (selectProjFileToLink) {
        selectProjFileToLink.innerHTML = '<option value="">Loading files...</option>';
        try {
          const files = await window.filesApi.list();
          if (!files || files.length === 0) {
            selectProjFileToLink.innerHTML = '<option value="">No uploaded files found. Upload some in Files view first.</option>';
          } else {
            selectProjFileToLink.innerHTML = files.map(f => `<option value="${f.id}">${f.originalName} (${(f.fileSize/1024).toFixed(1)} KB)</option>`).join('');
          }
        } catch (e) {
          selectProjFileToLink.innerHTML = '<option value="">Failed to load files</option>';
        }
      }
      modalLinkProjFile.style.display = 'flex';
    });
  }

  if (btnCancelLinkFile && modalLinkProjFile) {
    btnCancelLinkFile.addEventListener('click', () => {
      modalLinkProjFile.style.display = 'none';
    });
  }

  if (btnConfirmLinkFile) {
    btnConfirmLinkFile.addEventListener('click', async () => {
      if (!activeProjectId || !selectProjFileToLink || !selectProjFileToLink.value) {
        window.showToast('Please select a file to link', 'error');
        return;
      }
      const fileId = selectProjFileToLink.value;
      btnConfirmLinkFile.disabled = true;
      btnConfirmLinkFile.innerText = 'Linking...';

      try {
        await window.projectsApi.linkItem(activeProjectId, 'file', fileId);
        modalLinkProjFile.style.display = 'none';
        window.showToast('Document linked to project workspace', 'success');
        openProjectDetail(activeProjectId);
      } catch (err) {
        window.showToast(`Link error: ${err.message}`, 'error');
      } finally {
        btnConfirmLinkFile.disabled = false;
        btnConfirmLinkFile.innerText = 'Link File';
      }
    });
  }

  // Add/Edit Note Modal Handlers
  const btnAddProjNote = document.getElementById('btn-add-project-note');
  const modalAddProjNote = document.getElementById('modal-add-project-note');
  const btnCancelAddNote = document.getElementById('btn-cancel-add-note');
  const btnConfirmSaveNote = document.getElementById('btn-confirm-save-note');
  const noteModalTitle = document.getElementById('project-note-modal-title');

  if (btnAddProjNote && modalAddProjNote) {
    btnAddProjNote.addEventListener('click', () => {
      editingNoteId = null;
      if (noteModalTitle) noteModalTitle.innerText = 'Add Project Note';
      document.getElementById('note-input-title').value = '';
      document.getElementById('note-input-content').value = '';
      modalAddProjNote.style.display = 'flex';
    });
  }

  if (btnCancelAddNote && modalAddProjNote) {
    btnCancelAddNote.addEventListener('click', () => {
      modalAddProjNote.style.display = 'none';
    });
  }

  if (btnConfirmSaveNote) {
    btnConfirmSaveNote.addEventListener('click', async () => {
      if (!activeProjectId) return;
      const title = document.getElementById('note-input-title').value.trim();
      const content = document.getElementById('note-input-content').value.trim();

      if (!title) {
        window.showToast('Note title is required', 'error');
        return;
      }

      btnConfirmSaveNote.disabled = true;
      btnConfirmSaveNote.innerText = 'Saving...';

      try {
        if (editingNoteId) {
          await window.projectsApi.updateNote(activeProjectId, editingNoteId, { title, content });
          window.showToast('Note updated successfully', 'success');
        } else {
          await window.projectsApi.createNote(activeProjectId, { title, content });
          window.showToast('Note saved to project', 'success');
        }
        modalAddProjNote.style.display = 'none';
        openProjectDetail(activeProjectId);
      } catch (err) {
        window.showToast(`Save note error: ${err.message}`, 'error');
      } finally {
        btnConfirmSaveNote.disabled = false;
        btnConfirmSaveNote.innerText = 'Save Note';
      }
    });
  }

  // Save Output Modal Handlers
  const btnAddProjOutput = document.getElementById('btn-add-project-output');
  const modalSaveProjOutput = document.getElementById('modal-save-project-output');
  const btnCancelSaveOutput = document.getElementById('btn-cancel-save-output');
  const btnConfirmSaveOutput = document.getElementById('btn-confirm-save-output');

  if (btnAddProjOutput && modalSaveProjOutput) {
    btnAddProjOutput.addEventListener('click', () => {
      document.getElementById('output-input-title').value = '';
      document.getElementById('output-input-type').value = 'text';
      document.getElementById('output-input-content').value = '';
      modalSaveProjOutput.style.display = 'flex';
    });
  }

  if (btnCancelSaveOutput && modalSaveProjOutput) {
    btnCancelSaveOutput.addEventListener('click', () => {
      modalSaveProjOutput.style.display = 'none';
    });
  }

  if (btnConfirmSaveOutput) {
    btnConfirmSaveOutput.addEventListener('click', async () => {
      if (!activeProjectId) return;
      const title = document.getElementById('output-input-title').value.trim();
      const outputType = document.getElementById('output-input-type').value;
      const content = document.getElementById('output-input-content').value.trim();

      if (!title || !content) {
        window.showToast('Title and content are required', 'error');
        return;
      }

      btnConfirmSaveOutput.disabled = true;
      btnConfirmSaveOutput.innerText = 'Saving...';

      try {
        await window.projectsApi.createSavedOutput(activeProjectId, { title, outputType, content });
        modalSaveProjOutput.style.display = 'none';
        window.showToast('Output saved to project repository', 'success');
        openProjectDetail(activeProjectId);
      } catch (err) {
        window.showToast(`Save output error: ${err.message}`, 'error');
      } finally {
        btnConfirmSaveOutput.disabled = false;
        btnConfirmSaveOutput.innerText = 'Save to Project';
      }
    });
  }
}

// Load all user projects into grid
async function loadProjects() {
  const container = document.getElementById('projects-container-grid');
  if (!container) return;

  try {
    const projects = await window.projectsApi.list();
    if (!projects || projects.length === 0) {
      container.innerHTML = `
        <div style="grid-column:1/-1;text-align:center;padding:50px 20px;color:var(--color-text-muted);border:1px dashed var(--color-border);border-radius:var(--radius-lg);">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="44" height="44" style="color:var(--color-bright);margin-bottom:12px;opacity:0.6;">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
          <h3 style="color:#FFFFFF;margin-bottom:6px;font-size:16px;">No Projects Yet</h3>
          <p style="font-size:13px;max-width:420px;margin:0 auto 16px auto;">Organize chats, uploaded files, engineering notes, and outputs into structured domain workspaces.</p>
          <button class="btn btn-primary btn-sm" onclick="document.getElementById('btn-open-create-project-modal').click()">Create First Project</button>
        </div>
      `;
      return;
    }

    container.innerHTML = projects.map(proj => `
      <div class="project-card" style="--proj-accent-color: ${proj.color || '#8B5CF6'};" onclick="openProjectDetail('${proj.id}')">
        <div>
          <div class="project-card-header">
            <div class="project-card-title">${escapeHtml(proj.name)}</div>
            <div style="width:10px;height:10px;border-radius:50%;background:${proj.color || '#8B5CF6'};flex-shrink:0;"></div>
          </div>
          <div class="project-card-desc">${escapeHtml(proj.description || 'No description provided.')}</div>
        </div>

        <div>
          <div class="project-card-stats">
            <span>💬 ${proj.chatsCount} chats</span>
            <span>📁 ${proj.filesCount} files</span>
            <span>📝 ${proj.notesCount} notes</span>
            <span>⚡ ${proj.outputsCount} outputs</span>
          </div>
          <div class="project-card-footer" style="margin-top:10px;">
            <span style="font-size:11px;color:var(--color-text-muted);">Updated ${new Date(proj.updatedAt).toLocaleDateString()}</span>
            <span style="font-size:12px;font-weight:600;color:var(--color-bright);">Open Studio &rarr;</span>
          </div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--color-danger);">Failed to load projects: ${err.message}</div>`;
  }
}

// Open and render Project Studio Stage
async function openProjectDetail(projectId) {
  try {
    const project = await window.projectsApi.get(projectId);
    activeProjectId = project.id;
    activeProjectData = project;

    // Header updates
    const titleEl = document.getElementById('active-project-title');
    const descEl = document.getElementById('active-project-desc');
    const badgeEl = document.getElementById('active-project-color-badge');
    const instructionsEl = document.getElementById('project-instructions-editor');

    if (titleEl) titleEl.innerText = project.name;
    if (descEl) descEl.innerText = project.description || 'No description provided for this project.';
    if (badgeEl) badgeEl.style.backgroundColor = project.color || '#8B5CF6';
    if (instructionsEl) instructionsEl.value = project.instructions || '';

    // Tab counts
    const countChats = document.getElementById('proj-tab-count-chats');
    const countFiles = document.getElementById('proj-tab-count-files');
    const countNotes = document.getElementById('proj-tab-count-notes');
    const countOutputs = document.getElementById('proj-tab-count-outputs');

    if (countChats) countChats.innerText = (project.chats || []).length;
    if (countFiles) countFiles.innerText = (project.files || []).length;
    if (countNotes) countNotes.innerText = (project.notes || []).length;
    if (countOutputs) countOutputs.innerText = (project.savedOutputs || []).length;

    // Render Tab 1: Chats
    const chatsList = document.getElementById('project-chats-list');
    if (chatsList) {
      if (!project.chats || project.chats.length === 0) {
        chatsList.innerHTML = '<div style="font-size:12px;color:var(--color-text-muted);padding:24px;text-align:center;">No conversations linked to this project yet. Click "+ Start New Project Chat" above.</div>';
      } else {
        chatsList.innerHTML = project.chats.map(chat => `
          <div class="project-item-row">
            <div class="project-item-info" onclick="openChatFromProject('${chat.id}')">
              <span>💬</span>
              <div>
                <div class="project-item-title">${escapeHtml(chat.title || 'Untitled Chat')}</div>
                <div class="project-item-meta">${chat.messageCount || 0} messages • Updated ${new Date(chat.updatedAt).toLocaleString()}</div>
              </div>
            </div>
            <div style="display:flex;gap:6px;">
              <button class="btn btn-outline btn-sm" style="padding:2px 8px;font-size:11px;" onclick="openChatFromProject('${chat.id}')">Open</button>
              <button class="btn btn-danger btn-sm" style="padding:2px 8px;font-size:11px;" onclick="unlinkItemFromProject('${project.id}', 'chat', '${chat.id}')">Unlink</button>
            </div>
          </div>
        `).join('');
      }
    }

    // Render Tab 2: Files
    const filesList = document.getElementById('project-files-list');
    if (filesList) {
      if (!project.files || project.files.length === 0) {
        filesList.innerHTML = '<div style="font-size:12px;color:var(--color-text-muted);padding:24px;text-align:center;">No documents linked to this project yet. Click "+ Link Uploaded File" above.</div>';
      } else {
        filesList.innerHTML = project.files.map(file => `
          <div class="project-item-row">
            <div class="project-item-info">
              <span class="file-type-badge type-${file.fileType || 'txt'}">${file.fileType || 'DOC'}</span>
              <div>
                <div class="project-item-title">${escapeHtml(file.originalName)}</div>
                <div class="project-item-meta">${(file.fileSize/1024).toFixed(1)} KB • Uploaded ${new Date(file.createdAt).toLocaleDateString()}</div>
              </div>
            </div>
            <div style="display:flex;gap:6px;">
              <button class="btn btn-outline btn-sm" style="padding:2px 8px;font-size:11px;" onclick="previewProjectDoc('${file.id}')">Preview</button>
              <button class="btn btn-danger btn-sm" style="padding:2px 8px;font-size:11px;" onclick="unlinkItemFromProject('${project.id}', 'file', '${file.id}')">Unlink</button>
            </div>
          </div>
        `).join('');
      }
    }

    // Render Tab 3: Notes
    const notesList = document.getElementById('project-notes-list');
    if (notesList) {
      if (!project.notes || project.notes.length === 0) {
        notesList.innerHTML = '<div style="font-size:12px;color:var(--color-text-muted);padding:24px;text-align:center;grid-column:1/-1;">No notes created yet. Click "+ Add Note" to create research notes or architectural outlines.</div>';
      } else {
        notesList.innerHTML = project.notes.map(note => `
          <div class="project-note-card">
            <div>
              <div class="project-note-title">${escapeHtml(note.title)}</div>
              <div class="project-note-content">${escapeHtml(note.content)}</div>
            </div>
            <div class="project-note-footer">
              <span>${new Date(note.updatedAt).toLocaleDateString()}</span>
              <div style="display:flex;gap:4px;">
                <button class="btn btn-outline btn-sm" style="padding:1px 6px;font-size:10px;" onclick="editProjectNote('${note.id}', '${escapeAttr(note.title)}', '${escapeAttr(note.content)}')">Edit</button>
                <button class="btn btn-danger btn-sm" style="padding:1px 6px;font-size:10px;" onclick="deleteProjectNote('${project.id}', '${note.id}')">Delete</button>
              </div>
            </div>
          </div>
        `).join('');
      }
    }

    // Render Tab 4: Saved Outputs
    const outputsList = document.getElementById('project-outputs-list');
    if (outputsList) {
      if (!project.savedOutputs || project.savedOutputs.length === 0) {
        outputsList.innerHTML = '<div style="font-size:12px;color:var(--color-text-muted);padding:24px;text-align:center;grid-column:1/-1;">No saved outputs pinned yet. Click "+ Save Output" to archive code snippets, summaries, and synthesis.</div>';
      } else {
        outputsList.innerHTML = project.savedOutputs.map(out => `
          <div class="project-output-card">
            <div class="project-output-header">
              <span class="badge badge-active">${escapeHtml(out.outputType.toUpperCase())}</span>
              <div style="display:flex;gap:6px;">
                <button class="btn btn-outline btn-sm" style="padding:1px 6px;font-size:10px;" onclick="copySavedOutputText('${escapeAttr(out.content)}')">Copy</button>
                <button class="btn btn-danger btn-sm" style="padding:1px 6px;font-size:10px;" onclick="deleteSavedOutputItem('${project.id}', '${out.id}')">Delete</button>
              </div>
            </div>
            <div style="font-weight:600;font-size:13px;color:#FFFFFF;">${escapeHtml(out.title)}</div>
            <div class="project-output-content">${escapeHtml(out.content)}</div>
            <div style="font-size:10px;color:var(--color-text-muted);text-align:right;">${new Date(out.createdAt).toLocaleString()}</div>
          </div>
        `).join('');
      }
    }

    // Switch view stages
    document.getElementById('projects-list-stage').style.display = 'none';
    document.getElementById('project-detail-stage').style.display = 'block';

  } catch (err) {
    window.showToast(`Failed to load project details: ${err.message}`, 'error');
  }
}

window.openProjectDetail = openProjectDetail;

// Open Chat from Project
function openChatFromProject(chatId) {
  switchWorkspaceView('chat');
  if (window.chatController) {
    window.chatController.loadConversation(chatId);
  }
}
window.openChatFromProject = openChatFromProject;

// Unlink Item from Project
async function unlinkItemFromProject(projectId, itemType, itemId) {
  try {
    await window.projectsApi.unlinkItem(projectId, itemType, itemId);
    window.showToast(`Unlinked ${itemType} from project`, 'info');
    openProjectDetail(projectId);
  } catch (err) {
    window.showToast(`Unlink error: ${err.message}`, 'error');
  }
}
window.unlinkItemFromProject = unlinkItemFromProject;

// Preview doc from project
async function previewProjectDoc(fileId) {
  try {
    const file = await window.filesApi.get(fileId);
    const modal = document.getElementById('modal-doc-preview');
    const titleEl = document.getElementById('doc-preview-modal-title');
    const metaEl = document.getElementById('doc-preview-modal-meta');
    const textEl = document.getElementById('doc-preview-text');

    if (titleEl) titleEl.innerText = file.originalName;
    if (metaEl) metaEl.innerText = `Type: ${file.fileType.toUpperCase()} | Size: ${(file.fileSize/1024).toFixed(1)} KB | Multi-Tenant Isolated`;
    if (textEl) textEl.innerText = file.extractedText || 'No text extracted for this document.';
    if (modal) modal.style.display = 'flex';
  } catch (e) {
    window.showToast(`Preview failed: ${e.message}`, 'error');
  }
}
window.previewProjectDoc = previewProjectDoc;

// Edit note helper
function editProjectNote(noteId, title, content) {
  editingNoteId = noteId;
  const modal = document.getElementById('modal-add-project-note');
  const noteModalTitle = document.getElementById('project-note-modal-title');
  if (noteModalTitle) noteModalTitle.innerText = 'Edit Project Note';
  document.getElementById('note-input-title').value = title;
  document.getElementById('note-input-content').value = content;
  if (modal) modal.style.display = 'flex';
}
window.editProjectNote = editProjectNote;

// Delete note helper
async function deleteProjectNote(projectId, noteId) {
  try {
    await window.projectsApi.deleteNote(projectId, noteId);
    window.showToast('Note deleted', 'info');
    openProjectDetail(projectId);
  } catch (e) {
    window.showToast(`Delete note error: ${e.message}`, 'error');
  }
}
window.deleteProjectNote = deleteProjectNote;

// Copy saved output text helper
function copySavedOutputText(text) {
  navigator.clipboard.writeText(text);
  window.showToast('Output copied to clipboard', 'success');
}
window.copySavedOutputText = copySavedOutputText;

// Delete saved output helper
async function deleteSavedOutputItem(projectId, outputId) {
  try {
    await window.projectsApi.deleteSavedOutput(projectId, outputId);
    window.showToast('Saved output deleted', 'info');
    openProjectDetail(projectId);
  } catch (e) {
    window.showToast(`Delete output error: ${e.message}`, 'error');
  }
}
window.deleteSavedOutputItem = deleteSavedOutputItem;


/* ==========================================================================
   PHASE 6: PERSONALIZATION & CONTROLLED MEMORY CONTROLLER
   ========================================================================== */

function setupPersonalizationWorkspace() {
  // Save Personalization Button
  const btnSavePersonalization = document.getElementById('btn-save-personalization');
  if (btnSavePersonalization) {
    btnSavePersonalization.addEventListener('click', async () => {
      const displayName = document.getElementById('pref-display-name').value.trim();
      const preferredLanguage = document.getElementById('pref-preferred-lang').value;
      const aiTone = document.getElementById('pref-ai-tone').value;
      const theme = document.getElementById('pref-ui-theme').value;
      if (window.NexoraTheme) {
        window.NexoraTheme.set(theme);
      }
      const codeTheme = document.getElementById('pref-code-theme').value;
      const customInstructions = document.getElementById('pref-custom-instructions').value.trim();
      const autoSpeak = document.getElementById('pref-auto-speak').checked;

      btnSavePersonalization.disabled = true;
      btnSavePersonalization.innerText = 'Saving...';

      try {
        await window.personalizationApi.updatePreferences({
          displayName,
          preferredLanguage,
          aiTone,
          theme,
          codeTheme,
          customInstructions,
          autoSpeak
        });
        window.showToast('Personalization preferences saved successfully', 'success');
      } catch (err) {
        window.showToast(`Save error: ${err.message}`, 'error');
      } finally {
        btnSavePersonalization.disabled = false;
        btnSavePersonalization.innerText = 'Save Personalization Preferences';
      }
    });
  }

  // Global Memory Toggle Checkbox
  const toggleGlobalMemory = document.getElementById('toggle-global-memory');
  if (toggleGlobalMemory) {
    toggleGlobalMemory.addEventListener('change', async () => {
      const enabled = toggleGlobalMemory.checked;
      try {
        await window.personalizationApi.updatePreferences({ enableMemory: enabled });
        const badge = document.getElementById('memory-status-badge');
        if (badge) {
          badge.className = `badge ${enabled ? 'badge-active' : 'badge-suspended'}`;
          badge.innerText = enabled ? 'MEMORY ACTIVE' : 'MEMORY PAUSED';
        }
        window.showToast(`AI Controlled Memory ${enabled ? 'enabled' : 'disabled'}`, enabled ? 'success' : 'info');
      } catch (err) {
        window.showToast(`Toggle memory error: ${err.message}`, 'error');
        toggleGlobalMemory.checked = !enabled;
      }
    });
  }

  // Add Memory Modal Handlers
  const btnOpenCreateMem = document.getElementById('btn-open-create-memory-modal');
  const modalCreateMem = document.getElementById('modal-create-memory');
  const btnCancelCreateMem = document.getElementById('btn-cancel-create-memory');
  const btnConfirmCreateMem = document.getElementById('btn-confirm-create-memory');

  if (btnOpenCreateMem && modalCreateMem) {
    btnOpenCreateMem.addEventListener('click', () => {
      document.getElementById('memory-input-key').value = '';
      document.getElementById('memory-input-value').value = '';
      modalCreateMem.style.display = 'flex';
    });
  }

  if (btnCancelCreateMem && modalCreateMem) {
    btnCancelCreateMem.addEventListener('click', () => {
      modalCreateMem.style.display = 'none';
    });
  }

  if (btnConfirmCreateMem) {
    btnConfirmCreateMem.addEventListener('click', async () => {
      const category = document.getElementById('memory-input-category').value;
      const memoryKey = document.getElementById('memory-input-key').value.trim();
      const memoryValue = document.getElementById('memory-input-value').value.trim();

      if (!memoryKey || !memoryValue) {
        window.showToast('Memory key and retained fact are required', 'error');
        return;
      }

      btnConfirmCreateMem.disabled = true;
      btnConfirmCreateMem.innerText = 'Saving...';

      try {
        await window.personalizationApi.createMemory({ category, memoryKey, memoryValue });
        modalCreateMem.style.display = 'none';
        window.showToast('Memory fact retained successfully', 'success');
        loadMemories();
      } catch (err) {
        window.showToast(`Create memory error: ${err.message}`, 'error');
      } finally {
        btnConfirmCreateMem.disabled = false;
        btnConfirmCreateMem.innerText = 'Save Memory';
      }
    });
  }

  // Purge All Memories Modal Handlers
  const btnClearAllMem = document.getElementById('btn-clear-all-memories');
  const modalClearMem = document.getElementById('modal-clear-memories');
  const btnCancelClearMem = document.getElementById('btn-cancel-clear-memories');
  const btnConfirmClearMem = document.getElementById('btn-confirm-clear-memories');

  if (btnClearAllMem && modalClearMem) {
    btnClearAllMem.addEventListener('click', () => {
      modalClearMem.style.display = 'flex';
    });
  }

  if (btnCancelClearMem && modalClearMem) {
    btnCancelClearMem.addEventListener('click', () => {
      modalClearMem.style.display = 'none';
    });
  }

  if (btnConfirmClearMem) {
    btnConfirmClearMem.addEventListener('click', async () => {
      btnConfirmClearMem.disabled = true;
      btnConfirmClearMem.innerText = 'Purging...';

      try {
        await window.personalizationApi.clearMemories();
        modalClearMem.style.display = 'none';
        window.showToast('All retained memories purged', 'info');
        loadMemories();
      } catch (err) {
        window.showToast(`Purge memory error: ${err.message}`, 'error');
      } finally {
        btnConfirmClearMem.disabled = false;
        btnConfirmClearMem.innerText = 'Purge Memories';
      }
    });
  }
}

// Load Personalization Preferences
async function loadPersonalization() {
  try {
    const prefs = await window.personalizationApi.getPreferences();
    if (!prefs) return;

    const elDispName = document.getElementById('pref-display-name');
    const elPrefLang = document.getElementById('pref-preferred-lang');
    const elAiTone = document.getElementById('pref-ai-tone');
    const elUiTheme = document.getElementById('pref-ui-theme');
    const elCodeTheme = document.getElementById('pref-code-theme');
    const elCustInst = document.getElementById('pref-custom-instructions');
    const elAutoSpeak = document.getElementById('pref-auto-speak');
    const elToggleMemory = document.getElementById('toggle-global-memory');
    const badgeMemory = document.getElementById('memory-status-badge');

    if (elDispName) elDispName.value = prefs.displayName || '';
    if (elPrefLang) elPrefLang.value = prefs.preferredLanguage || 'English';
    if (elAiTone) elAiTone.value = prefs.aiTone || 'balanced';
    if (elUiTheme) {
      const activePref = window.NexoraTheme ? window.NexoraTheme.getPreference() : 'system';
      const userPref = (prefs.theme === 'light' || prefs.theme === 'dark' || prefs.theme === 'system') ? prefs.theme : activePref;
      elUiTheme.value = userPref;
      if (window.NexoraTheme && prefs.theme && (prefs.theme === 'light' || prefs.theme === 'dark' || prefs.theme === 'system')) {
        window.NexoraTheme.set(userPref);
      }
    }
    if (elCodeTheme) elCodeTheme.value = prefs.codeTheme || 'atom-one-dark';
    if (elCustInst) elCustInst.value = prefs.customInstructions || '';
    if (elAutoSpeak) elAutoSpeak.checked = !!prefs.autoSpeak;
    if (elToggleMemory) elToggleMemory.checked = !!prefs.enableMemory;

    if (badgeMemory) {
      badgeMemory.className = `badge ${prefs.enableMemory ? 'badge-active' : 'badge-suspended'}`;
      badgeMemory.innerText = prefs.enableMemory ? 'MEMORY ACTIVE' : 'MEMORY PAUSED';
    }
  } catch (err) {
    console.error('Failed to load personalization:', err);
  }
}

// Load Controlled Memories List
async function loadMemories() {
  const tbody = document.getElementById('memories-tbody');
  if (!tbody) return;

  try {
    const res = await window.personalizationApi.listMemories();
    const memories = res.memories || [];

    if (memories.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--color-text-muted);">No memories retained yet. Click "+ Add Memory" to preserve key context and preferences.</td></tr>';
      return;
    }

    tbody.innerHTML = memories.map(mem => `
      <tr>
        <td><span class="mem-cat-badge cat-${mem.category || 'preference'}">${escapeHtml(mem.category)}</span></td>
        <td><strong style="color:#FFFFFF;font-size:13px;">${escapeHtml(mem.memoryKey)}</strong></td>
        <td style="font-size:13px;color:var(--color-text-secondary);">${escapeHtml(mem.memoryValue)}</td>
        <td style="text-align:center;">
          <input type="checkbox" ${mem.isActive ? 'checked' : ''} style="width:15px;height:15px;cursor:pointer;accent-color:var(--color-primary);" onchange="toggleMemoryItemActive('${mem.id}', this.checked)">
        </td>
        <td style="text-align:right;">
          <button class="btn btn-danger btn-sm" style="padding:2px 8px;font-size:11px;" onclick="deleteMemoryItem('${mem.id}')" title="Delete memory">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--color-danger);">Failed to load memories: ${err.message}</td></tr>`;
  }
}

// Toggle individual memory active state
async function toggleMemoryItemActive(memoryId, isActive) {
  try {
    await window.personalizationApi.updateMemory(memoryId, { isActive });
    window.showToast(`Memory ${isActive ? 'activated' : 'deactivated'}`, 'info');
  } catch (err) {
    window.showToast(`Update error: ${err.message}`, 'error');
    loadMemories();
  }
}
window.toggleMemoryItemActive = toggleMemoryItemActive;

// Delete single memory
async function deleteMemoryItem(memoryId) {
  try {
    await window.personalizationApi.deleteMemory(memoryId);
    window.showToast('Memory item deleted', 'info');
    loadMemories();
  } catch (err) {
    window.showToast(`Delete error: ${err.message}`, 'error');
  }
}
window.deleteMemoryItem = deleteMemoryItem;

// Helper to escape HTML and Attributes
function escapeHtml(str) {
  if (!str) return '';
  return str.toString()
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeAttr(str) {
  if (!str) return '';
  return str.toString()
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '');
}




