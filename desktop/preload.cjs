const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('cadDesktop', {
  isDesktop: true,
  platform: process.platform,
  runtimeStatus: () => ipcRenderer.invoke('runtime:status'),
  restartRuntime: () => ipcRenderer.invoke('runtime:restart'),
  pickStepFile: () => ipcRenderer.invoke('file:open-step'),
  onRuntimeState: (callback) => {
    if (typeof callback !== 'function') return () => {};
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('runtime:state', listener);
    return () => ipcRenderer.removeListener('runtime:state', listener);
  },
});
