function UpdatePath {
    # Update the system PATH variable
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::Machine)
    $env:Path += ";"
    $env:Path += [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::User)

    # Re-import the updated environment variables into the PowerShell session
    [Environment]::SetEnvironmentVariable("Path", $env:Path, [System.EnvironmentVariableTarget]::Process)

    # Verify if the PATH variable is updated
    Write-Host "System PATH variable has been updated."
}

# For the script to run, scripts must be allowed to run on the system
# If scripts are not allowed to run, run the following command in an elevated PowerShell session:
# Set-ExecutionPolicy Bypass -Scope Process

function PressAnyKeyToExit {
    Write-Host "Press any key to exit..."
    $null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit
}

# If our parent folder is called "jira-command-line", copy the script to %TEM% and run it from there, otherwise we'll get locking issues
if ($PSScriptRoot -eq "$env:USERPROFILE\jira-command-line") {
    Write-Host "Copying the script to %TEMP%..."
    $tempPath = [System.IO.Path]::Combine($env:TEMP, "install-lib.ps1")
    Copy-Item -Path $PSScriptRoot\install-lib.ps1 -Destination $tempPath -Force
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$tempPath`"" -Verb RunAs
    Exit
}

# If we're not running as an administrator, restart as an administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Exit
}

Write-Host "Checking if winget is available..." -NoNewline

$wingetPath = Get-Command -Name winget -ErrorAction SilentlyContinue
if (-not $wingetPath) {
    Write-Host "[Please install winget/App Installer and re-run]" -ForegroundColor Red
    $url = "https://www.microsoft.com/en-us/p/app-installer/9nblggh4nns1"
    Start-Process $url
    PressAnyKeyToExit
} else {
    Write-Host "[Ok]" -ForegroundColor Green
}

UpdatePath

# If the machine is having cert issues...  (Doesn't work on Win 11)
# Write-Host "Enabling BypassCertificatePinningForMicrosoftStore setting..."
# winget settings --enable BypassCertificatePinningForMicrosoftStore

# Fix an odd source error with win 11
Add-AppxPackage -Path https://cdn.winget.microsoft.com/cache/source.msix

Write-Host "Checking if Python 3.11 or higher is installed..."
winget install --id Python.Python.3.11 --source=winget --silent
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
    write-host "last exit code: $LASTEXITCODE"
    Write-Host "[Please install Python 3.11 or higher and re-run]" -ForegroundColor Red
    $url = "https://www.python.org/downloads/"
    Start-Process $url
    PressAnyKeyToExit
}

Write-Host "Installing git for Windows..."
winget install --id Git.Git --source=winget --silent
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
    Write-Host "[Please install Git for Windows and re-run]" -ForegroundColor Red
    $url = "https://git-scm.com/download/win"
    Start-Process $url
    PressAnyKeyToExit
}
$gitPath = "$env:PROGRAMFILES\Git\bin\git.exe"

UpdatePath

# Add %LOCALAPPDATA%\Programs\Python\Python311 to PATH of the current process
$pythonPath = "$env:LOCALAPPDATA\Programs\Python\Python311\PYTHON.EXE"
$pipPath = "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts\PIP.EXE"

# Upgrade pip
Write-Host "Upgrading pip..."
& $pipPath install --upgrade pip

# Install the pip packages jira, github, pygit 
Write-Host "Installing Python packages..."
& $pipPath install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org jira windows-curses gitpython pygithub ttkthemes sv-ttk
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Failed to install Python packages]" -ForegroundColor Red
    PressAnyKeyToExit
}

Write-Host "Cloning Jira repository..."
$repoPath = "$env:USERPROFILE\jira-command-line"
if (Test-Path $repoPath) {
    Write-Host "[Jira repository already exists]" -ForegroundColor Yellow
    Remove-Item -Recurse -Force $repoPath
}
Set-Location $env:USERPROFILE
& $gitPath clone -c http.sslVerify=false https://github.com/benstaniford/jira-command-line
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Failed to clone Jira repository]" -ForegroundColor Red
    PressAnyKeyToExit
}

# Create a shortcut to the Jira script in the user's desktop
Write-Host "Creating a shortcut to the Jira script..."
$shortcutPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "Jira.lnk")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$pythonPath"
$shortcut.Arguments = "$repoPath\jira"
$shortcut.Save()

# Create a shortcut to the xray-ui script in the user's desktop, use the icon xray.ico
Write-Host "Creating a shortcut to the Xray UI script..."
$shortcutPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "Xray UI.lnk")
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$pythonPath"
$shortcut.Arguments = "$repoPath\xray-ui"
$shortcut.IconLocation = "$repoPath\xray.ico"
$shortcut.WindowStyle = 7
$shortcut.Save()

# Create a shortcut to %USERPROFILE%\.jira\config.json in the user's desktop
Write-Host "Creating a shortcut to the Jira configuration file..."
$shortcutPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "Jira Configuration.lnk")
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$env:SYSTEMROOT\System32\notepad.exe"
$shortcut.Arguments = "$env:USERPROFILE\.jira-config\config.json"
$shortcut.Save()

Write-Host "Jira has been installed successfully" -ForegroundColor Green
Write-Host "Please now run the Jira shortcut to generate a config template, and add API keys to the config file via the desktop shortcut" -ForegroundColor Yellow

PressAnyKeyToExit
