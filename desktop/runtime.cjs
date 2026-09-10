const { EventEmitter } = require('node:events');
const { spawn, execFile } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const net = require('node:net');
const path = require('node:path');

function candidatePythonPaths(root, platform = process.platform) {
  const envPython = process.env.CAD_CHECK_PYTHON;
  const local = platform === 'win32'
    ? path.join(root, '.venv', 'Scripts', 'python.exe')
    : path.join(root, '.venv', 'bin', 'python');
  return [envPython, local].filter(Boolean);
}

function findPython(root, platform = process.platform) {
  for (const candidate of candidatePythonPaths(root, platform)) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error('未找到 CAD Check Python 环境。请先运行 Electron bootstrap，或设置 CAD_CHECK_PYTHON。');
}

function reservePort(host = '127.0.0.1') {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.once('error', reject);
    server.listen(0, host, () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : null;
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

function healthOnce(url, token = null, timeoutMs = 1000) {
  return new Promise((resolve, reject) => {
    const headers = token ? {
      'X-CAD-Check-Session': token,
      'X-CAD-Check-Product-Form': 'electron',
    } : {};
    const request = http.get(url, { timeout: timeoutMs, headers }, (response) => {
      response.resume();
      if (response.statusCode === 200) resolve(true);
      else reject(new Error(`health returned ${response.statusCode}`));
    });
    request.on('timeout', () => request.destroy(new Error('health timeout')));
    request.on('error', reject);
  });
}

async function waitForHealth(url, { timeoutMs = 30000, intervalMs = 250, token = null } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      await healthOnce(url, token);
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
  }
  throw new Error(`CAD Runtime 启动超时：${lastError?.message || 'unknown error'}`);
}

function killProcessTree(child) {
  if (!child || child.killed || child.exitCode !== null) return Promise.resolve();
  if (process.platform === 'win32') {
    return new Promise((resolve) => {
      execFile('taskkill', ['/pid', String(child.pid), '/T', '/F'], () => resolve());
    });
  }
  child.kill('SIGTERM');
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      if (child.exitCode === null) child.kill('SIGKILL');
      resolve();
    }, 2500);
    child.once('exit', () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

class RuntimeManager extends EventEmitter {
  constructor(root) {
    super();
    this.root = root;
    this.child = null;
    this.port = null;
    this.sessionToken = null;
    this.state = 'STOPPED';
    this.lastError = null;
  }

  status() {
    return {
      state: this.state,
      port: this.port,
      pid: this.child?.pid || null,
      url: this.port ? `http://127.0.0.1:${this.port}` : null,
      productForm: 'electron',
      error: this.lastError?.message || null,
    };
  }

  getSessionToken() {
    return this.sessionToken;
  }

  async start() {
    if (this.state === 'RUNNING') return this.status();
    if (this.state === 'STARTING') throw new Error('CAD Runtime 正在启动');

    this.state = 'STARTING';
    this.lastError = null;
    this.emit('state', this.status());

    try {
      const python = findPython(this.root);
      this.port = await reservePort();
      this.sessionToken = crypto.randomBytes(24).toString('hex');
      const args = [
        '-m', 'uvicorn', 'server.app_v2:app',
        '--host', '127.0.0.1',
        '--port', String(this.port),
      ];
      this.child = spawn(python, args, {
        cwd: this.root,
        env: {
          ...process.env,
          PORT: String(this.port),
          CAD_CHECK_DESKTOP: '1',
          CAD_CHECK_PRODUCT_FORM: 'electron',
          CAD_CHECK_SESSION_TOKEN: this.sessionToken,
          PYTHONUNBUFFERED: '1',
        },
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      });

      this.child.stdout.on('data', (data) => process.stdout.write(`[cad-runtime] ${data}`));
      this.child.stderr.on('data', (data) => process.stderr.write(`[cad-runtime] ${data}`));
      this.child.once('exit', (code, signal) => {
        const unexpected = !['STOPPING', 'STOPPED'].includes(this.state);
        this.child = null;
        if (unexpected) {
          this.state = 'FAILED';
          this.lastError = new Error(`CAD Runtime 已退出 (code=${code}, signal=${signal})`);
        } else {
          this.state = 'STOPPED';
        }
        this.emit('state', this.status());
      });

      await waitForHealth(`http://127.0.0.1:${this.port}/api/health`, {
        token: this.sessionToken,
      });
      this.state = 'RUNNING';
      this.emit('state', this.status());
      return this.status();
    } catch (error) {
      this.lastError = error;
      this.state = 'FAILED';
      await killProcessTree(this.child);
      this.child = null;
      this.emit('state', this.status());
      throw error;
    }
  }

  async stop() {
    if (!this.child) {
      this.state = 'STOPPED';
      this.port = null;
      this.sessionToken = null;
      return this.status();
    }
    this.state = 'STOPPING';
    this.emit('state', this.status());
    const child = this.child;
    await killProcessTree(child);
    this.child = null;
    this.port = null;
    this.sessionToken = null;
    this.state = 'STOPPED';
    this.emit('state', this.status());
    return this.status();
  }

  async restart() {
    await this.stop();
    return this.start();
  }
}

module.exports = {
  RuntimeManager,
  candidatePythonPaths,
  findPython,
  healthOnce,
  reservePort,
  waitForHealth,
};
