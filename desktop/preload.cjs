const { contextBridge, ipcRenderer } = require('electron');

const isE2E = process.argv.includes('--cad-check-e2e=1');

contextBridge.exposeInMainWorld('cadDesktop', {
  isDesktop: true,
  isE2E,
  platform: process.platform,
  runtimeStatus: () => ipcRenderer.invoke('runtime:status'),
  restartRuntime: () => ipcRenderer.invoke('runtime:restart'),
  pickStepFile: () => ipcRenderer.invoke('file:open-step'),
  reportE2E: (payload) => isE2E ? ipcRenderer.invoke('e2e:report', payload) : Promise.resolve(false),
  onRuntimeState: (callback) => {
    if (typeof callback !== 'function') return () => {};
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('runtime:state', listener);
    return () => ipcRenderer.removeListener('runtime:state', listener);
  },
});
