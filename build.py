"""一键打包为单文件 exe。

用法：python build.py（或双击 build.bat）
产出：dist/PLC故障诊断平台桌面版.exe
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

EXE_NAME = "PLC故障诊断平台桌面版"


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


venv_dir = os.path.join(ROOT, ".venv")
venv_py = os.path.join(venv_dir, "Scripts", "python.exe")
if not os.path.exists(venv_py):
    print("[1/3] 创建虚拟环境")
    run([sys.executable, "-m", "venv", venv_dir])

print("[2/3] 安装依赖")
run([venv_py, "-m", "pip", "install", "-q", "-r", "requirements.txt", "pyinstaller"])

print("[3/3] 打包")
args = [
    os.path.join(venv_dir, "Scripts", "pyinstaller.exe"),
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name",
    EXE_NAME,
    "--icon",
    "assets/app.ico",
]
for data in ("templates;templates", "static;static"):
    args += ["--add-data", data]
if os.path.exists(os.path.join(ROOT, "runtime", "app.marshal")):
    args += ["--add-data", "runtime/app.marshal;runtime"]

for mod in (
    "clr",
    "webview.platforms.edgechromium",
    "flask",
    "jinja2",
    "werkzeug",
    "markupsafe",
    "itsdangerous",
    "click",
    "app",
):
    args += ["--hidden-import", mod]

args += ["--collect-all", "webview", "app_main.py"]
run(args)

print(f"\n完成：dist/{EXE_NAME}.exe")
