#!/usr/bin/env node
/**
 * Cross-platform setup script for Email Sync Job Dashboard
 * Works on Windows, macOS, and Linux
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const os = require('os');

const PROJECT_ROOT = __dirname;
const isWindows = process.platform === 'win32';
const isMac = process.platform === 'darwin';
const isLinux = process.platform === 'linux';

// Colors for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logSection(title) {
  console.log('\n' + '='.repeat(60));
  log(title, 'cyan');
  console.log('='.repeat(60));
}

function checkCommand(command, errorMessage) {
  try {
    execSync(command, { stdio: 'ignore' });
    return true;
  } catch (e) {
    log(`❌ ${errorMessage}`, 'red');
    return false;
  }
}

function getPythonCommand() {
  // Try python3 first (Mac/Linux), then python (Windows)
  if (checkCommand('python3 --version', '')) {
    return 'python3';
  }
  if (checkCommand('python --version', '')) {
    return 'python';
  }
  return null;
}

function getNodeVersion() {
  try {
    const version = execSync('node --version', { encoding: 'utf8' }).trim();
    return version;
  } catch (e) {
    return null;
  }
}

function getPythonVersion() {
  const pythonCmd = getPythonCommand();
  if (!pythonCmd) return null;
  try {
    const version = execSync(`${pythonCmd} --version`, { encoding: 'utf8' }).trim();
    return version;
  } catch (e) {
    return null;
  }
}

function ensureDirectory(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
    log(`✅ Created directory: ${dirPath}`, 'green');
  }
}

function copyEnvExample() {
  const envExample = path.join(PROJECT_ROOT, '.env.example');
  const envFile = path.join(PROJECT_ROOT, '.env');
  
  if (!fs.existsSync(envFile)) {
    if (fs.existsSync(envExample)) {
      fs.copyFileSync(envExample, envFile);
      log(`✅ Created .env from .env.example`, 'green');
      log(`⚠️  Please edit .env and add your Google OAuth credentials`, 'yellow');
    } else {
      // Create minimal .env file
      const envContent = `# Google OAuth Configuration
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback

# Service URLs (defaults - usually don't need to change)
AUTH_SERVICE_URL=http://localhost:8003
APPLICATION_SERVICE_URL=http://localhost:8002
EMAIL_INTELLIGENCE_SERVICE_URL=http://localhost:8004
API_GATEWAY_URL=http://localhost:8000

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:5173

# Database URLs (defaults to SQLite - change for production)
DATABASE_URL=sqlite:///./app.db
`;
      fs.writeFileSync(envFile, envContent);
      log(`✅ Created .env file`, 'green');
      log(`⚠️  Please edit .env and add your Google OAuth credentials`, 'yellow');
    }
  } else {
    log(`ℹ️  .env file already exists`, 'blue');
  }
}

function setupService(serviceName) {
  const servicePath = path.join(PROJECT_ROOT, 'services', serviceName);
  
  if (!fs.existsSync(servicePath)) {
    log(`⚠️  Service directory not found: ${serviceName}`, 'yellow');
    return false;
  }
  
  const venvPath = path.join(servicePath, 'venv');
  const requirementsPath = path.join(servicePath, 'requirements.txt');
  const pythonCmd = getPythonCommand();
  
  if (!pythonCmd) {
    log(`❌ Python not found. Please install Python 3.8+`, 'red');
    return false;
  }
  
  // Create virtual environment if it doesn't exist
  if (!fs.existsSync(venvPath)) {
    log(`📦 Creating virtual environment for ${serviceName}...`, 'blue');
    try {
      execSync(`${pythonCmd} -m venv "${venvPath}"`, { stdio: 'inherit', cwd: servicePath });
      log(`✅ Virtual environment created for ${serviceName}`, 'green');
    } catch (e) {
      log(`❌ Failed to create virtual environment for ${serviceName}`, 'red');
      return false;
    }
  }
  
  // Install dependencies
  if (fs.existsSync(requirementsPath)) {
    log(`📦 Installing dependencies for ${serviceName}...`, 'blue');
    try {
      const pipCmd = isWindows 
        ? path.join(venvPath, 'Scripts', 'pip.exe')
        : path.join(venvPath, 'bin', 'pip');
      
      execSync(`"${pipCmd}" install --upgrade pip`, { stdio: 'inherit', cwd: servicePath });
      execSync(`"${pipCmd}" install -r requirements.txt`, { stdio: 'inherit', cwd: servicePath });
      log(`✅ Dependencies installed for ${serviceName}`, 'green');
    } catch (e) {
      log(`❌ Failed to install dependencies for ${serviceName}`, 'red');
      return false;
    }
  }
  
  return true;
}

function setupFrontend() {
  const frontendPath = path.join(PROJECT_ROOT, 'frontend');
  
  if (!fs.existsSync(frontendPath)) {
    log(`⚠️  Frontend directory not found`, 'yellow');
    return false;
  }
  
  log(`📦 Installing frontend dependencies...`, 'blue');
  try {
    execSync('npm install', { stdio: 'inherit', cwd: frontendPath });
    log(`✅ Frontend dependencies installed`, 'green');
    return true;
  } catch (e) {
    log(`❌ Failed to install frontend dependencies`, 'red');
    return false;
  }
}

function validateEnvironment() {
  logSection('Environment Validation');
  
  // Check Node.js
  const nodeVersion = getNodeVersion();
  if (nodeVersion) {
    log(`✅ Node.js: ${nodeVersion}`, 'green');
  } else {
    log(`❌ Node.js not found. Please install Node.js 18+`, 'red');
    return false;
  }
  
  // Check Python
  const pythonVersion = getPythonVersion();
  if (pythonVersion) {
    log(`✅ Python: ${pythonVersion}`, 'green');
  } else {
    log(`❌ Python not found. Please install Python 3.8+`, 'red');
    return false;
  }
  
  // Check OS
  log(`✅ OS: ${process.platform} (${os.type()})`, 'green');
  
  return true;
}

function validateEnvFile() {
  const envFile = path.join(PROJECT_ROOT, '.env');
  
  if (!fs.existsSync(envFile)) {
    log(`⚠️  .env file not found. Run setup again to create it.`, 'yellow');
    return false;
  }
  
  const envContent = fs.readFileSync(envFile, 'utf8');
  const requiredVars = [
    'GOOGLE_CLIENT_ID',
    'GOOGLE_CLIENT_SECRET',
  ];
  
  const missing = [];
  for (const varName of requiredVars) {
    const regex = new RegExp(`^${varName}=(.+)$`, 'm');
    const match = envContent.match(regex);
    if (!match || !match[1] || match[1].trim() === '') {
      missing.push(varName);
    }
  }
  
  if (missing.length > 0) {
    log(`⚠️  Missing required environment variables: ${missing.join(', ')}`, 'yellow');
    log(`   Please edit .env and add your Google OAuth credentials`, 'yellow');
    return false;
  }
  
  log(`✅ All required environment variables are set`, 'green');
  return true;
}

// Main setup function
function main() {
  logSection('Email Sync Job Dashboard - Cross-Platform Setup');
  
  log(`Platform: ${process.platform}`, 'blue');
  log(`Node.js: ${getNodeVersion() || 'Not found'}`, 'blue');
  log(`Python: ${getPythonVersion() || 'Not found'}`, 'blue');
  
  // Validate environment
  if (!validateEnvironment()) {
    process.exit(1);
  }
  
  // Create necessary directories
  logSection('Creating Directories');
  const dirsToCreate = [
    path.join(PROJECT_ROOT, 'services', 'application-service', 'uploads', 'resumes'),
  ];
  
  for (const dir of dirsToCreate) {
    ensureDirectory(dir);
  }
  
  // Copy .env.example to .env
  logSection('Environment Configuration');
  copyEnvExample();
  
  // Setup services
  logSection('Setting Up Backend Services');
  const services = [
    'api-gateway',
    'auth-service',
    'gmail-connector-service',
    'application-service',
    'email-intelligence-service',
    'notification-service',
  ];
  
  let allServicesOk = true;
  for (const service of services) {
    if (!setupService(service)) {
      allServicesOk = false;
    }
  }
  
  // Setup frontend
  logSection('Setting Up Frontend');
  setupFrontend();
  
  // Validate .env file
  logSection('Environment Validation');
  const envValid = validateEnvFile();
  
  // Summary
  logSection('Setup Complete');
  
  if (allServicesOk && envValid) {
    log('✅ Setup completed successfully!', 'green');
    log('\nNext steps:', 'cyan');
    log('1. Edit .env and add your Google OAuth credentials', 'yellow');
    log('2. Run: npm run dev (or use start scripts)', 'yellow');
    log('3. Open http://localhost:5173 in your browser', 'yellow');
  } else {
    log('⚠️  Setup completed with warnings', 'yellow');
    if (!envValid) {
      log('   Please configure your .env file before running the application', 'yellow');
    }
  }
  
  log('\nFor more information, see README.md', 'blue');
}

// Run setup
main();
