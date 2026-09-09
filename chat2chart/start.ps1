param(
  [int]$Port = 8787
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$venv = Join-Path $here '.venv'
$pyExe = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pyExe)) {
  Write-Host "创建虚拟环境 .venv（优先使用 Python 3.11，与 akshare 兼容性最好）..."
  & py -3.11 -m venv $venv
  if (-not (Test-Path -LiteralPath $pyExe)) { throw '创建 venv 失败，请确认已安装 Python 3.11（py -3.11）' }
}

Write-Host "安装后端依赖..."
& $pyExe -m pip install -r (Join-Path $here 'backend\requirements.txt')

if (Test-Path -LiteralPath (Join-Path $here '.env')) {
  Write-Host "检测到 .env（未安装则复制 .env.example 为 .env）"
}

$env:C2C_PORT = "$Port"
Push-Location (Join-Path $here 'backend')
try {
  Write-Host "启动 chat2chart:  http://localhost:$Port  （需确保已安装 opencode CLI 且已登录模型）"
  # 注意：不要加 --reload —— 在 Windows 上 uvicorn 的 --reload 会把事件循环切换成 SelectorEventLoop，
  # 它不支持 asyncio 子进程（会抛 NotImplementedError），导致 opencode / 渲染无法启动。
  & $pyExe -m uvicorn main:app --host 127.0.0.1 --port $Port
}
finally { Pop-Location }
