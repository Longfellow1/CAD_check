const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('cadDesktop', {
  isDesktop: true,
  platform: process.platform,
  runtimeStatus: () => ipcRenderer.invoke('runtime:status'),
  restartRuntime: () => ipcRenderer.invoke('runtime:restart'),
  onRuntimeState: (callback) => {
    if (typeof callback !== 'function') return () => {};
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('runtime:state', listener);
    return () => ipcRenderer.removeListener('runtime:state', listener);
  },
});
