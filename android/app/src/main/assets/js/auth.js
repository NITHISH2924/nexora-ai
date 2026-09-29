/**
 * NEXORA AI - Auth Pages Controller (Signup, Login, Forgot, Reset, Verify)
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Check if user is already logged in on login or signup page
  const path = window.location.pathname;
  if (path.includes('/login') || path.includes('/signup')) {
    try {
      const user = await window.authApi.getMe();
      if (user && user.userId) {
        window.location.href = '/app';
        return;
      }
    } catch (e) {
      // Not logged in, stay on page
    }
  }

  // Password Visibility Toggle
  setupPasswordToggles();

  // Initialize specific page handlers
  initSignupPage();
  initLoginPage();
  initForgotPasswordPage();
  initResetPasswordPage();
  initVerifyEmailPage();
});

function setupPasswordToggles() {
  const toggles = document.querySelectorAll('.password-toggle');
  toggles.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (input) {
        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';
        btn.innerHTML = isPassword
          ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>'
          : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
      }
    });
  });
}

// Signup Page
function initSignupPage() {
  const form = document.getElementById('signup-form');
  if (!form) return;

  const passwordInput = document.getElementById('password');
  const strengthContainer = document.getElementById('password-strength');
  const bars = document.querySelectorAll('.strength-bar');
  const label = document.getElementById('strength-text');

  if (passwordInput && strengthContainer) {
    passwordInput.addEventListener('input', () => {
      const val = passwordInput.value;
      if (!val) {
        strengthContainer.classList.remove('active');
        return;
      }
      strengthContainer.classList.add('active');

      let score = 0;
      if (val.length >= 8) score++;
      if (/[A-Z]/.test(val) && /[a-z]/.test(val)) score++;
      if (/[0-9]/.test(val)) score++;
      if (/[^A-Za-z0-9]/.test(val)) score++;

      bars.forEach((bar, idx) => {
        bar.className = 'strength-bar';
        if (idx < score) {
          if (score <= 1) bar.classList.add('weak');
          else if (score <= 3) bar.classList.add('medium');
          else bar.classList.add('strong');
        }
      });

      if (score <= 1) label.innerText = 'Weak';
      else if (score <= 3) label.innerText = 'Medium';
      else label.innerText = 'Strong';
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const submitBtn = form.querySelector('button[type="submit"]');

    if (password !== confirmPassword) {
      window.showToast('Passwords do not match', 'error');
      return;
    }

    if (password.length < 8) {
      window.showToast('Password must be at least 8 characters long', 'error');
      return;
    }

    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Creating account...';

    try {
      const res = await window.authApi.signup(email, password);
      window.showToast('Account created successfully! Redirecting...', 'success');
      setTimeout(() => {
        window.location.href = '/app';
      }, 1000);
    } catch (err) {
      window.showToast(err.message, 'error');
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnText;
    }
  });
}

// Login Page
function initLoginPage() {
  const form = document.getElementById('login-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const rememberMe = document.getElementById('rememberMe')?.checked || false;
    const submitBtn = form.querySelector('button[type="submit"]');

    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Signing in...';

    try {
      await window.authApi.login(email, password, rememberMe);
      window.showToast('Welcome back! Redirecting...', 'success');
      setTimeout(() => {
        window.location.href = '/app';
      }, 800);
    } catch (err) {
      window.showToast(err.message, 'error');
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnText;
    }
  });
}

// Forgot Password Page
function initForgotPasswordPage() {
  const form = document.getElementById('forgot-password-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    const submitBtn = form.querySelector('button[type="submit"]');
    const resultBox = document.getElementById('forgot-result');

    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Sending link...';

    try {
      const res = await window.authApi.forgotPassword(email);
      form.style.display = 'none';
      if (resultBox) {
        resultBox.style.display = 'block';
      }
      window.showToast('Reset instructions dispatched', 'success');
    } catch (err) {
      window.showToast(err.message, 'error');
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnText;
    }
  });
}

// Reset Password Page
function initResetPasswordPage() {
  const form = document.getElementById('reset-password-form');
  if (!form) return;

  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('token');
  const tokenInput = document.getElementById('token');
  if (token && tokenInput) {
    tokenInput.value = token;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const resetToken = document.getElementById('token').value.trim();
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const submitBtn = form.querySelector('button[type="submit"]');

    if (!resetToken) {
      window.showToast('Reset token is required', 'error');
      return;
    }

    if (newPassword !== confirmPassword) {
      window.showToast('Passwords do not match', 'error');
      return;
    }

    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Updating password...';

    try {
      await window.authApi.resetPassword(resetToken, newPassword);
      window.showToast('Password updated! Redirecting to login...', 'success');
      setTimeout(() => {
        window.location.href = '/login';
      }, 1500);
    } catch (err) {
      window.showToast(err.message, 'error');
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnText;
    }
  });
}

// Verify Email Page
function initVerifyEmailPage() {
  const container = document.getElementById('verify-container');
  if (!container) return;

  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('token');

  const loadingState = document.getElementById('verify-loading');
  const successState = document.getElementById('verify-success');
  const errorState = document.getElementById('verify-error');
  const manualForm = document.getElementById('manual-verify-form');
  const errorMessageText = document.getElementById('verify-error-text');

  if (token) {
    // Automated verification
    if (loadingState) loadingState.style.display = 'block';
    if (manualForm) manualForm.style.display = 'none';

    window.authApi.verifyEmail(token)
      .then(() => {
        if (loadingState) loadingState.style.display = 'none';
        if (successState) successState.style.display = 'block';
        window.showToast('Email verified successfully!', 'success');
      })
      .catch((err) => {
        if (loadingState) loadingState.style.display = 'none';
        if (errorState) errorState.style.display = 'block';
        if (errorMessageText) errorMessageText.innerText = err.message;
        window.showToast(err.message, 'error');
      });
  } else {
    // Manual token entry
    if (manualForm) {
      manualForm.style.display = 'block';
      manualForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const inputToken = document.getElementById('token').value.trim();
        const submitBtn = manualForm.querySelector('button[type="submit"]');

        const originalBtnText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Verifying...';

        try {
          await window.authApi.verifyEmail(inputToken);
          manualForm.style.display = 'none';
          if (successState) successState.style.display = 'block';
          window.showToast('Email verified successfully!', 'success');
        } catch (err) {
          window.showToast(err.message, 'error');
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnText;
        }
      });
    }
  }
}
