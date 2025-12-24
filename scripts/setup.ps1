#
# Development Environment Setup Script (Windows PowerShell)
# For Nemotron v3 Home Security Intelligence Dashboard
#
# This script automates the setup of the development environment including:
# - Prerequisite checks (Python, Node.js)
# - Backend setup (virtualenv, dependencies, database)
# - Frontend setup (npm dependencies)
# - Pre-commit hooks installation
#
# Usage:
#   .\scripts\setup.ps1              # Full setup
#   .\scripts\setup.ps1 -Help        # Show help
#   .\scripts\setup.ps1 -SkipGpu     # Skip GPU checks
#

param(
    [switch]$Help,
    [switch]$SkipGpu,
    [switch]$SkipTests,
    [switch]$Clean
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

# Required versions
$RequiredPythonMajor = 3
$RequiredPythonMinor = 11
$RequiredNodeMajor = 18

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

function Print-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "===================================================================" -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host "===================================================================" -ForegroundColor Blue
    Write-Host ""
}

function Print-Step {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor Cyan
}

function Print-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Print-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Print-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Print-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Magenta
}

function Show-Help {
    Write-Host @"
Development Environment Setup Script (Windows)

Usage:
    .\scripts\setup.ps1 [OPTIONS]

Options:
    -Help           Show this help message
    -SkipGpu        Skip GPU/NVIDIA driver checks
    -SkipTests      Skip verification tests
    -Clean          Clean existing setup before reinstalling

Examples:
    .\scripts\setup.ps1                  # Full setup with all checks
    .\scripts\setup.ps1 -SkipGpu         # Setup without GPU requirements
    .\scripts\setup.ps1 -Clean           # Clean and reinstall everything

"@
    exit 0
}

function Test-Command {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# ─────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ─────────────────────────────────────────────────────────────────────────────

if ($Help) {
    Show-Help
}

if ($Clean) {
    Print-Warning "Cleaning existing setup..."
    if (Test-Path "$ProjectRoot\.venv") {
        Remove-Item -Recurse -Force "$ProjectRoot\.venv"
    }
    if (Test-Path "$ProjectRoot\frontend\node_modules") {
        Remove-Item -Recurse -Force "$ProjectRoot\frontend\node_modules"
    }
    if (Test-Path "$ProjectRoot\data\security.db") {
        Remove-Item -Force "$ProjectRoot\data\security.db"
    }
    Print-Success "Cleanup complete"
}

# ─────────────────────────────────────────────────────────────────────────────
# Start Setup
# ─────────────────────────────────────────────────────────────────────────────

Print-Header "Nemotron v3 Home Security Intelligence - Development Setup"

Write-Host "Project root: " -NoNewline
Write-Host $ProjectRoot -ForegroundColor Cyan
Write-Host ""

Set-Location $ProjectRoot

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Check Prerequisites
# ─────────────────────────────────────────────────────────────────────────────

Print-Header "Step 1: Checking Prerequisites"

# Check Python
Print-Step "Checking Python installation..."
if (Test-Command "python") {
    $PythonVersion = (python --version 2>&1) -replace 'Python ', ''
    $PythonParts = $PythonVersion.Split('.')
    $PythonMajor = [int]$PythonParts[0]
    $PythonMinor = [int]$PythonParts[1]

    if ($PythonMajor -ge $RequiredPythonMajor -and $PythonMinor -ge $RequiredPythonMinor) {
        Print-Success "Python $PythonVersion found"
    } else {
        Print-Error "Python $RequiredPythonMajor.$RequiredPythonMinor+ required, found $PythonVersion"
        exit 1
    }
} else {
    Print-Error "Python not found. Please install Python $RequiredPythonMajor.$RequiredPythonMinor+"
    Print-Info "Download from: https://www.python.org/downloads/"
    exit 1
}

# Check Node.js
Print-Step "Checking Node.js installation..."
if (Test-Command "node") {
    $NodeVersion = (node --version) -replace 'v', ''
    $NodeMajor = [int]($NodeVersion.Split('.')[0])

    if ($NodeMajor -ge $RequiredNodeMajor) {
        Print-Success "Node.js $NodeVersion found"
    } else {
        Print-Error "Node.js $RequiredNodeMajor+ required, found $NodeVersion"
        exit 1
    }
} else {
    Print-Error "Node.js not found. Please install Node.js $RequiredNodeMajor+"
    Print-Info "Download from: https://nodejs.org/"
    exit 1
}

# Check npm
Print-Step "Checking npm installation..."
if (Test-Command "npm") {
    $NpmVersion = npm --version
    Print-Success "npm $NpmVersion found"
} else {
    Print-Error "npm not found. Please install npm"
    exit 1
}

# Check git
Print-Step "Checking git installation..."
if (Test-Command "git") {
    $GitVersion = (git --version) -replace 'git version ', ''
    Print-Success "git $GitVersion found"
} else {
    Print-Error "git not found. Please install git"
    Print-Info "Download from: https://git-scm.com/download/win"
    exit 1
}

# Check Docker (optional)
Print-Step "Checking Docker installation (optional)..."
if (Test-Command "docker") {
    $DockerVersion = (docker --version) -replace 'Docker version ', '' -replace ',.*', ''
    Print-Success "Docker $DockerVersion found"
} else {
    Print-Warning "Docker not found (optional for development)"
}

# Check NVIDIA drivers (optional for GPU)
if (-not $SkipGpu) {
    Print-Step "Checking NVIDIA GPU support (optional)..."
    if (Test-Command "nvidia-smi") {
        try {
            $NvidiaInfo = nvidia-smi --query-gpu=driver_version,name --format=csv,noheader 2>&1
            if ($LASTEXITCODE -eq 0) {
                $DriverVersion = ($NvidiaInfo -split ',')[0].Trim()
                $GpuName = ($NvidiaInfo -split ',')[1].Trim()
                Print-Success "NVIDIA driver $DriverVersion found"
                Print-Info "GPU: $GpuName"
            } else {
                Print-Warning "nvidia-smi found but not working properly"
            }
        } catch {
            Print-Warning "Could not query NVIDIA GPU information"
        }
    } else {
        Print-Warning "nvidia-smi not found (GPU features will be limited)"
    }
} else {
    Print-Info "Skipping GPU checks (-SkipGpu flag)"
}

Print-Success "All required prerequisites are installed"

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Backend Setup
# ─────────────────────────────────────────────────────────────────────────────

Print-Header "Step 2: Setting Up Backend"

# Create virtual environment
Print-Step "Creating Python virtual environment..."
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Print-Success "Virtual environment created"
} else {
    Print-Info "Virtual environment already exists"
}

