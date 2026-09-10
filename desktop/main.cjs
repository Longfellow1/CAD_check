const fs = require('node:fs');
const path = require('node:path');
const { app, BrowserWindow, dialog, ipcMain, Menu, shell } = require('electron');
const { RuntimeManager } = require('./runtime.cjs');

const ROOT = path.resolve(__dirname, '..');
const runtime = new RuntimeManager(ROOT);
const OPEN_DEVTOOLS = process.argv.includes('--devtools') || process.env.CAD_CHECK_DEVTOOLS === '1';
const E2E = process.argv.includes('--e2e') || process.env.CAD_CHECK_E2E === '1';
const E2E_DIR = path.join(ROOT, '.cadcheck', 'e2e');
const E2E_FILE = path.join(E2E_DIR, 'electron-smoke.json');
let mainWindow = null;
let quitting = false;
let requestGuardInstalled = false;
let e2eTimer = null;
let e2eReported = false;

if (E2E) {
  // CI still exercises a real BrowserWindow/Renderer/Babylon code path, but
  // SwiftShader avoids making the contract dependent on runner GPU hardware.
  app.commandLine.appendSwitch('use-angle', 'swiftshader');
  app.commandLine.appendSwitch('enable-unsafe-swiftshader');
}

function writeE2E(payload) {
  fs.mkdirSync(E2E_DIR, { recursive: true });
  fs.writeFileSync(E2E_FILE, JSON.stringify({
    ...payload,
    product_form: 'electron',
    platform: process.platform,
    created_at: new Date().toISOString(),
    runtime: runtime.status(),
  }, null, 2));
}

function finishE2E(payload) {
  if (!E2E || e2eReported) return false;
  e2eReported = true;
  if (e2eTimer) clearTimeout(e2eTimer);
  const ok = payload?.ok === true;
  writeE2E({ ...payload, ok });
  process.exitCode = ok ? 0 : 1;
  setTimeout(() => app.quit(), 75);
  return true;
}

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
      additionalArguments: E2E ? ['--cad-check-e2e=1'] : [],
    },
  });

  installRuntimeRequestGuard(mainWindow);
  mainWindow.once('ready-to-show', () => {
    if (!E2E) mainWindow?.show();
  });
  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.webContents.setWindowOpenHandler(({ url: target }) => {
    if (!E2E) shell.openExternal(target).catch(() => {});
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, target) => {
    const runtimeUrl = runtime.status().url;
    if (!runtimeUrl || !target.startsWith(runtimeUrl)) event.preventDefault();
  });
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    if (E2E) finishE2E({ ok:false, stage:'renderer', error:`renderer gone: ${details.reason}` });
  });
  mainWindow.loadURL(url).catch((error) => {
    if (E2E) finishE2E({ ok:false, stage:'loadURL', error:error.message });
  });

  if (OPEN_DEVTOOLS) mainWindow.webContents.openDevTools({ mode: 'detach' });
}

async function boot() {
  try {
    if (E2E) {
      fs.mkdirSync(E2E_DIR, { recursive: true });
      try { fs.unlinkSync(E2E_FILE); } catch {}
    }
    const status = await runtime.start();
    createWindow(status.url);
    if (E2E) {
      e2eTimer = setTimeout(() => {
        finishE2E({ ok:false, stage:'watchdog', error:'Electron E2E exceeded 240 seconds' });
      }, 240000);
    }
  } catch (error) {
    if (E2E) {
      finishE2E({ ok:false, stage:'boot', error:error?.stack || error?.message || String(error) });
      return;
    }
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
  if (mainWindow && !mainWindow.isDestroyed()) await mainWindow.loadURL(status.url);
  return status;
});
ipcMain.handle('file:open-step', async () => {
  const owner = mainWindow && !mainWindow.isDestroyed() ? mainWindow : undefined;
  const result = await dialog.showOpenDialog(owner, {
    title: '打开 STEP / AP242 模型',
    properties: ['openFile'],
    filters: [
      { name: 'STEP / AP242', extensions: ['step', 'stp'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });
  if (result.canceled || !result.filePaths.length) return null;
  return result.filePaths[0];
});
ipcMain.handle('e2e:report', (_event, payload) => {
  if (!E2E) return false;
  return finishE2E(payload || { ok:false, error:'empty renderer E2E report' });
});

runtime.on('state', (status) => {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.webContents.send('runtime:state', status);
});

app.whenReady().then(boot);
app.on('activate', async () => {
  if (E2E || BrowserWindow.getAllWindows().length > 0) return;
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
  if (E2E || process.platform !== 'darwin') app.quit();
});
app.on('before-quit', (event) => {
  if (quitting || runtime.state === 'STOPPED') return;
  event.preventDefault();
  quitting = true;
  runtime.stop().finally(() => app.quit());
});
