#!/usr/bin/env node
/**
 * Cross-platform script to start all services
 * Works on Windows, macOS, and Linux
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const PROJECT_ROOT = __dirname;
const isWindows = process.platform === 'win32';

const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function startService(serviceName, port) {
  const servicePath = path.join(PROJECT_ROOT, 'services', serviceName);
  const venvPath = path.join(servicePath, 'venv');
  
  if (!fs.existsSync(servicePath)) {
    log(`❌ Service not found: ${serviceName}`, 'red');
    return null;
  }
  
  if (!fs.existsSync(venvPath)) {
    log(`❌ Virtual environment not found for ${serviceName}. Run: npm run setup`, 'red');
    return null;
  }
  
  const pythonCmd = isWindows
    ? path.join(venvPath, 'Scripts', 'python.exe')
    : path.join(venvPath, 'bin', 'python');
  
  if (!fs.existsSync(pythonCmd)) {
    log(`❌ Python not found in venv for ${serviceName}`, 'red');
    return null;
  }
  
  const args = ['-m', 'uvicorn', 'app.main:app', '--reload', '--host', '0.0.0.0', `--port`, port.toString()];
  
  log(`🚀 Starting ${serviceName} on port ${port}...`, 'blue');
  
  const proc = spawn(pythonCmd, args, {
    cwd: servicePath,
    stdio: 'inherit',
    shell: false,
  });
  
  proc.on('error', (err) => {
    log(`❌ Failed to start ${serviceName}: ${err.message}`, 'red');
  });
  
  return proc;
}

function startFrontend() {
  const frontendPath = path.join(PROJECT_ROOT, 'frontend');
  
  if (!fs.existsSync(frontendPath)) {
    log(`❌ Frontend directory not found`, 'red');
    return null;
  }
  
  log(`🚀 Starting frontend on port 5173...`, 'blue');
  
  const proc = spawn(isWindows ? 'npm.cmd' : 'npm', ['run', 'dev'], {
    cwd: frontendPath,
    stdio: 'inherit',
    shell: false,
  });
  
  proc.on('error', (err) => {
    log(`❌ Failed to start frontend: ${err.message}`, 'red');
  });
  
  return proc;
}

function main() {
  console.log('\n' + '='.repeat(60));
  log('Starting All Services', 'cyan');
  console.log('='.repeat(60) + '\n');
  
  log(`Platform: ${process.platform}`, 'blue');
  log(`OS: ${os.type()} ${os.release()}`, 'blue');
  console.log('');
  
  // Verify environment first (but don't block startup)
  try {
    const { spawn } = require('child_process');
    const verifyProc = spawn('node', ['verify.js'], { stdio: 'pipe' });
    verifyProc.on('close', (code) => {
      if (code !== 0) {
        log('⚠️  Environment verification found issues - continuing anyway', 'yellow');
        log('   Add Google OAuth credentials to .env for full functionality', 'yellow');
      }
    });
  } catch (e) {
    log('⚠️  Environment verification skipped', 'yellow');
  }
  
  const services = [
    { name: 'api-gateway', port: 8000 },
    { name: 'auth-service', port: 8003 },
    { name: 'gmail-connector-service', port: 8001 },
    { name: 'application-service', port: 8002 },
    { name: 'email-intelligence-service', port: 8004 },
    { name: 'notification-service', port: 8005 },
  ];
  
  const processes = [];
  
  // Start backend services
  for (const service of services) {
    const proc = startService(service.name, service.port);
    if (proc) {
      processes.push(proc);
    }
    // Small delay between starts
    setTimeout(() => {}, 500);
  }
  
  // Start frontend
  setTimeout(() => {
    const frontendProc = startFrontend();
    if (frontendProc) {
      processes.push(frontendProc);
    }
  }, 2000);
  
  // Handle cleanup
  process.on('SIGINT', () => {
    log('\n\n🛑 Shutting down services...', 'yellow');
    processes.forEach(proc => {
      if (proc && !proc.killed) {
        proc.kill();
      }
    });
    process.exit(0);
  });
  
  log('\n✅ All services starting...', 'green');
  log('Press Ctrl+C to stop all services\n', 'yellow');
  log('Services will be available at:', 'cyan');
  log('  - Frontend: http://localhost:5173', 'blue');
  log('  - API Gateway: http://localhost:8000', 'blue');
  log('  - Auth Service: http://localhost:8003', 'blue');
  log('  - Gmail Connector: http://localhost:8001', 'blue');
  log('  - Application Service: http://localhost:8002', 'blue');
  log('  - Email Intelligence: http://localhost:8004', 'blue');
  log('  - Notification Service: http://localhost:8005', 'blue');
  console.log('');
}

main();
