/**
 * IIT BHU Wi-Fi AutoConnect - Content Script
 * Automatically fills and submits credentials on captive portal pages.
 */

(async function () {
  'use strict';

  // Read stored credentials from local storage
  const config = await chrome.storage.local.get(['username', 'password', 'autoLogin']);
  const autoLogin = config.autoLogin !== false; // default true
  const username = config.username || '';
  const password = config.password || '';

  if (!autoLogin || !username || !password) {
    console.log('[IIT BHU AutoConnect] Not configured or auto-login disabled.');
    return;
  }

  function showToast(message, isSuccess = false) {
    const toast = document.createElement('div');
    toast.id = 'iitbhu-autoconnect-toast';
    toast.textContent = message;
    Object.assign(toast.style, {
      position: 'fixed',
      top: '20px',
      right: '20px',
      backgroundColor: isSuccess ? '#10b981' : '#1e3a8a',
      color: '#ffffff',
      padding: '12px 20px',
      borderRadius: '8px',
      boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      fontSize: '14px',
      fontWeight: '600',
      zIndex: '999999',
      transition: 'opacity 0.3s ease, transform 0.3s ease',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    });
    document.body.appendChild(toast);
  }

  function setInputValue(input, value) {
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  async function attemptAutoLogin() {
    // 1. Locate username field
    const userInput =
      document.querySelector('input[name="username"]') ||
      document.querySelector('input[id="username"]') ||
      document.querySelector('input[type="text"]');

    // 2. Locate password field
    const passInput =
      document.querySelector('input[name="password"]') ||
      document.querySelector('input[id="password"]') ||
      document.querySelector('input[type="password"]');

    if (!userInput || !passInput) {
      // Not a login form page
      return false;
    }

    showToast('⚡ IIT BHU AutoConnect: Logging in...');

    // Record last connected timestamp in local storage
    const now = Date.now();
    await chrome.storage.local.set({ lastConnectedAt: now });
    try {
      chrome.runtime.sendMessage({ type: 'AUTO_LOGIN_TRIGGERED', timestamp: now });
    } catch {
      // Ignore background message failure
    }

    // Fill credentials
    setInputValue(userInput, username);
    setInputValue(passInput, password);

    // 3. Locate submit/continue button or form
    const form = userInput.form || passInput.form || document.querySelector('form');
    const submitBtn =
      document.querySelector('input[type="submit"]') ||
      document.querySelector('button[type="submit"]') ||
      document.querySelector('input[value*="Continue" i]') ||
      document.querySelector('input[value*="Login" i]') ||
      Array.from(document.querySelectorAll('button, input[type="button"], a')).find(el =>
        /continue|login|sign in|submit/i.test(el.textContent || el.value || '')
      );

    setTimeout(() => {
      if (submitBtn) {
        submitBtn.click();
      } else if (form) {
        form.submit();
      }
    }, 150);

    return true;
  }

  // Attempt login immediately or on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attemptAutoLogin);
  } else {
    attemptAutoLogin();
  }
})();
