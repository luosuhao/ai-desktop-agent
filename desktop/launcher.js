/**
 * AI桌面端系统 - 轻量启动器
 * 双击运行，启动后端 + 打开浏览器窗口，关闭窗口后退出后端
 */
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');

const BACKEND_PORT = 18327;
const rootDir = path.join(__dirname, '..');

function startBackend() {
  const backendExe = path.join(rootDir, 'backend', 'dist', 'backend.exe');
  const backendDir = path.join(rootDir, 'backend');

  let cmd, args;
  if (fs.existsSync(backendExe)) {
    cmd = backendExe;
    args = [];
  } else {
    cmd = 'python';
    args = [path.join(backendDir, 'run.py')];
  }

  const proc = spawn(cmd, args, {
    cwd: backendDir,
    windowsHide: true,
    stdio: 'pipe',
    env: { ...process.env, API_PORT: String(BACKEND_PORT) },
  });

  proc.stdout.on('data', d => process.stdout.write(`[backend] ${d}`));
  proc.stderr.on('data', d => process.stderr.write(`[backend] ${d}`));
  proc.on('exit', code => {
    console.log(`[backend] exited with code ${code}`);
    process.exit();
  });

  return proc;
}

function waitForBackend(maxWait = 45000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      http.get(`http://127.0.0.1:${BACKEND_PORT}/`, (res) => {
        if (res.statusCode === 200) return resolve();
        if (Date.now() - start > maxWait) return reject(new Error('Backend timeout'));
        setTimeout(check, 300);
      }).on('error', () => {
        if (Date.now() - start > maxWait) return reject(new Error('Backend timeout'));
        setTimeout(check, 300);
      });
    };
    check();
  });
}

async function main() {
  console.log('Starting AI Desktop System...');
  const backend = startBackend();

  try {
    await waitForBackend();
    console.log('Backend ready!');

    // Open the frontend in the default browser (standalone window mode)
    const frontendPath = `http://localhost:${BACKEND_PORT}`;
    // Use start for Windows
    spawn('cmd', ['/c', 'start', '', frontendPath], { windowsHide: true, stdio: 'ignore' });

    console.log(`Frontend opened at ${frontendPath}`);
    console.log('Close this window to stop the backend.');

    // Keep running until user closes
    process.stdin.resume();
  } catch (err) {
    console.error('Failed to start:', err.message);
    backend.kill();
    process.exit(1);
  }
}

main();
