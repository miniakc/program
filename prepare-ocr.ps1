$ErrorActionPreference = 'Stop'
$OcrTemp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$InstallDir = Join-Path $OcrTemp 'ems-tesseract'
$Download = Join-Path $env:TEMP 'ems-tesseract-5.5.3.exe'
$Url = 'https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe'
Invoke-WebRequest $Url -OutFile $Download
$Expected = 'BEE9E3434BD94FD65387D9BE28CD467A41F61B1275383B55B0F59A1331270AE4'
if ((Get-FileHash $Download -Algorithm SHA256).Hash -ne $Expected) { throw 'OCR 설치 패키지 SHA256 불일치' }
$Process = Start-Process -FilePath $Download -ArgumentList @('/S', "/D=$InstallDir") -Wait -PassThru
if ($Process.ExitCode -ne 0) { throw "OCR 준비 실패: $($Process.ExitCode)" }
if (-not (Test-Path (Join-Path $InstallDir 'tesseract.exe'))) { throw 'OCR 실행 파일 없음' }
$Dest = Join-Path $PSScriptRoot 'dist\EMSQuiz\ocr'
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item (Join-Path $InstallDir '*') $Dest -Recurse -Force
# Source-pinned official language data, bundled before distribution; no runtime model download.
foreach ($Language in @('kor','eng')) {
    Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/$Language.traineddata" -OutFile (Join-Path $Dest "tessdata\$Language.traineddata")
}
Invoke-WebRequest 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/LICENSE' -OutFile (Join-Path $Dest 'TESSDATA-LICENSE')
& (Join-Path $Dest 'tesseract.exe') --list-langs --tessdata-dir (Join-Path $Dest 'tessdata')
if ($LASTEXITCODE -ne 0) { throw 'OCR 언어 데이터 로드 실패' }
