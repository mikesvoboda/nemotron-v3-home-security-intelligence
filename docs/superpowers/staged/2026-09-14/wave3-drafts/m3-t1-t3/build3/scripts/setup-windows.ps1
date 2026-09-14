# Setup Windows Task Scheduler for Home Security Intelligence containers
# This script creates scheduled tasks for auto-start on boot
#
# Usage: Run as Administrator
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
#
# Requirements:
# - Windows 10/11 with Podman Desktop or WSL2 + Podman
# - Administrator privileges
# - Containers already running

param(
    [switch]$Uninstall,
    [switch]$Help
)

# Colors
$Green = "Green"
$Red = "Red"
$Yellow = "Yellow"

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Show-Help {
    Write-Host @"
Home Security Intelligence - Windows Task Scheduler Setup

Usage:
    .\setup-windows.ps1           # Install scheduled tasks
    .\setup-windows.ps1 -Uninstall # Remove scheduled tasks
    .\setup-windows.ps1 -Help      # Show this help

Requirements:
    - Run as Administrator
    - Podman Desktop or WSL2 + Podman installed
    - Containers already running

This script creates Windows Scheduled Tasks to auto-start
all Home Security Intelligence containers on system boot.
"@
}

if ($Help) {
    Show-Help
    exit 0
}

Write-ColorOutput "Home Security Intelligence - Windows Setup" $Green
Write-Host "============================================="

# Check if running as Administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-ColorOutput "Error: This script must be run as Administrator" $Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'"
    exit 1
}

# Find podman executable
$podmanPath = $null
$possiblePaths = @(
    "C:\Program Files\RedHat\Podman\podman.exe",
    "C:\Program Files\Podman\podman.exe",
    "$env:LOCALAPPDATA\Programs\Podman\podman.exe",
    (Get-Command podman -ErrorAction SilentlyContinue).Source
)

foreach ($path in $possiblePaths) {
    if ($path -and (Test-Path $path)) {
        $podmanPath = $path
        break
    }
}

if (-not $podmanPath) {
    Write-ColorOutput "Error: podman not found. Please install Podman Desktop." $Red
    Write-Host "Download from: https://podman-desktop.io/"
    exit 1
}

Write-Host "Found podman at: $podmanPath"

# Task name prefix
$taskPrefix = "HomeSecurityIntelligence"

if ($Uninstall) {
    Write-Host ""
    Write-Host "Removing scheduled tasks..."

    $tasks = Get-ScheduledTask | Where-Object { $_.TaskName -like "$taskPrefix*" }
    foreach ($task in $tasks) {
        try {
            Unregister-ScheduledTask -TaskName $task.TaskName -Confirm:$false
            Write-ColorOutput "  - Removed: $($task.TaskName)" $Green
        } catch {
            Write-ColorOutput "  - Failed to remove: $($task.TaskName)" $Red
        }
    }

    Write-Host ""
    Write-ColorOutput "Uninstall complete!" $Green
    exit 0
}

# Get running containers
Write-Host ""
Write-Host "Detecting running containers..."

try {
    $containersRaw = & $podmanPath ps --format "{{.Names}}" 2>&1
    $containers = $containersRaw | Where-Object { $_ -like "nemotron-v3-home-security-intelligence*" }
} catch {
    Write-ColorOutput "Error: Failed to list containers" $Red
    exit 1
}

if (-not $containers -or $containers.Count -eq 0) {
    Write-ColorOutput "No running containers found." $Yellow
    Write-Host "Please start containers first with:"
    Write-Host "  podman-compose -f docker-compose.prod.yml up -d"
    exit 1
}

Write-Host "Found $($containers.Count) containers"

# Create scheduled tasks
Write-Host ""
Write-Host "Creating scheduled tasks..."

$created = 0
foreach ($container in $containers) {
    $taskName = "$taskPrefix`_$($container -replace 'nemotron-v3-home-security-intelligence_', '')"

    # Remove existing task if present
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    try {
        # Create action - start the container
        $action = New-ScheduledTaskAction -Execute $podmanPath -Argument "start $container"

        # Trigger at system startup
        $trigger = New-ScheduledTaskTrigger -AtStartup

        # Settings
        $settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 1)

        # Principal - run as SYSTEM for startup tasks
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

        # Register task
        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Description "Auto-start Home Security Intelligence container: $container" | Out-Null

        Write-ColorOutput "  - $taskName : OK" $Green
        $created++
    } catch {
        Write-ColorOutput "  - $taskName : FAILED - $_" $Red
    }
}

# Create frontend dependency task (waits for backend)
Write-Host ""
Write-Host "Creating frontend dependency task..."

$frontendContainer = $containers | Where-Object { $_ -like "*frontend*" }
$backendContainer = $containers | Where-Object { $_ -like "*backend*" }

if ($frontendContainer -and $backendContainer) {
    $depTaskName = "$taskPrefix`_frontend_after_backend"

    # Remove existing
    $existingTask = Get-ScheduledTask -TaskName $depTaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $depTaskName -Confirm:$false
    }

    # Create a script that waits for backend then restarts frontend
    $scriptContent = @"
# Wait for backend to be healthy, then restart frontend
`$maxWait = 120
`$waited = 0
while (`$waited -lt `$maxWait) {
    `$health = & '$podmanPath' inspect $backendContainer --format '{{.State.Health.Status}}' 2>`$null
    if (`$health -eq 'healthy') {
        & '$podmanPath' restart $frontendContainer
        exit 0
    }
    Start-Sleep -Seconds 5
    `$waited += 5
}
& '$podmanPath' restart $frontendContainer
"@

    $scriptPath = "$env:ProgramData\HomeSecurityIntelligence\restart-frontend.ps1"
    $scriptDir = Split-Path $scriptPath -Parent

    if (-not (Test-Path $scriptDir)) {
        New-Item -ItemType Directory -Path $scriptDir -Force | Out-Null
    }

    $scriptContent | Out-File -FilePath $scriptPath -Encoding UTF8 -Force

    try {
        $action = New-ScheduledTaskAction `
            -Execute "powershell.exe" `
            -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""

        # Trigger 30 seconds after startup (give backend time to start)
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $trigger.Delay = "PT30S"

        $settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable

        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

        Register-ScheduledTask `
            -TaskName $depTaskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Description "Restart frontend after backend is healthy" | Out-Null

        Write-ColorOutput "  - Frontend dependency task: OK" $Green
    } catch {
        Write-ColorOutput "  - Frontend dependency task: FAILED - $_" $Red
    }
}

# Summary
Write-Host ""
Write-Host "============================================="
Write-ColorOutput "Setup Complete!" $Green
Write-Host ""
Write-Host "Created $created scheduled tasks."
Write-Host "Services will start automatically on system boot."
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  # View all tasks"
Write-Host "  Get-ScheduledTask | Where-Object { `$_.TaskName -like 'HomeSecurityIntelligence*' }"
Write-Host ""
Write-Host "  # Run a task manually"
Write-Host "  Start-ScheduledTask -TaskName 'HomeSecurityIntelligence_backend_1'"
Write-Host ""
Write-Host "  # Disable a task"
Write-Host "  Disable-ScheduledTask -TaskName 'HomeSecurityIntelligence_backend_1'"
Write-Host ""
Write-Host "  # Remove all tasks"
Write-Host "  .\setup-windows.ps1 -Uninstall"
