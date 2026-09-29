/**
 * NEXORA AI - API Client & Session Management Module
 */

function getApiBase() {
  if (typeof window !== 'undefined' && window.AndroidBridge && typeof window.AndroidBridge.getServerUrl === 'function') {
    const custom = window.AndroidBridge.getServerUrl();
    if (custom && custom.trim().length > 0) {
      return custom.replace(/\/+$/, '') + '/api';
    }
  }
  return '/api';
}

// Toast Notification Manager
function showToast(message, type = 'info', duration = 4000) {
  if (typeof window !== 'undefined' && window.AndroidBridge && typeof window.AndroidBridge.vibrate === 'function') {
    window.AndroidBridge.vibrate(type === 'error' ? 'heavy' : 'light');
  }

  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let iconSvg = '';
  if (type === 'success') {
    iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M20 6L9 17l-5-5"/></svg>';
  } else if (type === 'error') {
    iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
  } else {
    iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
  }

  toast.innerHTML = `
    <span style="display:flex;align-items:center;color:${type === 'success' ? '#10B981' : type === 'error' ? '#EF4444' : '#A78BFA'}">${iconSvg}</span>
    <div style="flex:1">${message}</div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Token Storage with Android KeyStore Synchronization
const TokenManager = {
  getToken() {
    if (typeof window !== 'undefined' && window.AndroidBridge && typeof window.AndroidBridge.getToken === 'function') {
      const nativeToken = window.AndroidBridge.getToken();
      if (nativeToken && nativeToken.trim().length > 0) {
        return nativeToken.trim();
      }
    }
    return localStorage.getItem('nexora_token');
  },
  setToken(token) {
    if (token) {
      localStorage.setItem('nexora_token', token);
      if (typeof window !== 'undefined' && window.AndroidBridge && typeof window.AndroidBridge.saveToken === 'function') {
        window.AndroidBridge.saveToken(token);
      }
    }
  },
  removeToken() {
    localStorage.removeItem('nexora_token');
    if (typeof window !== 'undefined' && window.AndroidBridge && typeof window.AndroidBridge.clearToken === 'function') {
      window.AndroidBridge.clearToken();
    }
  }
};

// Generic HTTP Request Handler
async function request(endpoint, options = {}) {
  const url = `${getApiBase()}${endpoint}`;

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  const token = TokenManager.getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
    credentials: 'include' // include httpOnly cookies
  };

  try {
    const response = await fetch(url, config);
    let data;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = { detail: await response.text() };
    }

    if (!response.ok) {
      let errorMsg = 'An unexpected error occurred';
      if (data && data.detail) {
        if (Array.isArray(data.detail)) {
          // Pydantic validation error array
          errorMsg = data.detail.map(err => err.msg || err.message).join(', ');
        } else {
          errorMsg = data.detail;
        }
      } else if (data && data.message) {
        errorMsg = data.message;
      }
      throw new Error(errorMsg);
    }

    return data;
  } catch (err) {
    if (err.name === 'TypeError' && err.message && err.message.toLowerCase().includes('fetch')) {
      throw new Error('Unable to connect to server. Please check your network connection.');
    }
    throw err;
  }
}

// Auth API Endpoints
const authApi = {
  async signup(email, password) {
    const res = await request('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    if (res.token) {
      TokenManager.setToken(res.token);
    }
    return res;
  },

  async login(email, password, rememberMe = false) {
    const res = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, rememberMe })
    });
    if (res.token) {
      TokenManager.setToken(res.token);
    }
    return res;
  },

  async logout() {
    try {
      await request('/auth/logout', { method: 'POST' });
    } catch (e) {
      // proceed even if server-side call errors
    } finally {
      TokenManager.removeToken();
    }
  },

  async getMe() {
    return await request('/auth/me', { method: 'GET' });
  },

  async forgotPassword(email) {
    return await request('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  },

  async resetPassword(token, newPassword) {
    return await request('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, newPassword })
    });
  },

  async verifyEmail(token) {
    return await request('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token })
    });
  },

  async resendVerification() {
    return await request('/auth/resend-verification', {
      method: 'POST'
    });
  }
};

// User Profile API Endpoints
const userApi = {
  async getProfile() {
    return await request('/user/profile', { method: 'GET' });
  },

  async changePassword(currentPassword, newPassword) {
    return await request('/user/change-password', {
      method: 'POST',
      body: JSON.stringify({ currentPassword, newPassword })
    });
  },

  async getActivity() {
    return await request('/user/activity', { method: 'GET' });
  },

  async deleteAccount() {
    return await request('/user/account', { method: 'DELETE' });
  }
};

window.executeAccountDeletion = async function() {
  try {
    showToast('Deleting your account...', 'info');
    await userApi.deleteAccount();
    TokenManager.removeToken();
    showToast('Account permanently deleted.', 'success');
    setTimeout(() => { window.location.href = '/login'; }, 1500);
  } catch (err) {
    showToast(err.message || 'Failed to delete account', 'error');
  }
};


// Owner Administration API Endpoints
const ownerApi = {
  async getOverview() {
    return await request('/owner/overview', { method: 'GET' });
  },

  async getUsers(q = '', role = '', status = '') {
    const params = new URLSearchParams();
    if (q) params.append('q', q);
    if (role) params.append('role', role);
    if (status) params.append('status', status);
    const qs = params.toString();
    return await request(`/owner/users${qs ? '?' + qs : ''}`, { method: 'GET' });
  },

  async getLoginActivity(limit = 50) {
    return await request(`/owner/login-activity?limit=${limit}`, { method: 'GET' });
  },

  async updateUserStatus(userId, accountStatus) {
    return await request(`/owner/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ accountStatus })
    });
  },

  async updateUserRole(userId, role) {
    return await request(`/owner/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role })
    });
  }
};

// Phase 2: AI Chat & Workspace API Endpoints
const chatApi = {
  async listModels() {
    return await request('/chat/models', { method: 'GET' });
  },

  async getConversations(q = '', limit = 50, offset = 0) {
    const params = new URLSearchParams();
    if (q) params.append('q', q);
    if (limit) params.append('limit', limit);
    if (offset) params.append('offset', offset);
    const queryStr = params.toString() ? `?${params.toString()}` : '';
    return await request(`/chat/conversations${queryStr}`, { method: 'GET' });
  },

  async createConversation(title = 'New Chat', model = 'gemini-1.5-flash', systemPrompt = null) {
    return await request('/chat/conversations', {
      method: 'POST',
      body: JSON.stringify({ title, model, systemPrompt })
    });
  },

  async getConversation(conversationId) {
    return await request(`/chat/conversations/${conversationId}`, { method: 'GET' });
  },

  async updateConversation(conversationId, data) {
    return await request(`/chat/conversations/${conversationId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  },

  async deleteConversation(conversationId) {
    return await request(`/chat/conversations/${conversationId}`, { method: 'DELETE' });
  },

  async sendMessage(conversationId, content, model = null, systemPrompt = null) {
    return await request(`/chat/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, model, systemPrompt })
    });
  },

  async editMessage(conversationId, messageId, newContent) {
    return await request(`/chat/conversations/${conversationId}/messages/${messageId}`, {
      method: 'PUT',
      body: JSON.stringify({ content: newContent })
    });
  },

  async streamChat({
    conversationId,
    content,
    model = null,
    systemPrompt = null,
    fileIds = null,
    onUserMessage = null,
    onDelta = null,
    onDone = null,
    onError = null,
    abortSignal = null
  }) {
    const token = TokenManager.getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    try {
      const response = await fetch(`${getApiBase()}/chat/conversations/${conversationId}/stream`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({ content, model, systemPrompt, fileIds }),
        signal: abortSignal
      });


      if (!response.ok) {
        const errorText = await response.text();
        let errMsg = 'Failed to connect to AI stream';
        try {
          const errObj = JSON.parse(errorText);
          errMsg = errObj.detail || errObj.message || errMsg;
        } catch (e) {
          errMsg = errorText || errMsg;
        }
        throw new Error(errMsg);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep remainder

        let currentEvent = 'message';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            currentEvent = 'message';
            continue;
          }

          if (trimmed.startsWith('event: ')) {
            currentEvent = trimmed.slice(7).trim();
          } else if (trimmed.startsWith('data: ')) {
            const dataStr = trimmed.slice(6);
            try {
              const data = JSON.parse(dataStr);
              if (currentEvent === 'user_message' && onUserMessage) {
                onUserMessage(data);
              } else if (currentEvent === 'delta' && onDelta) {
                onDelta(data.chunk);
              } else if (currentEvent === 'done' && onDone) {
                onDone(data);
              } else if (currentEvent === 'error' && onError) {
                onError(new Error(data.error || 'AI Streaming error'));
              }
            } catch (e) {
              // ignore parse errors on malformed lines
            }
          }
        }
      }

      if (onDone) onDone({ done: true });
    } catch (err) {
      if (err.name === 'AbortError') {
        if (onDone) onDone({ aborted: true });
      } else {
        if (onError) onError(err);
        else throw err;
      }
    }
  },

  async streamRegenerate({
    conversationId,
    model = null,
    systemPrompt = null,
    onDelta = null,
    onDone = null,
    onError = null,
    abortSignal = null
  }) {
    const token = TokenManager.getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    try {
      const response = await fetch(`${getApiBase()}/chat/conversations/${conversationId}/regenerate`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({ content: 'regenerate', model, systemPrompt }),
        signal: abortSignal
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to regenerate response');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        let currentEvent = 'message';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            currentEvent = 'message';
            continue;
          }

          if (trimmed.startsWith('event: ')) {
            currentEvent = trimmed.slice(7).trim();
          } else if (trimmed.startsWith('data: ')) {
            const dataStr = trimmed.slice(6);
            try {
              const data = JSON.parse(dataStr);
              if (currentEvent === 'delta' && onDelta) {
                onDelta(data.chunk);
              } else if (currentEvent === 'done' && onDone) {
                onDone(data);
              } else if (currentEvent === 'error' && onError) {
                onError(new Error(data.error || 'Regenerate error'));
              }
            } catch (e) {}
          }
        }
      }
      if (onDone) onDone({ done: true });
    } catch (err) {
      if (err.name === 'AbortError') {
        if (onDone) onDone({ aborted: true });
      } else {
        if (onError) onError(err);
        else throw err;
      }
    }
  }
};

// Phase 3: Files & Document Intelligence API Client
const filesApi = {
  async uploadFile(file, onProgress = null) {
    const token = TokenManager.getToken();
    const formData = new FormData();
    formData.append('file', file);

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/files/upload`, true);
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }
      xhr.withCredentials = true;

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percent = Math.round((event.loaded / event.total) * 100);
            onProgress(percent, event.loaded, event.total);
          }
        };
      }

      xhr.onload = () => {
        try {
          const res = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(res);
          } else {
            reject(new Error(res.detail || res.message || 'File upload failed'));
          }
        } catch (e) {
          reject(new Error('Invalid response from server'));
        }
      };

      xhr.onerror = () => {
        reject(new Error('Network error during file upload'));
      };

      xhr.send(formData);
    });
  },

  async listFiles({ q = '', fileType = '', limit = 50, offset = 0 } = {}) {
    const params = new URLSearchParams();
    if (q) params.append('q', q);
    if (fileType && fileType !== 'all') params.append('fileType', fileType);
    params.append('limit', limit);
    params.append('offset', offset);
    return request(`/files?${params.toString()}`);
  },

  async getFile(fileId) {
    return request(`/files/${fileId}`);
  },

  async deleteFile(fileId) {
    return request(`/files/${fileId}`, { method: 'DELETE' });
  },

  async executeAiAction(fileId, { action, query = null, model = null, systemPrompt = null }) {
    return request(`/files/${fileId}/ai-action`, {
      method: 'POST',
      body: JSON.stringify({ action, query, model, systemPrompt })
    });
  },

  async analyzeVision({ fileId = null, imageBase64 = null, action = 'describe', query = null, model = null }) {
    return request('/files/vision/analyze', {
      method: 'POST',
      body: JSON.stringify({ fileId, imageBase64, action, query, model })
    });
  }
};

