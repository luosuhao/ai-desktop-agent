const { contextBridge } = require('electron');

// Expose minimal API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  getBackendUrl: () => `http://127.0.0.1:18327`,
  isDesktopApp: true,
});
