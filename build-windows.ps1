$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'Windows x64 빌드 PC에서 실행하세요.' }
# Python is required on the build computer only, never on the receiving user's PC.
& py -3.12 -m venv .build-venv
if ($LASTEXITCODE -ne 0) { throw '빌드 PC에 Python 3.12 x64가 필요합니다.' }
$BuildPython = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
& $BuildPython -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw '빌드 의존성 설치 실패' }
& $BuildPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw '검사 실패' }
& $BuildPython -m PyInstaller --noconfirm --clean --onedir --windowed --name EMSQuiz --collect-all pypdf --collect-all pypdfium2 --collect-all pypdfium2_raw --collect-all pdfplumber --collect-all pdfminer app.py
if ($LASTEXITCODE -ne 0) { throw '프로그램 빌드 실패' }
& (Join-Path $PSScriptRoot 'prepare-ocr.ps1')
$SmokeReport = Join-Path $PSScriptRoot 'dist\bundle-smoke.json'
New-Item -ItemType Directory -Force -Path 'dist\qa' | Out-Null
& $BuildPython -c "import sys; sys.path.insert(0,'tests'); from test_pdf_layout import textbook_fixture; textbook_fixture('dist/qa/layout-fixture.pdf')"
if ($LASTEXITCODE -ne 0) { throw '문단·박스·표 검사 PDF 준비 실패' }
if (Test-Path $SmokeReport) { Remove-Item $SmokeReport }
$Smoke = Start-Process -FilePath (Join-Path $PSScriptRoot 'dist\EMSQuiz\EMSQuiz.exe') -ArgumentList @('--self-test', ('"' + $SmokeReport + '"')) -PassThru
if (-not $Smoke.WaitForExit(180000)) { Stop-Process -Id $Smoke.Id -Force; throw '번들 검사 시간 초과' }
if (Test-Path $SmokeReport) { Get-Content $SmokeReport -Raw }
if ($Smoke.ExitCode -ne 0 -or -not (Test-Path $SmokeReport)) { throw '번들 실행 검사 실패' }
$SmokeResult = Get-Content $SmokeReport -Raw | ConvertFrom-Json
if (-not $SmokeResult.ok -or -not $SmokeResult.frozen) { throw 'Python 포함 번들 검사 실패' }
# Preserve dependency license metadata next to the program.
$LicenseDir = Join-Path $PSScriptRoot 'dist\EMSQuiz\licenses'
New-Item -ItemType Directory -Force -Path $LicenseDir | Out-Null
Copy-Item NOTICE.md $LicenseDir
$BasePython = & $BuildPython -c "import sys; print(sys.base_prefix)"
Get-ChildItem $BasePython -File -Filter 'LICENSE*' | Copy-Item -Destination $LicenseDir
$TclRoot = Join-Path $BasePython 'tcl'
if (Test-Path $TclRoot) {
    Get-ChildItem $TclRoot -Recurse -File | Where-Object { $_.Name -match '^(license|copying)(\.|$)' } | ForEach-Object {
        $RuntimeName = $_.Directory.Name + '-' + $_.Name
        Copy-Item $_.FullName (Join-Path $LicenseDir $RuntimeName)
    }
}
Get-ChildItem '.build-venv\Lib\site-packages' -Directory -Filter '*.dist-info' | ForEach-Object {
    $Target = Join-Path $LicenseDir $_.Name
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Get-ChildItem $_.FullName -File | Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE|METADATA)' } | Copy-Item -Destination $Target
    $Nested = Join-Path $_.FullName 'licenses'
    if (Test-Path $Nested) { Copy-Item $Nested $Target -Recurse -Force }
}
$CompilerCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$Compiler = if ($CompilerCommand) { $CompilerCommand.Source } else { $null }
if (-not $Compiler) {
    $Candidate = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
    if (Test-Path $Candidate) { $Compiler = $Candidate }
}
if (-not $Compiler) { throw '프로그램 폴더 빌드 완료. 설치 EXE 생성에는 빌드 PC에 Inno Setup 6가 필요합니다.' }
& $Compiler installer.iss
if ($LASTEXITCODE -ne 0) { throw '설치 파일 생성 실패' }
# Verify the installed copy with a PATH that cannot locate the builder's Python.
$InstalledDir = Join-Path $env:TEMP 'EMSQuiz-installed-test'
$Install = Start-Process -FilePath (Join-Path $PSScriptRoot 'release\EMSQuiz-Setup-0.6.1.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART', ('/DIR="' + $InstalledDir + '"')) -Wait -PassThru
if ($Install.ExitCode -ne 0) { throw '설치 시험 실패' }
$OldPath = $env:PATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $Report = Join-Path $PSScriptRoot 'dist\installed-smoke.json'
    $Installed = Start-Process -FilePath (Join-Path $InstalledDir 'EMSQuiz.exe') -ArgumentList @('--self-test', ('"' + $Report + '"')) -PassThru
    if (-not $Installed.WaitForExit(180000)) { Stop-Process -Id $Installed.Id -Force; throw '설치된 EXE 검사 시간 초과' }
    if (Test-Path $Report) { Get-Content $Report -Raw }
    if ($Installed.ExitCode -ne 0 -or -not (Test-Path $Report)) { throw '설치된 EXE 실행 시험 실패' }
} finally { $env:PATH = $OldPath }
$Uninstall = Start-Process -FilePath (Join-Path $InstalledDir 'unins000.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
if ($Uninstall.ExitCode -ne 0) { throw '제거 시험 실패' }

Write-Host '설치 파일: release\EMSQuiz-Setup-0.6.1.exe'