// Phase 4: AI Tools & Intelligence Assistants Client
const toolsApi = {
  async search({ query, model = null, maxResults = 5, searchDepth = 'standard' }) {
    return request('/tools/search', {
      method: 'POST',
      body: JSON.stringify({ query, model, maxResults, searchDepth })
    });
  },

  async assistCode({ action, language = 'python', code = null, prompt = null, errorMessage = null, model = null }) {
    return request('/tools/code/assist', {
      method: 'POST',
      body: JSON.stringify({ action, language, code, prompt, errorMessage, model })
    });
  },

  async executeCode({ language = 'python', code, stdin = null }) {
    return request('/tools/code/execute', {
      method: 'POST',
      body: JSON.stringify({ language, code, stdin })
    });
  },

  async assistWriting({ action, text = '', tone = 'professional', targetLanguage = 'English', recipient = null, jobTitle = null, companyName = null, model = null }) {
    return request('/tools/writing/assist', {
      method: 'POST',
      body: JSON.stringify({ action, text, tone, targetLanguage, recipient, jobTitle, companyName, model })
    });
  }
};

// Phase 5: Image Generation API Client
const imageGenApi = {
  async generate({ prompt, negativePrompt = null, model = 'dall-e-3', aspectRatio = '1:1', style = 'photorealistic' }) {
    return request('/images/generate', {
      method: 'POST',
      body: JSON.stringify({ prompt, negativePrompt, model, aspectRatio, style })
    });
  },

  async listImages(limit = 50, offset = 0) {
    return request(`/images/generated?limit=${limit}&offset=${offset}`, { method: 'GET' });
  },

  async getImage(imageId) {
    return request(`/images/generated/${imageId}`, { method: 'GET' });
  },

  async deleteImage(imageId) {
    return request(`/images/generated/${imageId}`, { method: 'DELETE' });
  }
};

