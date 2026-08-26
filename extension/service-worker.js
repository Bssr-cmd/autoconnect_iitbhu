/**
 * IIT BHU Wi-Fi AutoConnect - Service Worker (Manifest V3)
 */

// Initialize extension on install
chrome.runtime.onInstalled.addListener(async () => {
  console.log('[IIT BHU AutoConnect] Extension installed/updated.');
  const data = await chrome.storage.local.get(['autoLogin']);
  if (data.autoLogin === undefined) {
    await chrome.storage.local.set({ autoLogin: true });
  }

  // Periodic connectivity & badge refresh alarm (every 3 minutes)
  await chrome.alarms.create('checkConnectivity', { periodInMinutes: 3 });
  await updateConnectionBadge();
});

chrome.runtime.onStartup.addListener(async () => {
  await updateConnectionBadge();
});

// React instantly to settings / credentials / toggle changes
chrome.storage.onChanged.addListener(async (changes, area) => {
  if (area === 'local' && (changes.autoLogin || changes.username || changes.password)) {
    await updateConnectionBadge();
  }
});

// Handle auto-login messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && (message.type === 'AUTO_LOGIN_TRIGGERED' || message.type === 'LOGIN_SUCCESS')) {
    const timestamp = message.timestamp || Date.now();
    chrome.storage.local.set({ lastConnectedAt: timestamp });
    updateConnectionBadge();
  }
  return false;
});

/**
 * Updates the extension badge text and color based on Auto-Login state & connectivity.
 */
async function updateConnectionBadge() {
  const data = await chrome.storage.local.get(['autoLogin', 'username', 'password']);
  const autoLogin = data.autoLogin !== false; // default true
  const isConfigured = Boolean(data.username && data.password);

  // If user disabled Auto-Login in popup
  if (!autoLogin) {
    await chrome.action.setBadgeText({ text: 'OFF' });
    await chrome.action.setBadgeBackgroundColor({ color: '#64748B' }); // Slate Grey
    return;
  }

  // If not configured with credentials yet
  if (!isConfigured) {
    await chrome.action.setBadgeText({ text: 'SET' });
    await chrome.action.setBadgeBackgroundColor({ color: '#3B82F6' }); // Blue
    return;
  }

  // Check connectivity
  let isOnline = false;
  try {
    const response = await fetch('https://www.google.com/generate_204', {
      method: 'GET',
      cache: 'no-cache',
      mode: 'no-cors'
    });
    // With mode 'no-cors', a successful network probe returns opaque response
    isOnline = true;
  } catch {
    // Fallback probe
    try {
      const resp2 = await fetch('http://detectportal.firefox.com/canonical.html', {
        method: 'GET',
        cache: 'no-cache'
      });
      if (resp2.ok) {
        isOnline = true;
      }
    } catch {
      isOnline = false;
    }
  }

  if (isOnline) {
    await chrome.action.setBadgeText({ text: 'ON' });
    await chrome.action.setBadgeBackgroundColor({ color: '#10B981' }); // Vibrant Green
  } else {
    // Captive portal or offline
    await chrome.action.setBadgeText({ text: '!' });
    await chrome.action.setBadgeBackgroundColor({ color: '#F59E0B' }); // Orange warning
  }
}

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'checkConnectivity') {
    await updateConnectionBadge();
  }
});
