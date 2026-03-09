const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const pythonPath = path.join(__dirname, '..', 'venv', 'bin', 'python');
const net = require('net');

const isDev = process.env.NODE_ENV === 'development';
let mainWindow;
let pythonProcess = null;
let backendPort = 8000;

function findFreePort(startPort) {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.listen(startPort, '127.0.0.1', () => {
            const port = server.address().port;
            server.close(() => resolve(port));
        });
        server.on('error', () =>
            findFreePort(startPort + 1).then(resolve).catch(reject)
        );
    });
}

function startPythonBackend(port) {
    return new Promise((resolve, reject) => {
        const projectRoot = path.join(__dirname, '..');

        if (isDev) {
            // Dev mode: run python directly
            const pythonBin = process.platform === 'win32' ? 'python' : 'python3';
            const scriptPath = path.join(projectRoot, 'backend_entry.py');
            pythonProcess = spawn(pythonPath, [scriptPath, String(port)], {  // ← use pythonPath here
                cwd: projectRoot,
                env: { ...process.env },
            });
        } else {
            // Production: run PyInstaller frozen binary
            const binaryName = process.platform === 'win32'
                ? 'blockchain_server.exe'
                : 'blockchain_server';
            const binaryPath = path.join(
                process.resourcesPath,
                'blockchain_server',
                binaryName
            );
            pythonProcess = spawn(binaryPath, [String(port)], {
                cwd: projectRoot,
            });
        }

        pythonProcess.stdout.on('data', (d) => console.log('[Python]', d.toString()));
        pythonProcess.stderr.on('data', (d) => console.error('[Python ERR]', d.toString()));
        pythonProcess.on('error', (err) => reject(err));

        // Poll until backend is up
        let tries = 0;
        const poll = setInterval(() => {
            const sock = net.createConnection({ port, host: '127.0.0.1' });
            sock.on('connect', () => {
                sock.destroy();
                clearInterval(poll);
                console.log(`[Electron] Backend ready on port ${port}`);
                resolve(port);
            });
            sock.on('error', () => {
                sock.destroy();
                if (++tries > 40) {
                    clearInterval(poll);
                    reject(new Error('Backend did not start in time'));
                }
            });
        }, 500);
    });
}

function createWindow(port) {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
        minWidth: 900,
        minHeight: 600,
        title: 'Permissioned Blockchain Manager',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });

    if (isDev) {
        mainWindow.loadURL(`http://localhost:3000?backendPort=${port}`);
        mainWindow.webContents.openDevTools();
    } else {
        mainWindow.loadFile(
            path.join(__dirname, '..', 'frontend', 'build', 'index.html'),
            { query: { backendPort: String(port) } }
        );
    }

    mainWindow.on('closed', () => { mainWindow = null; });
}

ipcMain.handle('get-backend-port', () => backendPort);

app.whenReady().then(async () => {
    try {
        backendPort = await findFreePort(8000);
        await startPythonBackend(backendPort);
        createWindow(backendPort);
    } catch (err) {
        dialog.showErrorBox(
            'Startup Error',
            `Could not start blockchain backend:\n\n${err.message}`
        );
        app.quit();
    }
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
    if (!mainWindow) createWindow(backendPort);
});

app.on('before-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
    }
});
