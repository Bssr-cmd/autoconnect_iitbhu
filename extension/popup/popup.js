/**
 * IIT BHU Wi-Fi AutoConnect - Popup Controller
 */

document.addEventListener('DOMContentLoaded', async () => {
  const form = document.getElementById('auth-form');
  const userInput = document.getElementById('username');
  const passInput = document.getElementById('password');
  const autoLoginToggle = document.getElementById('auto-login-toggle');
  const togglePassBtn = document.getElementById('toggle-password');
  const connectBtn = document.getElementById('connect-btn');
  const statusPill = document.getElementById('status-pill');
  const toast = document.getElementById('toast');

  // 1. Load stored settings
  const stored = await chrome.storage.local.get(['username', 'password', 'autoLogin']);
  if (stored.username) userInput.value = stored.username;
  if (stored.password) passInput.value = stored.password;
  if (stored.autoLogin !== undefined) autoLoginToggle.checked = stored.autoLogin;

  // 2. Check network status
  checkStatus();

  // 3. Password visibility toggle
  togglePassBtn.addEventListener('click', () => {
    const isPassword = passInput.type === 'password';
    passInput.type = isPassword ? 'text' : 'password';
    togglePassBtn.textContent = isPassword ? '🙈' : '👁️';
  });

  // 4. Save credentials
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = userInput.value.trim();
    const password = passInput.value;
    const autoLogin = autoLoginToggle.checked;

    if (!username || !password) {
      showToast('Please enter both username and password.', false);
      return;
    }

    await chrome.storage.local.set({ username, password, autoLogin });
    showToast('✓ Credentials saved successfully!', true);
    checkStatus();
  });

  // 5. Connect Now button
  connectBtn.addEventListener('click', async () => {
    const username = userInput.value.trim();
    const password = passInput.value;

    if (!username || !password) {
      showToast('Please enter credentials first.', false);
      return;
    }

    // Save first
    await chrome.storage.local.set({ username, password, autoLogin: autoLoginToggle.checked });

    showToast('Opening portal...', true);
    // Open captive portal in a tab
    chrome.tabs.create({ url: 'http://detectportal.firefox.com/canonical.html' });
  });

  function showToast(message, isSuccess = true) {
    toast.textContent = message;
    toast.className = `toast ${isSuccess ? 'toast-success' : 'toast-error'}`;
    toast.classList.remove('hidden');

    setTimeout(() => {
      toast.classList.add('hidden');
    }, 3000);
  }

  async function checkStatus() {
    statusPill.textContent = 'Checking...';
    statusPill.className = 'status-pill status-ready';

    try {
      const resp = await fetch('http://connectivitycheck.gstatic.com/generate_204', {
        method: 'GET',
        cache: 'no-cache'
      });

      if (resp.status === 204) {
        statusPill.textContent = 'Connected';
        statusPill.className = 'status-pill status-online';
      } else {
        statusPill.textContent = 'Login Required';
        statusPill.className = 'status-pill status-portal';
      }
    } catch {
      statusPill.textContent = 'Offline / Portal';
      statusPill.className = 'status-pill status-portal';
    }
  }
});
