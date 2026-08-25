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
  const lastConnectedTimeEl = document.getElementById('last-connected-time');
  const toast = document.getElementById('toast');

  // 1. Load stored settings and last connected timestamp
  const stored = await chrome.storage.local.get(['username', 'password', 'autoLogin', 'lastConnectedAt']);
  if (stored.username) userInput.value = stored.username;
  if (stored.password) passInput.value = stored.password;
  if (stored.autoLogin !== undefined) autoLoginToggle.checked = stored.autoLogin;
  updateLastConnectedDisplay(stored.lastConnectedAt);

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
    const now = Date.now();
    await chrome.storage.local.set({
      username,
      password,
      autoLogin: autoLoginToggle.checked,
      lastConnectedAt: now
    });
    updateLastConnectedDisplay(now);

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

  function formatTime(timestamp) {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return 'Never';

    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);

    const timeString = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (diffSec < 60) {
      return 'Just now';
    } else if (diffMin < 60) {
      return `${diffMin}m ago (${timeString})`;
    } else if (diffHours < 24 && date.getDate() === now.getDate()) {
      return `Today at ${timeString}`;
    } else if (diffHours < 48 && date.getDate() === now.getDate() - 1) {
      return `Yesterday at ${timeString}`;
    } else {
      const dateString = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      return `${dateString}, ${timeString}`;
    }
  }

  function updateLastConnectedDisplay(timestamp) {
    if (lastConnectedTimeEl) {
      lastConnectedTimeEl.textContent = formatTime(timestamp);
    }
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
