#!/usr/bin/env node
/**
 * Cross-platform environment verification script
 * Checks that all requirements are met before running the application
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const os = require('os');

const PROJECT_ROOT = __dirname;
const isWindows = process.platform === 'win32';

const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function checkCommand(command) {
  try {
    execSync(command, { stdio: 'ignore' });
    return true;
  } catch (e) {
    return false;
  }
}

function getPythonCommand() {
  if (checkCommand('python3 --version')) return 'python3';
  if (checkCommand('python --version')) return 'python';
  return null;
}

function verifyNode() {
  try {
    const version = execSync('node --version', { encoding: 'utf8' }).trim();
    const major = parseInt(version.replace('v', '').split('.')[0]);
    if (major >= 18) {
      log(`✅ Node.js: ${version}`, 'green');
      return true;
    } else {
      log(`❌ Node.js version too old: ${version} (need 18+)`, 'red');
      return false;
    }
  } catch (e) {
    log(`❌ Node.js not found`, 'red');
    return false;
  }
}

function verifyPython() {
  const pythonCmd = getPythonCommand();
  if (!pythonCmd) {
    log(`❌ Python not found`, 'red');
    return false;
  }
  
  try {
    const version = execSync(`${pythonCmd} --version`, { encoding: 'utf8' }).trim();
    log(`✅ Python: ${version}`, 'green');
    return true;
  } catch (e) {
    log(`❌ Python not found`, 'red');
    return false;
  }
}

function verifyEnvFile() {
  const envFile = path.join(PROJECT_ROOT, '.env');
  if (!fs.existsSync(envFile)) {
    log(`❌ .env file not found`, 'red');
    log(`   Run: node setup.js`, 'yellow');
    return false;
  }
  
  const envContent = fs.readFileSync(envFile, 'utf8');
  const required = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET'];
  const missing = [];
  
  for (const varName of required) {
    const regex = new RegExp(`^${varName}=(.+)$`, 'm');
    const match = envContent.match(regex);
    if (!match || !match[1] || match[1].trim() === '') {
      missing.push(varName);
    }
  }
  
  if (missing.length > 0) {
    log(`❌ Missing environment variables: ${missing.join(', ')}`, 'red');
    log(`   Please edit .env and add your Google OAuth credentials`, 'yellow');
    return false;
  }
  
  log(`✅ Environment variables configured`, 'green');
  return true;
}

function verifyServices() {
  const services = [
    'api-gateway',
    'auth-service',
    'gmail-connector-service',
    'application-service',
    'email-intelligence-service',
    'notification-service',
  ];
  
  let allOk = true;
  for (const service of services) {
    const servicePath = path.join(PROJECT_ROOT, 'services', service);
    const venvPath = path.join(servicePath, 'venv');
    
    if (!fs.existsSync(servicePath)) {
      log(`❌ Service directory not found: ${service}`, 'red');
      allOk = false;
      continue;
    }
    
    if (!fs.existsSync(venvPath)) {
      log(`⚠️  Virtual environment not found: ${service}`, 'yellow');
      log(`   Run: node setup.js`, 'yellow');
      allOk = false;
      continue;
    }
    
    // Check if uvicorn is installed
    const pythonCmd = isWindows 
      ? path.join(venvPath, 'Scripts', 'python.exe')
      : path.join(venvPath, 'bin', 'python');
    
    if (!fs.existsSync(pythonCmd)) {
      log(`⚠️  Python executable not found in venv: ${service}`, 'yellow');
      allOk = false;
      continue;
    }
    
    try {
      execSync(`"${pythonCmd}" -c "import uvicorn"`, { stdio: 'ignore' });
      log(`✅ ${service}: Ready`, 'green');
    } catch (e) {
      log(`⚠️  ${service}: Dependencies not installed`, 'yellow');
      log(`   Run: node setup.js`, 'yellow');
      allOk = false;
    }
  }
  
  return allOk;
}

function verifyFrontend() {
  const frontendPath = path.join(PROJECT_ROOT, 'frontend');
  const nodeModulesPath = path.join(frontendPath, 'node_modules');
  
  if (!fs.existsSync(frontendPath)) {
    log(`❌ Frontend directory not found`, 'red');
    return false;
  }
  
  if (!fs.existsSync(nodeModulesPath)) {
    log(`⚠️  Frontend dependencies not installed`, 'yellow');
    log(`   Run: cd frontend && npm install`, 'yellow');
    return false;
  }
  
  log(`✅ Frontend: Ready`, 'green');
  return true;
}

function main() {
  console.log('\n' + '='.repeat(60));
  log('Environment Verification', 'blue');
  console.log('='.repeat(60) + '\n');
  
  log(`Platform: ${process.platform}`, 'blue');
  log(`OS: ${os.type()} ${os.release()}`, 'blue');
  console.log('');
  
  const checks = [
    { name: 'Node.js', fn: verifyNode },
    { name: 'Python', fn: verifyPython },
    { name: 'Environment File', fn: verifyEnvFile },
    { name: 'Backend Services', fn: verifyServices },
    { name: 'Frontend', fn: verifyFrontend },
  ];
  
  let allPassed = true;
  for (const check of checks) {
    if (!check.fn()) {
      allPassed = false;
    }
    console.log('');
  }
  
  console.log('='.repeat(60));
  if (allPassed) {
    log('✅ All checks passed! Ready to run.', 'green');
    process.exit(0);
  } else {
    log('❌ Some checks failed. Please fix the issues above.', 'red');
    process.exit(1);
  }
}

main();