// Phase 5: Voice Intelligence API Client
const voiceApi = {
  async getStatus() {
    return request('/voice/status', { method: 'GET' });
  },

  async transcribe(audioBlob, language = 'en') {
    const token = TokenManager.getToken();
    const formData = new FormData();
    formData.append('file', audioBlob, 'voice_recording.wav');
    formData.append('language', language);

    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${getApiBase()}/voice/transcribe`, {
      method: 'POST',
      headers,
      body: formData,
      credentials: 'omit'
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Audio transcription failed');
    }
    return await res.json();
  },

  async synthesize({ text, voice = 'alloy', speed = 1.0, model = 'tts-1' }) {
    return request('/voice/synthesize', {
      method: 'POST',
      body: JSON.stringify({ text, voice, speed, model })
    });
  },

  async pipeline({ audioBase64, voice = 'alloy', model = null, systemPrompt = null }) {
    return request('/voice/pipeline', {
      method: 'POST',
      body: JSON.stringify({ audioBase64, voice, model, systemPrompt })
    });
  }
};

// Phase 6: Projects Workspace API Client
const projectsApi = {
  async create({ name, description = null, instructions = null, color = '#8B5CF6' }) {
    return request('/projects', {
      method: 'POST',
      body: JSON.stringify({ name, description, instructions, color })
    });
  },

  async list(limit = 50, offset = 0) {
    return request(`/projects?limit=${limit}&offset=${offset}`, { method: 'GET' });
  },

  async get(projectId) {
    return request(`/projects/${projectId}`, { method: 'GET' });
  },

  async update(projectId, data) {
    return request(`/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  },

  async delete(projectId) {
    return request(`/projects/${projectId}`, { method: 'DELETE' });
  },

  async addNote(projectId, { title, content }) {
    return request(`/projects/${projectId}/notes`, {
      method: 'POST',
      body: JSON.stringify({ title, content })
    });
  },

  async listNotes(projectId) {
    return request(`/projects/${projectId}/notes`, { method: 'GET' });
  },

  async updateNote(projectId, noteId, data) {
    return request(`/projects/${projectId}/notes/${noteId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  },

  async deleteNote(projectId, noteId) {
    return request(`/projects/${projectId}/notes/${noteId}`, { method: 'DELETE' });
  },

  async saveOutput(projectId, { title, outputType = 'text', content, metadata = null }) {
    return request(`/projects/${projectId}/outputs`, {
      method: 'POST',
      body: JSON.stringify({ title, outputType, content, metadata })
    });
  },

  async listOutputs(projectId) {
    return request(`/projects/${projectId}/outputs`, { method: 'GET' });
  },

  async deleteOutput(projectId, outputId) {
    return request(`/projects/${projectId}/outputs/${outputId}`, { method: 'DELETE' });
  },

  async associateItem(projectId, itemType, itemId) {
    return request(`/projects/${projectId}/items`, {
      method: 'POST',
      body: JSON.stringify({ itemType, itemId })
    });
  },

  async removeItem(projectId, itemType, itemId) {
    return request(`/projects/${projectId}/items/${itemType}/${itemId}`, { method: 'DELETE' });
  }
};

projectsApi.createNote = projectsApi.addNote;
projectsApi.createSavedOutput = projectsApi.saveOutput;
projectsApi.linkItem = projectsApi.associateItem;
projectsApi.unlinkItem = projectsApi.removeItem;

// Phase 6: Personalization & Controlled Memory API Client
const personalizationApi = {
  async getPreferences() {
    return request('/personalization/preferences', { method: 'GET' });
  },

  async updatePreferences(data) {
    return request('/personalization/preferences', {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  },

  async listMemories() {
    return request('/personalization/memories', { method: 'GET' });
  },

  async createMemory({ key, value, category = 'preference', memoryKey = null, memoryValue = null }) {
    const finalKey = key || memoryKey;
    const finalValue = value || memoryValue;
    return request('/personalization/memories', {
      method: 'POST',
      body: JSON.stringify({ key: finalKey, value: finalValue, category })
    });
  },

  async updateMemory(memoryId, data) {
    return request(`/personalization/memories/${memoryId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  },

  async deleteMemory(memoryId) {
    return request(`/personalization/memories/${memoryId}`, { method: 'DELETE' });
  },

  async clearAllMemories() {
    return request('/personalization/memories', { method: 'DELETE' });
  }
};

personalizationApi.clearMemories = personalizationApi.clearAllMemories;

window.authApi = authApi;
window.userApi = userApi;
window.ownerApi = ownerApi;
window.chatApi = chatApi;
window.filesApi = filesApi;
window.toolsApi = toolsApi;
window.imageGenApi = imageGenApi;
window.voiceApi = voiceApi;
window.projectsApi = projectsApi;
window.personalizationApi = personalizationApi;
window.TokenManager = TokenManager;
window.showToast = showToast;




