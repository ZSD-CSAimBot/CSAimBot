if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Script did not receive Administrator privileges from the installer!" -ForegroundColor Red
    Write-Host "Installation cannot continue." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    exit 1
}

Write-Host "=== Checking Environment ===" -ForegroundColor Cyan
Write-Host "`n[1/4] Checking WSL and Ubuntu..." -ForegroundColor Yellow

wsl.exe -d Ubuntu -e true 2>$null
$ubuntuInstalled = ($LASTEXITCODE -eq 0)

if (-not $ubuntuInstalled) {
    Write-Host "ERROR: Ubuntu distribution not found. Starting installation..." -ForegroundColor Cyan
    wsl.exe --install -d Ubuntu
    
    Write-Host "`nNOTICE: WSL installation has been initiated." -ForegroundColor Green
    Write-Host "You may need to restart your computer." -ForegroundColor Red
    Write-Host "After restarting and setting a password in Ubuntu, please run the installer again." -ForegroundColor Red
    Start-Sleep -Seconds 5
    exit 1
} else {
    Write-Host "WSL and Ubuntu are already installed and working correctly." -ForegroundColor Green
}

Write-Host "`n[2/4] Checking Docker inside Ubuntu..." -ForegroundColor Yellow

wsl.exe -d Ubuntu -- bash -c "command -v docker" > $null 2>&1
$dockerInstalled = ($LASTEXITCODE -eq 0)

if (-not $dockerInstalled) {
    Write-Host "ERROR: Docker not found in Ubuntu. Starting installation..." -ForegroundColor Cyan
    
    $wslUser = wsl.exe -d Ubuntu -- bash -c "echo `$USER"
    $wslUser = $wslUser.Trim()

    wsl.exe -d Ubuntu -u root -- bash -c "apt-get update"
    wsl.exe -d Ubuntu -u root -- bash -c "curl -fsSL https://get.docker.com -o get-docker.sh"
    wsl.exe -d Ubuntu -u root -- bash -c "sh get-docker.sh"
    wsl.exe -d Ubuntu -u root -- bash -c "usermod -aG docker $wslUser"
    
    Write-Host "Docker has been successfully installed!" -ForegroundColor Green
} else {
    $dockerVersion = wsl.exe -d Ubuntu -- bash -c "docker --version"
    Write-Host "Docker is already installed: $dockerVersion" -ForegroundColor Green
}

Write-Host "`n[3/4] Checking NVIDIA Container Toolkit inside Ubuntu..." -ForegroundColor Yellow

wsl.exe -d Ubuntu -- bash -c "command -v nvidia-ctk" > $null 2>&1
$nvidiaCtkInstalled = ($LASTEXITCODE -eq 0)

if (-not $nvidiaCtkInstalled) {
    Write-Host "ERROR: NVIDIA Container Toolkit not found in Ubuntu. Starting installation..." -ForegroundColor Cyan

    wsl.exe -d Ubuntu -u root -- bash -c "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg --yes"
    wsl.exe -d Ubuntu -u root -- bash -c "curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list"
    wsl.exe -d Ubuntu -u root -- bash -c "apt-get update"
    wsl.exe -d Ubuntu -u root -- bash -c "apt-get install -y nvidia-container-toolkit"
    wsl.exe -d Ubuntu -u root -- bash -c "nvidia-ctk runtime configure --runtime=docker"
    wsl.exe -d Ubuntu -u root -- bash -c "service docker restart"
    
    Write-Host "NVIDIA Container Toolkit has been successfully installed and configured!" -ForegroundColor Green
} else {
    Write-Host "NVIDIA Container Toolkit is already installed and configured." -ForegroundColor Green
}

Write-Host "`n[4/4] Checking native CUDA Toolkit 12.8 for Windows..." -ForegroundColor Yellow

$cuda128Path = $env:CUDA_PATH_V12_8
$nvccExists = Get-Command nvcc -ErrorAction SilentlyContinue
$isCuda128 = $false

if ($cuda128Path -and (Test-Path $cuda128Path)) {
    $isCuda128 = $true
} elseif ($nvccExists) {
    $nvccOutput = nvcc --version | Out-String
    if ($nvccOutput -match "release 12.8") {
        $isCuda128 = $true
    }
}

if ($isCuda128) {
    Write-Host "CUDA Toolkit 12.8 is already installed in Windows." -ForegroundColor Green
} else {
    Write-Host "Native CUDA Toolkit 12.8 not found in Windows. Starting download..." -ForegroundColor Cyan
    
    $cudaUrl = "https://developer.download.nvidia.com/compute/cuda/12.8.0/network_installers/cuda_12.8.0_windows_network.exe"
    $installerPath = "$env:TEMP\cuda_12.8_network_installer.exe"
    
    Invoke-WebRequest -Uri $cudaUrl -OutFile $installerPath
    
    Write-Host "Starting silent installation of CUDA Toolkit 12.8." -ForegroundColor Yellow
    Write-Host "Depending on your connection and disk speed, this may take several minutes. Please wait..." -ForegroundColor Yellow

    Start-Process -FilePath $installerPath -ArgumentList "-s" -Wait -NoNewWindow
    
    Write-Host "Silent installation of native CUDA Toolkit 12.8 in Windows has been completed!" -ForegroundColor Green
}

Write-Host "`n=== Environment setup completed successfully! ===" -ForegroundColor Cyan
Start-Sleep -Seconds 5
exit 0