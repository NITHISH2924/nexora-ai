/**
 * NEXORA AI - Conversational Workspace & Chat Engine Controller (/app)
 */

class ChatController {
  constructor() {
    this.activeConversationId = null;
    this.activeModel = localStorage.getItem('nexora_model') || 'gemini-1.5-flash';
    this.systemPrompt = localStorage.getItem('nexora_system_prompt') || '';
    this.isStreaming = false;
    this.abortController = null;
    this.conversations = [];
    this.availableModels = [];
    this.targetRenameConvId = null;
    this.targetDeleteConvId = null;
    this.attachedFileContent = null;
    this.attachedFileName = null;
  }

  async init() {
    this.setupMarked();
    this.bindEvents();
    await this.loadModels();
    await this.loadConversations();
    
    // Check if URL has conversation parameter or start with fresh new chat
    const urlParams = new URLSearchParams(window.location.search);
    const convId = urlParams.get('c');
    if (convId) {
      await this.selectConversation(convId);
    } else {
      this.resetToNewChat();
    }
  }

  setupMarked() {
    if (typeof marked !== 'undefined') {
      marked.setOptions({
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false,
        highlight: function (code, lang) {
          if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
            try {
              return hljs.highlight(code, { language: lang }).value;
            } catch (__) {}
          }
          if (typeof hljs !== 'undefined') {
            try {
              return hljs.highlightAuto(code).value;
            } catch (__) {}
          }
          return code;
        }
      });
    }
  }

  bindEvents() {
    // New chat buttons
    const btnNewChat = document.getElementById('btn-sidebar-new-chat');
    if (btnNewChat) btnNewChat.addEventListener('click', () => this.resetToNewChat());

    // Clear chat button
    const btnClear = document.getElementById('btn-clear-chat');
    if (btnClear) btnClear.addEventListener('click', () => this.resetToNewChat());

    // Export conversation
    const btnExport = document.getElementById('btn-export-chat');
    if (btnExport) btnExport.addEventListener('click', () => this.exportCurrentChat());

    // Send / Stop button
    const btnSend = document.getElementById('btn-send-message');
    if (btnSend) {
      btnSend.addEventListener('click', () => {
        if (this.isStreaming) {
          this.stopGeneration();
        } else {
          this.handleSendMessage();
        }
      });
    }

    // Textarea input auto-grow and key bindings
    const textarea = document.getElementById('chat-textarea');
    if (textarea) {
      textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
      });

      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.handleSendMessage();
        }
      });
    }

    // Global shortcut Ctrl+K / Cmd+K for New Chat
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        this.resetToNewChat();
      }
    });

    // Search conversations input
    const searchInput = document.getElementById('conversation-search-input');
    if (searchInput) {
      let searchTimeout;
      searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
          this.loadConversations(e.target.value);
        }, 250);
      });
    }

    // Model Selector Dropdown
    const modelBtn = document.getElementById('model-select-btn');
    const modelDropdown = document.getElementById('model-dropdown-menu');
    if (modelBtn && modelDropdown) {
      modelBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        modelDropdown.classList.toggle('open');
      });
      document.addEventListener('click', () => {
        modelDropdown.classList.remove('open');
      });
    }

    // Prompt Starter Cards
    document.querySelectorAll('.prompt-starter-card').forEach((card) => {
      card.addEventListener('click', () => {
        const prompt = card.getAttribute('data-prompt');
        if (prompt && textarea) {
          textarea.value = prompt;
          textarea.style.height = 'auto';
          textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
          this.handleSendMessage();
        }
      });
    });

    // Attachment file handlers
    const attachBtn = document.getElementById('btn-attach-file');
    const fileInput = document.getElementById('file-attachment-input');
    if (attachBtn && fileInput) {
      attachBtn.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
          window.showToast(`Uploading document "${file.name}"...`, 'info', 2000);
          const savedFile = await window.filesApi.uploadFile(file);
          this.attachedFileIds = [savedFile.id];
          this.attachedFileName = savedFile.originalFilename;
          this.attachedFileContent = savedFile.extractedText || null;
          this.renderAttachmentPreview();
          window.showToast(`Attached "${savedFile.originalFilename}" to chat context`, 'success');
        } catch (err) {
          window.showToast(`Upload failed: ${err.message}`, 'error');
        }
      });
    }

    // Image upload handler
    const imgBtn = document.getElementById('btn-attach-image');
    const imgInput = document.getElementById('image-attachment-input');
    if (imgBtn && imgInput) {
      imgBtn.addEventListener('click', () => imgInput.click());
      imgInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
          window.showToast(`Uploading image "${file.name}"...`, 'info', 2000);
          const savedFile = await window.filesApi.uploadFile(file);
          this.attachedFileIds = [savedFile.id];
          this.attachedFileName = `[Image: ${savedFile.originalFilename}]`;
          this.attachedFileContent = null;
          this.renderAttachmentPreview();
          window.showToast(`Attached image "${savedFile.originalFilename}" to vision context`, 'success');
        } catch (err) {
          window.showToast(`Image upload failed: ${err.message}`, 'error');
        }
      });
    }

    const removeAttachBtn = document.getElementById('btn-remove-attachment');
    if (removeAttachBtn) {
      removeAttachBtn.addEventListener('click', () => {
        this.clearAttachment();
      });
    }


    // Rename Modal Bindings
    const btnEditTitle = document.getElementById('btn-edit-conv-title');
    if (btnEditTitle) {
      btnEditTitle.addEventListener('click', () => {
        if (!this.activeConversationId) return;
        this.openRenameModal(this.activeConversationId, document.getElementById('active-conv-title').innerText);
      });
    }
    const btnCancelRename = document.getElementById('btn-cancel-rename');
    const btnSaveRename = document.getElementById('btn-save-rename');
    if (btnCancelRename) btnCancelRename.addEventListener('click', () => this.closeRenameModal());
    if (btnSaveRename) btnSaveRename.addEventListener('click', () => this.saveRenameConversation());

    // Delete Modal Bindings
    const btnCancelDelete = document.getElementById('btn-cancel-delete');
    const btnConfirmDelete = document.getElementById('btn-confirm-delete');
    if (btnCancelDelete) btnCancelDelete.addEventListener('click', () => this.closeDeleteModal());
    if (btnConfirmDelete) btnConfirmDelete.addEventListener('click', () => this.confirmDeleteConversation());
  }

  renderAttachmentPreview() {
    const previewBar = document.getElementById('attachment-preview-bar');
    const filenameEl = document.getElementById('attachment-filename');
    if (previewBar && filenameEl) {
      filenameEl.innerText = this.attachedFileName;
      previewBar.style.display = 'flex';
    }
  }

  clearAttachment() {
    this.attachedFileContent = null;
    this.attachedFileName = null;
    const previewBar = document.getElementById('attachment-preview-bar');
    if (previewBar) previewBar.style.display = 'none';
    const fileInput = document.getElementById('file-attachment-input');
    if (fileInput) fileInput.value = '';
    const imgInput = document.getElementById('image-attachment-input');
    if (imgInput) imgInput.value = '';
  }

  async loadModels() {
    try {
      const data = await window.chatApi.listModels();
      if (data && data.models) {
        this.availableModels = data.models;
        this.renderModelDropdown(data.models);
      }
    } catch (e) {
      console.warn('Could not load AI models list:', e);
    }
  }

  renderModelDropdown(models) {
    const menu = document.getElementById('model-dropdown-menu');
    const labelEl = document.getElementById('current-selected-model-label');
    if (!menu) return;

    menu.innerHTML = '';
    models.forEach((m) => {
      const isSelected = m.id === this.activeModel;
      if (isSelected && labelEl) {
        labelEl.innerText = m.name;
      }

      const item = document.createElement('div');
      item.className = `model-option-item ${isSelected ? 'active' : ''}`;
      item.innerHTML = `
        <div class="model-option-header">
          <span class="model-option-name">${m.name}</span>
          <span class="model-option-tag">${m.category || 'AI Model'}</span>
        </div>
        <div class="model-option-desc">${m.description || ''}</div>
      `;

      item.addEventListener('click', () => {
        this.activeModel = m.id;
        localStorage.setItem('nexora_model', m.id);
        if (labelEl) labelEl.innerText = m.name;
        menu.classList.remove('open');
        this.renderModelDropdown(this.availableModels);
        window.showToast(`Switched model to ${m.name}`, 'info', 2000);
      });

      menu.appendChild(item);
    });
  }

  async loadConversations(searchQuery = '') {
    try {
      const listEl = document.getElementById('recent-chats-list');
      const countEl = document.getElementById('chat-total-count');
      const conversations = await window.chatApi.getConversations(searchQuery);
      this.conversations = conversations || [];

      if (countEl) countEl.innerText = this.conversations.length;
      if (!listEl) return;

      if (this.conversations.length === 0) {
        listEl.innerHTML = '<div class="chat-list-empty">No conversations yet</div>';
        return;
      }

      listEl.innerHTML = '';
      this.conversations.forEach((conv) => {
        const isActive = conv.id === this.activeConversationId;
        const item = document.createElement('div');
        item.className = `chat-history-item ${isActive ? 'active' : ''}`;
        item.setAttribute('data-id', conv.id);

        item.innerHTML = `
          <div class="chat-item-main">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <span class="chat-item-title">${this.escapeHtml(conv.title)}</span>
          </div>
          <div class="chat-item-actions">
            <button class="chat-action-btn edit-btn" title="Rename">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
            </button>
            <button class="chat-action-btn delete-btn" title="Delete">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
        `;

        // Click to select
        item.querySelector('.chat-item-main').addEventListener('click', () => {
          this.selectConversation(conv.id);
        });

        // Rename click
        item.querySelector('.edit-btn').addEventListener('click', (e) => {
          e.stopPropagation();
          this.openRenameModal(conv.id, conv.title);
        });

        // Delete click
        item.querySelector('.delete-btn').addEventListener('click', (e) => {
          e.stopPropagation();
          this.openDeleteModal(conv.id);
        });

        listEl.appendChild(item);
      });
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  }

  resetToNewChat() {
    this.activeConversationId = null;
    const titleEl = document.getElementById('active-conv-title');
    if (titleEl) titleEl.innerText = 'New Chat';

    const emptyState = document.getElementById('chat-empty-state');
    const feed = document.getElementById('message-feed');
    if (emptyState) emptyState.style.display = 'block';
    if (feed) feed.innerHTML = '';

    // Remove active state from sidebar
    document.querySelectorAll('.chat-history-item').forEach(el => el.classList.remove('active'));

    const textarea = document.getElementById('chat-textarea');
    if (textarea) {
      textarea.value = '';
      textarea.style.height = 'auto';
      textarea.focus();
    }
    this.clearAttachment();

    // Update URL query string
    window.history.replaceState({}, '', '/app');
  }

  async selectConversation(conversationId) {
    if (this.isStreaming) {
      this.stopGeneration();
    }

    try {
      const conv = await window.chatApi.getConversation(conversationId);
      this.activeConversationId = conv.id;

      // Update Title
      const titleEl = document.getElementById('active-conv-title');
      if (titleEl) titleEl.innerText = conv.title;

      // Update model if conversation specified one
      if (conv.model) {
        this.activeModel = conv.model;
        const labelEl = document.getElementById('current-selected-model-label');
        const found = this.availableModels.find(m => m.id === conv.model);
        if (labelEl) labelEl.innerText = found ? found.name : conv.model;
      }

      // Render Messages
      const emptyState = document.getElementById('chat-empty-state');
      const feed = document.getElementById('message-feed');

      if (!conv.messages || conv.messages.length === 0) {
        if (emptyState) emptyState.style.display = 'block';
        if (feed) feed.innerHTML = '';
      } else {
        if (emptyState) emptyState.style.display = 'none';
        if (feed) {
          feed.innerHTML = '';
          conv.messages.forEach(msg => this.appendMessageToFeed(msg));
          this.scrollToBottom();
        }
      }

      // Update active state in sidebar
      document.querySelectorAll('.chat-history-item').forEach(el => {
        el.classList.toggle('active', el.getAttribute('data-id') === conv.id);
      });

      // Update URL
      window.history.replaceState({}, '', `/app?c=${conv.id}`);

      const textarea = document.getElementById('chat-textarea');
      if (textarea) textarea.focus();
    } catch (err) {
      window.showToast(err.message || 'Could not load conversation', 'error');
      this.resetToNewChat();
    }
  }

  async handleSendMessage() {
    const textarea = document.getElementById('chat-textarea');
    if (!textarea) return;

    let content = textarea.value.trim();
    // Capture attached fileIds if any
    const fileIdsToSend = (this.attachedFileIds && this.attachedFileIds.length > 0) ? [...this.attachedFileIds] : null;

    // Attach file context text preview if present
    if (this.attachedFileContent) {
      content = `${content ? content + '\n\n' : ''}### Attached File: ${this.attachedFileName}\n\`\`\`\n${this.attachedFileContent.slice(0, 2000)}\n\`\`\``;
    }

    textarea.value = '';
    textarea.style.height = 'auto';
    this.clearAttachment();

    // 1. Ensure Conversation exists
    if (!this.activeConversationId) {
      try {
        const newConv = await window.chatApi.createConversation(
          'New Chat',
          this.activeModel,
          this.systemPrompt
        );
        this.activeConversationId = newConv.id;
        window.history.replaceState({}, '', `/app?c=${newConv.id}`);
        await this.loadConversations();
      } catch (err) {
        window.showToast('Failed to initialize conversation session', 'error');
        return;
      }
    }

    // Hide empty state
    const emptyState = document.getElementById('chat-empty-state');
    if (emptyState) emptyState.style.display = 'none';

    // 2. Render User Message immediately
    const tempUserMsg = {
      id: 'temp-' + Date.now(),
      role: 'user',
      content: content,
      createdAt: new Date().toISOString()
    };
    this.appendMessageToFeed(tempUserMsg);
    this.scrollToBottom();

    // 3. Prepare Streaming Assistant Placeholder
    const tempAssistantMsgId = 'asst-' + Date.now();
    const assistantRow = this.createAssistantRow(tempAssistantMsgId, this.activeModel);
    const feed = document.getElementById('message-feed');
    if (feed) feed.appendChild(assistantRow);
    this.scrollToBottom();

    const bubbleEl = assistantRow.querySelector('.message-bubble');
    let accumulatedText = '';

    // 4. Start Streaming Mode
    this.setStreamingState(true);
    this.abortController = new AbortController();

    await window.chatApi.streamChat({
      conversationId: this.activeConversationId,
      content: content,
      model: this.activeModel,
      systemPrompt: this.systemPrompt,
      fileIds: fileIdsToSend,
      abortSignal: this.abortController.signal,

      onUserMessage: (userMsg) => {
        // Update user message ID
        const row = document.getElementById(`msg-${tempUserMsg.id}`);
        if (row) row.id = `msg-${userMsg.id}`;
      },
      onDelta: (chunk) => {
        accumulatedText += chunk;
        if (bubbleEl) {
          bubbleEl.innerHTML = this.renderMarkdown(accumulatedText) + '<span class="streaming-cursor"></span>';
          this.attachCodeCopyButtons(bubbleEl);
          this.scrollToBottom();
        }
      },
      onDone: (data) => {
        this.setStreamingState(false);
        if (bubbleEl) {
          bubbleEl.innerHTML = this.renderMarkdown(accumulatedText);
          this.attachCodeCopyButtons(bubbleEl);
        }

        // Update Assistant Row ID
        if (data && data.assistantMessage) {
          assistantRow.id = `msg-${data.assistantMessage.id}`;
        }

        // Add action buttons
        this.appendAssistantActions(assistantRow, accumulatedText);

        // Update Title if changed
        if (data && data.conversationTitle) {
          const titleEl = document.getElementById('active-conv-title');
          if (titleEl) titleEl.innerText = data.conversationTitle;
        }

        this.loadConversations();
      },
      onError: (err) => {
        this.setStreamingState(false);
        if (bubbleEl) {
          bubbleEl.innerHTML = `<div style="color:var(--color-danger);padding:8px 0;"><strong>Error:</strong> ${this.escapeHtml(err.message)}</div>`;
        }
        window.showToast(err.message, 'error');
      }
    });
  }

  async regenerateLastResponse() {
    if (!this.activeConversationId || this.isStreaming) return;

    // Remove last assistant row from DOM
    const feed = document.getElementById('message-feed');
    if (!feed) return;
    const lastRow = feed.lastElementChild;
    if (lastRow && lastRow.classList.contains('assistant-row')) {
      lastRow.remove();
    }

    // Spawn new streaming assistant row
    const tempAssistantMsgId = 'asst-regen-' + Date.now();
    const assistantRow = this.createAssistantRow(tempAssistantMsgId, this.activeModel);
    feed.appendChild(assistantRow);
    this.scrollToBottom();

    const bubbleEl = assistantRow.querySelector('.message-bubble');
    let accumulatedText = '';

    this.setStreamingState(true);
    this.abortController = new AbortController();

    await window.chatApi.streamRegenerate({
      conversationId: this.activeConversationId,
      model: this.activeModel,
      systemPrompt: this.systemPrompt,
      abortSignal: this.abortController.signal,
      onDelta: (chunk) => {
        accumulatedText += chunk;
        if (bubbleEl) {
          bubbleEl.innerHTML = this.renderMarkdown(accumulatedText) + '<span class="streaming-cursor"></span>';
          this.attachCodeCopyButtons(bubbleEl);
          this.scrollToBottom();
        }
      },
      onDone: (data) => {
        this.setStreamingState(false);
        if (bubbleEl) {
          bubbleEl.innerHTML = this.renderMarkdown(accumulatedText);
          this.attachCodeCopyButtons(bubbleEl);
        }
        if (data && data.assistantMessage) {
          assistantRow.id = `msg-${data.assistantMessage.id}`;
        }
        this.appendAssistantActions(assistantRow, accumulatedText);
        this.loadConversations();
      },
      onError: (err) => {
        this.setStreamingState(false);
        if (bubbleEl) {
          bubbleEl.innerHTML = `<div style="color:var(--color-danger);padding:8px 0;"><strong>Regenerate Error:</strong> ${this.escapeHtml(err.message)}</div>`;
        }
        window.showToast(err.message, 'error');
      }
    });
  }

  stopGeneration() {
    if (this.abortController) {
      this.abortController.abort();
      this.setStreamingState(false);
      window.showToast('Generation stopped', 'info', 2000);
    }
  }

  setStreamingState(isStreaming) {
    this.isStreaming = isStreaming;
    const btnSend = document.getElementById('btn-send-message');
    const iconSend = document.getElementById('icon-send');
    const iconStop = document.getElementById('icon-stop');
    const engineBadge = document.getElementById('active-engine-badge');

    if (btnSend && iconSend && iconStop) {
      if (isStreaming) {
        btnSend.classList.add('stop-mode');
        btnSend.title = 'Stop generating';
        iconSend.style.display = 'none';
        iconStop.style.display = 'block';
        if (engineBadge) engineBadge.innerText = 'Engine: Streaming...';
      } else {
        btnSend.classList.remove('stop-mode');
        btnSend.title = 'Send message (Enter)';
        iconSend.style.display = 'block';
        iconStop.style.display = 'none';
        if (engineBadge) engineBadge.innerText = 'Engine: Ready';
      }
    }
  }

  appendMessageToFeed(msg) {
    const feed = document.getElementById('message-feed');
    if (!feed) return;

    if (msg.role === 'user') {
      const userRow = document.createElement('div');
      userRow.className = 'chat-message-row user-row';
      userRow.id = `msg-${msg.id}`;

      userRow.innerHTML = `
        <div class="message-avatar">U</div>
        <div class="message-content-wrapper">
          <div class="message-meta">
            <span class="message-sender-name">You</span>
            <span class="message-time">${this.formatTime(msg.createdAt)}</span>
          </div>
          <div class="message-bubble">${this.escapeHtml(msg.content)}</div>
          <div class="message-actions-bar">
            <button class="msg-action-btn btn-edit-msg">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
              <span>Edit</span>
            </button>
            <button class="msg-action-btn btn-copy-msg">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              <span>Copy</span>
            </button>
          </div>
        </div>
      `;

      userRow.querySelector('.btn-copy-msg').addEventListener('click', () => {
        navigator.clipboard.writeText(msg.content);
        window.showToast('Message copied to clipboard', 'success', 2000);
      });

      userRow.querySelector('.btn-edit-msg').addEventListener('click', () => {
        this.openInlineMessageEdit(userRow, msg);
      });

      feed.appendChild(userRow);
    } else {
      const assistantRow = this.createAssistantRow(msg.id, msg.model);
      const bubbleEl = assistantRow.querySelector('.message-bubble');
      bubbleEl.innerHTML = this.renderMarkdown(msg.content);
      this.attachCodeCopyButtons(bubbleEl);
      this.appendAssistantActions(assistantRow, msg.content);
      feed.appendChild(assistantRow);
    }
  }

  createAssistantRow(msgId, modelName = 'gemini-1.5-flash') {
    const row = document.createElement('div');
    row.className = 'chat-message-row assistant-row';
    row.id = `msg-${msgId}`;

    const displayModel = (modelName || 'NEXORA AI').replace('gemini-', 'Gemini ').replace('gpt-', 'GPT-');

    row.innerHTML = `
      <div class="message-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="18" height="18">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
      </div>
      <div class="message-content-wrapper">
        <div class="message-meta">
          <span class="message-sender-name">NEXORA AI</span>
          <span class="message-model-tag">${displayModel}</span>
        </div>
        <div class="message-bubble"><span class="streaming-cursor"></span></div>
      </div>
    `;
    return row;
  }

  appendAssistantActions(assistantRow, content) {
    const wrapper = assistantRow.querySelector('.message-content-wrapper');
    if (!wrapper || wrapper.querySelector('.message-actions-bar')) return;

    const actionsBar = document.createElement('div');
    actionsBar.className = 'message-actions-bar';
    actionsBar.innerHTML = `
      <button class="msg-action-btn btn-speak-response" title="Read response aloud with Text-to-Speech">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
        <span>Read Aloud</span>
      </button>
      <button class="msg-action-btn btn-copy-response">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
        <span>Copy Response</span>
      </button>
      <button class="msg-action-btn btn-regenerate-response">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="1 4 1 10 7 10"></polyline><polyline points="23 20 23 14 17 14"></polyline><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path></svg>
        <span>Regenerate</span>
      </button>
    `;

    const speakBtn = actionsBar.querySelector('.btn-speak-response');
    if (speakBtn) {
      speakBtn.addEventListener('click', () => {
        if (window.playSpeechAudio) {
          window.playSpeechAudio(content, speakBtn);
        }
      });
    }

    actionsBar.querySelector('.btn-copy-response').addEventListener('click', () => {
      navigator.clipboard.writeText(content);
      window.showToast('Response copied to clipboard', 'success', 2000);
    });

    actionsBar.querySelector('.btn-regenerate-response').addEventListener('click', () => {
      this.regenerateLastResponse();
    });

    wrapper.appendChild(actionsBar);
  }

  openInlineMessageEdit(userRow, msg) {
    const bubble = userRow.querySelector('.message-bubble');
    const actions = userRow.querySelector('.message-actions-bar');
    if (!bubble) return;

    const originalContent = msg.content;
    actions.style.display = 'none';

    bubble.innerHTML = `
      <textarea class="form-input" style="width:100%;min-height:80px;font-size:14px;resize:vertical;" id="edit-msg-input">${this.escapeHtml(originalContent)}</textarea>
      <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:8px;">
        <button class="btn btn-secondary btn-sm" id="btn-cancel-msg-edit">Cancel</button>
        <button class="btn btn-primary btn-sm" id="btn-save-msg-edit">Save & Regenerate</button>
      </div>
    `;

    const cancelBtn = bubble.querySelector('#btn-cancel-msg-edit');
    const saveBtn = bubble.querySelector('#btn-save-msg-edit');
    const inputEl = bubble.querySelector('#edit-msg-input');

    cancelBtn.addEventListener('click', () => {
      bubble.innerText = originalContent;
      actions.style.display = 'flex';
    });

    saveBtn.addEventListener('click', async () => {
      const newText = inputEl.value.trim();
      if (!newText) return;
      try {
        await window.chatApi.editMessage(this.activeConversationId, msg.id, newText);
        await this.selectConversation(this.activeConversationId);
        // Trigger regeneration from this edited point
        await this.regenerateLastResponse();
      } catch (e) {
        window.showToast(e.message || 'Failed to edit message', 'error');
      }
    });
  }

  renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
      try {
        let parsed = marked.parse(text || '');
        // Enhance code blocks with custom header and copy button
        parsed = parsed.replace(/<pre><code class="language-([^"]+)">([\s\S]*?)<\/code><\/pre>/gi, (match, lang, code) => {
          return `
            <div class="code-block-wrapper">
              <div class="code-block-header">
                <span>${lang.toUpperCase()}</span>
                <button class="code-copy-btn" data-code="${this.escapeAttribute(code)}">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  <span>Copy Code</span>
                </button>
              </div>
              <pre><code class="hljs language-${lang}">${code}</code></pre>
            </div>
          `;
        });
        return parsed;
      } catch (e) {
        return this.escapeHtml(text);
      }
    }
    return this.escapeHtml(text);
  }

  attachCodeCopyButtons(container) {
    container.querySelectorAll('.code-copy-btn').forEach((btn) => {
      if (btn.getAttribute('data-bound')) return;
      btn.setAttribute('data-bound', 'true');
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const codeWrapper = btn.closest('.code-block-wrapper');
        const codeEl = codeWrapper ? codeWrapper.querySelector('code') : null;
        const textToCopy = codeEl ? codeEl.innerText : '';
        navigator.clipboard.writeText(textToCopy);
        
        const label = btn.querySelector('span');
        if (label) label.innerText = 'Copied!';
        setTimeout(() => {
          if (label) label.innerText = 'Copy Code';
        }, 2000);
      });
    });
  }

  exportCurrentChat() {
    if (!this.activeConversationId) {
      window.showToast('No active conversation to export', 'info');
      return;
    }
    const title = document.getElementById('active-conv-title').innerText || 'NEXORA_AI_Conversation';
    const feed = document.getElementById('message-feed');
    let mdContent = `# ${title}\n*Exported from NEXORA AI on ${new Date().toLocaleString()}*\n\n---\n\n`;

    feed.querySelectorAll('.chat-message-row').forEach(row => {
      const isUser = row.classList.contains('user-row');
      const sender = isUser ? 'User' : 'NEXORA AI Assistant';
      const bubble = row.querySelector('.message-bubble');
      const text = bubble ? bubble.innerText : '';
      mdContent += `### ${sender}\n\n${text}\n\n---\n\n`;
    });

    const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${title.replace(/[^a-zA-Z0-9_-]/g, '_')}.md`;
    link.click();
    URL.revokeObjectURL(url);
    window.showToast('Conversation exported as Markdown', 'success');
  }

  openRenameModal(convId, currentTitle) {
    this.targetRenameConvId = convId;
    const modal = document.getElementById('modal-rename-conv');
    const input = document.getElementById('input-rename-conv');
    if (modal && input) {
      input.value = currentTitle || '';
      modal.style.display = 'flex';
      input.focus();
    }
  }

  closeRenameModal() {
    this.targetRenameConvId = null;
    const modal = document.getElementById('modal-rename-conv');
    if (modal) modal.style.display = 'none';
  }

  async saveRenameConversation() {
    const input = document.getElementById('input-rename-conv');
    if (!this.targetRenameConvId || !input) return;
    const newTitle = input.value.trim();
    if (!newTitle) return;

    try {
      await window.chatApi.updateConversation(this.targetRenameConvId, { title: newTitle });
      if (this.targetRenameConvId === this.activeConversationId) {
        const titleEl = document.getElementById('active-conv-title');
        if (titleEl) titleEl.innerText = newTitle;
      }
      this.closeRenameModal();
      await this.loadConversations();
      window.showToast('Conversation renamed', 'success');
    } catch (e) {
      window.showToast(e.message || 'Failed to rename conversation', 'error');
    }
  }

  openDeleteModal(convId) {
    this.targetDeleteConvId = convId;
    const modal = document.getElementById('modal-delete-conv');
    if (modal) modal.style.display = 'flex';
  }

  closeDeleteModal() {
    this.targetDeleteConvId = null;
    const modal = document.getElementById('modal-delete-conv');
    if (modal) modal.style.display = 'none';
  }

  async confirmDeleteConversation() {
    if (!this.targetDeleteConvId) return;
    try {
      const deletingActive = (this.targetDeleteConvId === this.activeConversationId);
      await window.chatApi.deleteConversation(this.targetDeleteConvId);
      this.closeDeleteModal();
      await this.loadConversations();
      if (deletingActive) {
        this.resetToNewChat();
      }
      window.showToast('Conversation deleted', 'success');
    } catch (e) {
      window.showToast(e.message || 'Failed to delete conversation', 'error');
    }
  }

  scrollToBottom() {
    const container = document.getElementById('chat-messages-container');
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  formatTime(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '';
    }
  }

  escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  escapeAttribute(str) {
    if (!str) return '';
    return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
}

window.ChatController = ChatController;
