/**
 * ==========================================================================
 * NEXORA AI — Centralized Theme System & Branding Engine
 * 
 * Official Themes:
 * 1. 'light'  — White Theme (Background: #FFFDF3, Text: #1F2937 / #6B7280 / #9CA3AF)
 * 2. 'dark'   — Dark Theme  (Background: #0B0B0B, Text: #E5E7EB / #9CA3AF / #6B7280)
 * 3. 'system' — System Default (Automatic OS / Browser preference tracking)
 * 
 * Official Metallic N/D Circular Logo:
 * - White Theme: /assets/logo-light.png
 * - Dark Theme:  /assets/logo-dark.png
 * ==========================================================================
 */

(function() {
  'use strict';

  const STORAGE_KEY = 'nexora_theme';
  const DEFAULT_PREFERENCE = 'system'; // Default for new users is system default

  // OS Theme Query Matcher
  let mediaQuery = null;
  if (typeof window !== 'undefined' && window.matchMedia) {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  }

  function getSystemScheme() {
    if (mediaQuery && mediaQuery.matches) {
      return 'dark';
    }
    return 'light';
  }

  function getSavedPreference() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'light' || saved === 'dark' || saved === 'system') {
        return saved;
      }
    } catch (e) {
      console.warn('Could not read theme preference from localStorage:', e);
    }
    return DEFAULT_PREFERENCE;
  }

  function resolveEffectiveTheme(preference) {
    if (preference === 'light') return 'light';
    if (preference === 'dark') return 'dark';
    return getSystemScheme();
  }

  function updateLogoAssets(effectiveTheme) {
    const logoSrc = (effectiveTheme === 'dark') ? '/assets/logo-dark.png' : '/assets/logo-light.png';
    const logoImgs = document.querySelectorAll('.brand-logo-img, .brand-icon-img, [data-brand-logo]');
    logoImgs.forEach(function(img) {
      if (img && img.tagName === 'IMG') {
        if (!img.src.includes('avatar') && !img.src.includes('uploads')) {
          img.src = logoSrc;
        }
      }
    });

    const favicon = document.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
    if (favicon) {
      favicon.href = (effectiveTheme === 'dark') ? '/assets/logo-dark.png' : '/assets/logo-light.png';
    }
  }

  function updateToggleButtons(preference, effectiveTheme) {
    const buttons = document.querySelectorAll('.btn-theme-toggle, [data-action="toggle-theme"]');
    const nextLabel = (effectiveTheme === 'light') ? 'Switch to Dark Theme' : 'Switch to White Theme';

    buttons.forEach(function(btn) {
      btn.setAttribute('aria-label', nextLabel);
      btn.setAttribute('title', nextLabel);

      const darkIcon = btn.querySelector('.theme-icon-dark');
      const lightIcon = btn.querySelector('.theme-icon-light');

      if (darkIcon && lightIcon) {
        if (effectiveTheme === 'light') {
          darkIcon.style.display = 'inline-flex';
          lightIcon.style.display = 'none';
        } else {
          darkIcon.style.display = 'none';
          lightIcon.style.display = 'inline-flex';
        }
      }
    });
  }

  function updateHighlightTheme(effectiveTheme) {
    const hljsLink = document.getElementById('hljs-theme-link');
    if (hljsLink) {
      if (effectiveTheme === 'dark') {
        hljsLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css';
      } else {
        hljsLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
      }
    }
  }

  function applyTheme(preference, save) {
    if (save === undefined) save = true;

    const validPref = (preference === 'light' || preference === 'dark' || preference === 'system')
      ? preference
      : DEFAULT_PREFERENCE;

    const effectiveTheme = resolveEffectiveTheme(validPref);
    const root = document.documentElement;

    root.setAttribute('data-theme', effectiveTheme);
    root.setAttribute('data-theme-preference', validPref);

    if (effectiveTheme === 'dark') {
      root.classList.add('theme-dark');
      root.classList.remove('theme-light');
    } else {
      root.classList.add('theme-light');
      root.classList.remove('theme-dark');
    }

    if (save) {
      try {
        localStorage.setItem(STORAGE_KEY, validPref);
      } catch (e) {
        console.warn('Could not save theme preference to localStorage:', e);
      }
    }

    updateLogoAssets(effectiveTheme);
    updateToggleButtons(validPref, effectiveTheme);
    updateHighlightTheme(effectiveTheme);

    // Sync select dropdown in settings if present
    const prefSelect = document.getElementById('pref-ui-theme');
    if (prefSelect && prefSelect.value !== validPref) {
      prefSelect.value = validPref;
    }

    // Dispatch custom event for real-time reactivity across workspace
    window.dispatchEvent(new CustomEvent('nexora:theme-changed', {
      detail: {
        preference: validPref,
        effectiveTheme: effectiveTheme
      }
    }));

    return effectiveTheme;
  }

  function toggleTheme() {
    const currentPref = getSavedPreference();
    const effective = resolveEffectiveTheme(currentPref);
    // Toggling flips between the two explicit themes
    const nextPref = (effective === 'dark') ? 'light' : 'dark';
    return applyTheme(nextPref, true);
  }

  // Dynamic listener for OS / Browser theme changes
  if (mediaQuery) {
    const osThemeChangeHandler = function() {
      const pref = getSavedPreference();
      if (pref === 'system') {
        applyTheme('system', false);
      }
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', osThemeChangeHandler);
    } else if (mediaQuery.addListener) {
      mediaQuery.addListener(osThemeChangeHandler);
    }
  }

  // 1. Immediate synchronous theme application before DOM render to prevent theme flashing
  const initialPref = getSavedPreference();
  const initialEffective = resolveEffectiveTheme(initialPref);
  document.documentElement.setAttribute('data-theme', initialEffective);
  document.documentElement.setAttribute('data-theme-preference', initialPref);
  if (initialEffective === 'dark') {
    document.documentElement.classList.add('theme-dark');
  } else {
    document.documentElement.classList.add('theme-light');
  }

  // 2. Bind DOM listeners on ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      applyTheme(getSavedPreference(), false);

      document.addEventListener('click', function(e) {
        const toggleBtn = e.target.closest('.btn-theme-toggle, [data-action="toggle-theme"]');
        if (toggleBtn) {
          e.preventDefault();
          toggleTheme();
        }
      });

      const prefSelect = document.getElementById('pref-ui-theme');
      if (prefSelect) {
        prefSelect.value = getSavedPreference();
        prefSelect.addEventListener('change', function() {
          applyTheme(prefSelect.value, true);
        });
      }
    });
  } else {
    applyTheme(getSavedPreference(), false);
  }

  // Expose global API
  window.NexoraTheme = {
    get: function() {
      return document.documentElement.getAttribute('data-theme') || initialEffective;
    },
    getPreference: function() {
      return getSavedPreference();
    },
    getEffectiveTheme: function() {
      return resolveEffectiveTheme(getSavedPreference());
    },
    set: function(preference) {
      return applyTheme(preference, true);
    },
    toggle: toggleTheme,
    init: function() {
      return applyTheme(getSavedPreference(), false);
    }
  };

})();
