const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  candidatePythonPaths,
  findPython,
  reservePort,
  waitForHealth,
} = require('./runtime.cjs');

test('candidate python path follows platform venv layout', () => {
  const root = path.join('/tmp', 'cad-check');
  delete process.env.CAD_CHECK_PYTHON;
  assert.equal(candidatePythonPaths(root, 'darwin')[0], path.join(root, '.venv', 'bin', 'python'));
  assert.equal(candidatePythonPaths(root, 'win32')[0], path.join(root, '.venv', 'Scripts', 'python.exe'));
});

test('findPython resolves an explicit existing override', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'cad-check-runtime-'));
  const fakePython = path.join(tmp, 'python');
  fs.writeFileSync(fakePython, '');
  const previous = process.env.CAD_CHECK_PYTHON;
  process.env.CAD_CHECK_PYTHON = fakePython;
  try {
    assert.equal(findPython(tmp), fakePython);
  } finally {
    if (previous === undefined) delete process.env.CAD_CHECK_PYTHON;
    else process.env.CAD_CHECK_PYTHON = previous;
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test('reservePort returns a usable loopback port', async () => {
  const port = await reservePort();
  assert.ok(Number.isInteger(port));
  assert.ok(port > 0 && port < 65536);
});

test('waitForHealth accepts a responding local health endpoint', async () => {
  const server = http.createServer((request, response) => {
    if (request.url === '/api/health') {
      response.writeHead(200, { 'content-type': 'application/json' });
      response.end('{"ok":true}');
      return;
    }
    response.writeHead(404);
    response.end();
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  try {
    await waitForHealth(`http://127.0.0.1:${address.port}/api/health`, {
      timeoutMs: 1000,
      intervalMs: 20,
    });
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('waitForHealth sends Electron session and product-form headers', async () => {
  const token = 'test-session-token';
  const server = http.createServer((request, response) => {
    const ok = request.url === '/api/health'
      && request.headers['x-cad-check-session'] === token
      && request.headers['x-cad-check-product-form'] === 'electron';
    response.writeHead(ok ? 200 : 403, { 'content-type': 'application/json' });
    response.end(ok ? '{"ok":true}' : '{"ok":false}');
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  try {
    await waitForHealth(`http://127.0.0.1:${address.port}/api/health`, {
      token,
      timeoutMs: 1000,
      intervalMs: 20,
    });
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
