const path = require('node:path');
const { app, BrowserWindow, dialog, ipcMain, Menu, shell } = require('electron');
const { RuntimeManager } = require('./runtime.cjs');

const ROOT = path.resolve(__dirname, '..');
const runtime = new RuntimeManager(ROOT);
const OPEN_DEVTOOLS = process.argv.includes('--devtools') || process.env.CAD_CHECK_DEVTOOLS === '1';
let mainWindow = null;
let quitting = false;
let requestGuardInstalled = false;

function installRuntimeRequestGuard(win) {
  if (requestGuardInstalled) return;
  requestGuardInstalled = true;
  win.webContents.session.webRequest.onBeforeSendHeaders((details, callback) => {
    const runtimeUrl = runtime.status().url;
    const token = runtime.getSessionToken();
    if (runtimeUrl && token && details.url.startsWith(runtimeUrl)) {
      details.requestHeaders['X-CAD-Check-Session'] = token;
      details.requestHeaders['X-CAD-Check-Product-Form'] = 'electron';
    }
    callback({ requestHeaders: details.requestHeaders });
  });
}

function createWindow(url) {
  Menu.setApplicationMenu(null);
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1180,
    minHeight: 720,
    show: false,
    title: 'CAD Check',
    backgroundColor: '#f4f6f8',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  installRuntimeRequestGuard(mainWindow);

  mainWindow.once('ready-to-show', () => mainWindow?.show());
  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.webContents.setWindowOpenHandler(({ url: target }) => {
    shell.openExternal(target).catch(() => {});
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, target) => {
    const runtimeUrl = runtime.status().url;
    if (!runtimeUrl || !target.startsWith(runtimeUrl)) event.preventDefault();
  });
  mainWindow.loadURL(url);

  if (OPEN_DEVTOOLS) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }
}

async function boot() {
  try {
    const status = await runtime.start();
    createWindow(status.url);
  } catch (error) {
    await dialog.showMessageBox({
      type: 'error',
      title: 'CAD Check 启动失败',
      message: 'CAD Runtime 未能启动',
      detail: error?.stack || error?.message || String(error),
    });
    app.quit();
  }
}

ipcMain.handle('runtime:status', () => runtime.status());
ipcMain.handle('runtime:restart', async () => {
  const status = await runtime.restart();
  if (mainWindow && !mainWindow.isDestroyed()) {
    await mainWindow.loadURL(status.url);
  }
  return status;
});

runtime.on('state', (status) => {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.webContents.send('runtime:state', status);
});

app.whenReady().then(boot);

app.on('activate', async () => {
  if (BrowserWindow.getAllWindows().length > 0) return;
  try {
    const status = runtime.state === 'RUNNING' ? runtime.status() : await runtime.start();
    createWindow(status.url);
  } catch (error) {
    await dialog.showMessageBox({
      type: 'error',
      title: 'CAD Check 启动失败',
      message: 'CAD Runtime 未能启动',
      detail: error?.message || String(error),
    });
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', (event) => {
  if (quitting || runtime.state === 'STOPPED') return;
  event.preventDefault();
  quitting = true;
  runtime.stop().finally(() => app.quit());
});