# Activate virtual environment
Print-Step "Activating virtual environment..."
$ActivateScript = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    & $ActivateScript
    Print-Success "Virtual environment activated"
} else {
    Print-Error "Could not find activation script at $ActivateScript"
    exit 1
}

# Upgrade pip
Print-Step "Upgrading pip..."
python -m pip install --upgrade pip --quiet
Print-Success "pip upgraded"

# Install backend dependencies
Print-Step "Installing backend dependencies..."
if (Test-Path "backend\requirements.txt") {
    pip install -r backend\requirements.txt --quiet
    Print-Success "Backend dependencies installed"
} else {
    Print-Error "backend\requirements.txt not found"
    exit 1
}

# Install development tools
Print-Step "Installing development tools (pre-commit, ruff, mypy)..."
pip install pre-commit ruff mypy --quiet
Print-Success "Development tools installed"

# Create .env file if it doesn't exist
Print-Step "Setting up environment configuration..."
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Print-Success ".env file created from .env.example"
        Print-Warning "Please review and update .env with your configuration"
    } else {
        Print-Warning ".env.example not found, skipping .env creation"
    }
} else {
    Print-Info ".env file already exists"
}

# Create data directory for database
Print-Step "Creating data directory..."
if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}
Print-Success "Data directory ready"

# Initialize database
Print-Step "Initializing database..."
if (Test-Path "backend\main.py") {
    Print-Info "Database will be initialized on first run"
    Print-Success "Database setup ready"
} else {
    Print-Warning "backend\main.py not found, skipping database initialization"
}

Print-Success "Backend setup complete"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Frontend Setup
# ─────────────────────────────────────────────────────────────────────────────

Print-Header "Step 3: Setting Up Frontend"

Set-Location "$ProjectRoot\frontend"

# Install frontend dependencies
Print-Step "Installing frontend dependencies..."
if (Test-Path "package.json") {
    npm install
    Print-Success "Frontend dependencies installed"
} else {
    Print-Error "frontend\package.json not found"
    exit 1
}

# Create frontend .env if needed
Print-Step "Checking frontend environment configuration..."
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Print-Success "Frontend .env file created"
    } else {
        Print-Info "No frontend .env.example found (may not be required)"
    }
} else {
    Print-Info "Frontend .env already exists"
}

Set-Location $ProjectRoot
Print-Success "Frontend setup complete"

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Pre-commit Hooks
# ─────────────────────────────────────────────────────────────────────────────

Print-Header "Step 4: Setting Up Pre-commit Hooks"

