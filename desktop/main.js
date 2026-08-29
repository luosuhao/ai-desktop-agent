const { app, BrowserWindow, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let backendProcess = null;
let tray = null;
const BACKEND_PORT = 18327; // Fixed port to avoid conflicts

// Determine resource paths (dev vs production)
const isDev = !app.isPackaged;
const rootDir = isDev
  ? path.join(__dirname, '..')
  : process.resourcesPath;

const frontendPath = path.join(rootDir, 'frontend', 'dist', 'index.html');
const backendDir = path.join(rootDir, 'backend');
const backendExe = path.join(backendDir, 'dist', 'backend.exe');
const iconPath = path.join(__dirname, 'icon.ico');

/** Wait until backend is reachable */
function waitForBackend(maxWaitMs = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/`, (res) => {
        if (res.statusCode === 200) return resolve();
        if (Date.now() - start > maxWaitMs) return reject(new Error('Backend timeout'));
        setTimeout(check, 300);
      });
      req.on('error', () => {
        if (Date.now() - start > maxWaitMs) return reject(new Error('Backend timeout'));
        setTimeout(check, 300);
      });
      req.end();
    };
    check();
  });
}

/** Start the Python backend as a hidden process */
function startBackend() {
  const fs = require('fs');
  // Prefer PyInstaller exe, fall back to system Python
  let cmd, args;
  if (fs.existsSync(backendExe)) {
    cmd = backendExe;
    args = [];
  } else {
    cmd = 'python';
    args = [path.join(backendDir, 'run.py')];
  }

  const logPath = path.join(app.getPath('userData'), 'backend.log');
  const logStream = require('fs').createWriteStream(logPath, { flags: 'a' });

  backendProcess = spawn(cmd, args, {
    cwd: backendDir,
    windowsHide: true,
    stdio: 'pipe',
    env: { ...process.env, API_PORT: String(BACKEND_PORT) },
  });

  backendProcess.stdout.on('data', (d) => {
    logStream.write(`[stdout] ${d}`);
    if (isDev) console.log(`[backend] ${d}`);
  });
  backendProcess.stderr.on('data', (d) => {
    logStream.write(`[stderr] ${d}`);
    if (isDev) console.error(`[backend] ${d}`);
  });
  backendProcess.on('exit', (code) => {
    logStream.write(`[exit] code=${code}\n`);
    logStream.end();
    if (isDev) console.log(`[backend] exited with code ${code}`);
    backendProcess = null;
  });
}

/** Kill backend process */
function stopBackend() {
  if (backendProcess) {
    backendProcess.kill('SIGTERM');
    // Force kill after 3s
    setTimeout(() => {
      if (backendProcess) {
        try { backendProcess.kill('SIGKILL'); } catch (_) {}
      }
    }, 3000);
  }
}

/** Create system tray icon */
function createTray() {
  try {
    const icon = nativeImage.createFromPath(iconPath);
    tray = new Tray(icon.resize({ width: 16, height: 16 }));
    tray.setToolTip('AI桌面端系统');
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: '显示窗口', click: () => { if (mainWindow) mainWindow.show(); } },
      { label: '退出', click: () => { app.isQuitting = true; app.quit(); } },
    ]));
    tray.on('double-click', () => { if (mainWindow) mainWindow.show(); });
  } catch (_) { /* tray not critical */ }
}

/** Create the main application window */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    icon: iconPath,
    title: 'AI桌面端系统',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Hide menu bar for cleaner look
  mainWindow.setMenuBarVisibility(false);

  // Load frontend
  mainWindow.loadFile(frontendPath);

  // Show window when ready
  mainWindow.once('ready-to-show', () => mainWindow.show());

  // Close window = quit app (user can minimize normally)
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      app.isQuitting = true;
      app.quit();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ---- App lifecycle ----

app.whenReady().then(async () => {
  // Start backend
  startBackend();

  // Create window immediately (shows blank while backend loads)
  createWindow();
  createTray();

  // Wait for backend, then reload to show full UI
  try {
    await waitForBackend(45000);
    if (mainWindow) mainWindow.loadFile(frontendPath);
  } catch (err) {
    // If backend fails, show error but keep window open
    if (mainWindow) {
      mainWindow.loadURL(`data:text/html,<h2 style="color:red">后端启动失败</h2><p>${err.message}</p>`);
    }
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  app.isQuitting = true;
  stopBackend();
});

app.on('will-quit', () => {
  stopBackend();
  if (tray) { tray.destroy(); tray = null; }
});
