/**
 * IIT BHU Wi-Fi AutoConnect - Service Worker (Manifest V3)
 */

chrome.runtime.onInstalled.addListener(async () => {
  console.log('[IIT BHU AutoConnect] Extension installed.');
  const data = await chrome.storage.local.get(['autoLogin']);
  if (data.autoLogin === undefined) {
    await chrome.storage.local.set({ autoLogin: true });
  }

  // Set up periodic connectivity check alarm (every 5 minutes)
  await chrome.alarms.create('checkConnectivity', { periodInMinutes: 5 });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && (message.type === 'AUTO_LOGIN_TRIGGERED' || message.type === 'LOGIN_SUCCESS')) {
    const timestamp = message.timestamp || Date.now();
    chrome.storage.local.set({ lastConnectedAt: timestamp });
  }
  return false;
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'checkConnectivity') {
    try {
      const response = await fetch('http://connectivitycheck.gstatic.com/generate_204', {
        method: 'GET',
        cache: 'no-cache'
      });
      if (response.status === 204) {
        await chrome.action.setBadgeText({ text: 'ON' });
        await chrome.action.setBadgeBackgroundColor({ color: '#10B981' }); // Green
      } else {
        await chrome.action.setBadgeText({ text: '!' });
        await chrome.action.setBadgeBackgroundColor({ color: '#F59E0B' }); // Orange
      }
    } catch {
      await chrome.action.setBadgeText({ text: 'OFF' });
      await chrome.action.setBadgeBackgroundColor({ color: '#EF4444' }); // Red
    }
  }
});