# Install pre-commit hooks
Print-Step "Installing pre-commit hooks..."
if (Test-Path ".pre-commit-config.yaml") {
    pre-commit install
    pre-commit install --hook-type commit-msg
    Print-Success "Pre-commit hooks installed"

    Print-Step "Pre-commit hooks will run on every commit to ensure code quality"
    Print-Info "Hooks include: ruff (linting), mypy (type checking), pytest (tests)"
} else {
    Print-Warning ".pre-commit-config.yaml not found, skipping pre-commit setup"
}

Print-Success "Pre-commit setup complete"

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Verification
# ─────────────────────────────────────────────────────────────────────────────

Print-Header "Step 5: Verifying Installation"

# Verify Python tools
Print-Step "Verifying Python tools..."

Write-Host "  ruff: " -NoNewline
if (Test-Command "ruff") {
    ruff --version
} else {
    python -m ruff --version
}

Write-Host "  mypy: " -NoNewline
try {
    python -m mypy --version
} catch {
    Write-Host "not found"
}

Write-Host "  pytest: " -NoNewline
try {
    $PytestVersion = (python -m pytest --version 2>&1) | Select-Object -First 1
    Write-Host $PytestVersion
} catch {
    Write-Host "not found"
}

Print-Success "Python tools verified"

# Verify Node.js tools
Print-Step "Verifying Node.js tools..."

Set-Location "$ProjectRoot\frontend"

Write-Host "  eslint: " -NoNewline
try {
    npx eslint --version
} catch {
    Write-Host "not found"
}

Write-Host "  prettier: " -NoNewline
try {
    npx prettier --version
} catch {
    Write-Host "not found"
}

Write-Host "  vitest: " -NoNewline
try {
    npx vitest --version
} catch {
    Write-Host "not found"
}

Write-Host "  typescript: " -NoNewline
try {
    npx tsc --version
} catch {
    Write-Host "not found"
}

Set-Location $ProjectRoot

Print-Success "Node.js tools verified"

# Run quick tests (optional)
if (-not $SkipTests) {
    Print-Step "Running quick verification tests..."

    # Test Python import
    try {
        $ImportTest = python -c "import fastapi, sqlalchemy, redis; print('Backend imports OK')" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Print-Success "Backend imports verified"
        } else {
            Print-Warning "Some backend imports failed (this may be normal for optional dependencies)"
        }
    } catch {
        Print-Warning "Could not verify backend imports"
    }

    # Test frontend TypeScript
    Set-Location "$ProjectRoot\frontend"
    try {
        npx tsc --noEmit 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Print-Success "Frontend TypeScript compilation verified"
        } else {
            Print-Warning "TypeScript compilation has errors (fix before running)"
        }
    } catch {
        Print-Warning "Could not verify TypeScript compilation"
    }

    Set-Location $ProjectRoot
} else {
    Print-Info "Skipping verification tests (-SkipTests flag)"
}

# ─────────────────────────────────────────────────────────────────────────────
# Setup Complete
# ─────────────────────────────────────────────────────────────────────────────

Print-Header "Setup Complete!"

Write-Host "Your development environment is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Review and update .env file with your configuration:"
Write-Host "     notepad .env" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Start the backend server:"
Write-Host "     .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "     cd backend" -ForegroundColor Yellow
Write-Host "     uvicorn main:app --reload" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Start the frontend development server (in another terminal):"
Write-Host "     cd frontend" -ForegroundColor Yellow
Write-Host "     npm run dev" -ForegroundColor Yellow
Write-Host ""
Write-Host "Available Commands:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend:"
Write-Host "    .\.venv\Scripts\Activate.ps1      Activate Python virtual environment" -ForegroundColor Yellow
Write-Host "    cd backend; pytest                Run backend tests" -ForegroundColor Yellow
Write-Host "    ruff check backend\               Run Python linting" -ForegroundColor Yellow
Write-Host "    mypy backend\                     Run type checking" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Frontend:"
Write-Host "    cd frontend; npm run dev          Start development server" -ForegroundColor Yellow
Write-Host "    cd frontend; npm test             Run frontend tests" -ForegroundColor Yellow
Write-Host "    cd frontend; npm run lint         Run ESLint" -ForegroundColor Yellow
Write-Host "    cd frontend; npm run build        Build for production" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Development:"
Write-Host "    pre-commit run --all-files        Run all pre-commit hooks" -ForegroundColor Yellow
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  - Project README: README.md"
Write-Host "  - Agent navigation: AGENTS.md files in each directory"
Write-Host "  - Roadmap: docs\ROADMAP.md"
Write-Host ""
Write-Host "Happy coding!" -ForegroundColor Green
Write-Host ""
