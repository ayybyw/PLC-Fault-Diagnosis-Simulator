"""PLC 故障诊断模拟平台 · 桌面版外壳

原程序（PLC故障诊断平台.exe）采用 Flask + 系统浏览器方案：
启动本地服务后调用 webbrowser 打开 http://127.0.0.1:5000。

本外壳复用原程序完全相同的后端模块（runtime/app.marshal）与前端资源
（templates / static），把页面承载在独立的桌面窗口中（Edge WebView2），
不再弹出浏览器标签页，也没有黑色控制台窗口。原 exe 不做任何改动。

运行链路：单实例检查 -> 启动内嵌 Flask 服务 -> 选空闲端口 -> 等待就绪
-> 打开原生窗口（深色标题栏、居中、记忆尺寸）-> 关窗即停服务退出。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import marshal
import os
import socket
import sys
import threading
import time
import types

APP_TITLE = "PLC 故障诊断模拟平台"
HOST = "127.0.0.1"
PREFERRED_PORT = 5000
WINDOW_SIZE = (1320, 830)
MIN_SIZE = (1000, 660)
MUTEX_NAME = "Local\\PLCDiagnosisDesktop_SingleInstance"


# ---------------------------------------------------------------- 路径与配置
def base_dir() -> str:
    """打包后返回资源解包目录；开发模式返回脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def state_dir() -> str:
    path = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "PLC故障诊断平台"
    )
    os.makedirs(path, exist_ok=True)
    return path


def load_window_state() -> dict:
    try:
        with open(os.path.join(state_dir(), "window.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_window_state(data: dict) -> None:
    try:
        with open(os.path.join(state_dir(), "window.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


# ---------------------------------------------------------------- 后端加载
def load_flask_app(base: str):
    """优先加载可编辑的 app.py；它出问题时回退到内嵌的原始字节码。

    app.py 就是原程序后端逻辑的源码还原，改文案、加故障都在那里改。
    """
    if base not in sys.path:
        sys.path.insert(0, base)
    try:
        import app as app_module  # noqa: F401 - 源码版后端

        return app_module.app
    except Exception:
        pass

    path = os.path.join(base, "runtime", "app.marshal")
    if not os.path.exists(path):
        raise FileNotFoundError("缺少后端模块：app.py 不可用，且 runtime/app.marshal 不存在")
    with open(path, "rb") as f:
        code = marshal.loads(f.read())

    module = types.ModuleType("app")
    module.__file__ = os.path.join(base, "app.py")
    module.__package__ = ""
    sys.modules["app"] = module
    exec(code, module.__dict__)  # noqa: S102 - 原程序逻辑，原样复用
    return module.app


def pick_port(preferred: int = PREFERRED_PORT) -> int:
    """优先沿用原程序的 5000，被占用则交给系统分配空闲端口。"""
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((HOST, port))
            except OSError:
                continue
            return int(s.getsockname()[1])
    raise RuntimeError("无法分配本地端口")


def port_ready(port: int, timeout: float = 0.2) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((HOST, port)) == 0


def start_server(app, port: int):
    from werkzeug.serving import make_server

    server = make_server(HOST, port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, name="flask-server", daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------- 窗口外观
user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

# 必须声明参数/返回类型：64 位下 HWND 若按 c_int 传递会被截断，调用静默失败
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wt.UINT]
user32.SetWindowPos.restype = wt.BOOL
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowRect.restype = wt.BOOL
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL
user32.IsZoomed.argtypes = [wt.HWND]
user32.IsZoomed.restype = wt.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
dwmapi.DwmSetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

try:
    user32.GetDpiForWindow.argtypes = [wt.HWND]
    user32.GetDpiForWindow.restype = wt.UINT
except AttributeError:
    pass


def find_hwnd(title: str, timeout: float = 8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
        time.sleep(0.05)
    return None


def apply_dark_titlebar(hwnd) -> None:
    """Windows 10/11 深色标题栏，与页面深色主题统一。"""
    if not hwnd:
        return
    value = ctypes.c_int(1)
    for attr in (20, 19):
        if dwmapi.DwmSetWindowAttribute(
            hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
        ) == 0:
            break
    # 顺手把标题栏文字刷成浅色
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0027)


def ensure_dark_titlebar(hwnd, timeout: float = 5.0) -> None:
    """窗口刚创建时 DWM 会忽略这个设置，需要重试到生效为止。"""
    if not hwnd:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        apply_dark_titlebar(hwnd)
        current = ctypes.c_int(0)
        if (
            dwmapi.DwmGetWindowAttribute(hwnd, 20, ctypes.byref(current), 4) == 0
            and current.value == 1
        ):
            return
        time.sleep(0.1)


def center_window(hwnd) -> None:
    if not hwnd:
        return
    rect = wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return
    w, h = rect.right - rect.left, rect.bottom - rect.top
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 3)
    user32.SetWindowPos(hwnd, None, x, y, 0, 0, 0x0001 | 0x0004)


def window_rect(hwnd) -> dict | None:
    if not hwnd:
        return None
    rect = wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return {
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
        "x": rect.left,
        "y": rect.top,
    }


def dpi_scale(hwnd) -> float:
    """GetWindowRect 返回物理像素，而 create_window 接收逻辑像素，需换算。"""
    try:
        dpi = user32.GetDpiForWindow(hwnd)
        if dpi:
            return dpi / 96.0
    except Exception:
        pass
    return 1.0


def snapshot_window(hwnd) -> dict:
    """记录窗口尺寸（换算成逻辑像素）与最大化状态。"""
    state: dict = {}
    if not hwnd:
        return state
    state["maximized"] = bool(user32.IsZoomed(hwnd))
    rect = window_rect(hwnd)
    if rect and not state["maximized"]:
        scale = dpi_scale(hwnd)
        state["width"] = int(round(rect["width"] / scale))
        state["height"] = int(round(rect["height"] / scale))
    else:
        saved = load_window_state()
        if saved.get("width"):
            state["width"] = int(saved["width"])
        if saved.get("height"):
            state["height"] = int(saved["height"])
    return state


# ---------------------------------------------------------------- 单实例
def acquire_single_instance():
    """返回 (mutex_handle, is_first)。已存在实例时把旧窗口提到前台。"""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wt.HANDLE
    kernel32.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
    ctypes.set_last_error(0)  # 成功创建新对象时 LastError 不会被清零，必须先复位
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    already = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    if already:
        hwnd = user32.FindWindowW(None, APP_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
    return handle, not already


# ---------------------------------------------------------------- 兜底与提示
def fatal(message: str) -> None:
    try:
        user32.MessageBoxW(None, message, APP_TITLE, 0x10)
    except Exception:
        print(message, file=sys.stderr)


def open_fallback_window(url: str) -> None:
    """WebView2 不可用时的降级方案：用 Edge 的 --app 模式开独立窗口。"""
    import subprocess

    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for exe in candidates:
        if os.path.exists(exe):
            subprocess.Popen(
                [
                    exe,
                    f"--app={url}",
                    f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ]
            )
            return
    raise RuntimeError("未找到可用的 WebView2 运行时或 Edge 浏览器")


# ---------------------------------------------------------------- 主流程
def main() -> int:
    mutex, first = acquire_single_instance()
    if not first:
        return 0

    base = base_dir()
    try:
        app = load_flask_app(base)
    except Exception as exc:  # pragma: no cover
        fatal(f"加载诊断平台后端失败：\n{exc}")
        return 1

    try:
        port = pick_port()
        server = start_server(app, port)
    except Exception as exc:  # pragma: no cover
        fatal(f"启动本地服务失败：\n{exc}")
        return 1

    deadline = time.time() + 15
    while time.time() < deadline and not port_ready(port):
        time.sleep(0.05)

    url = f"http://{HOST}:{port}/"
    if not port_ready(port):
        server.shutdown()
        fatal("服务启动后仍无法访问，请重试。")
        return 1

    try:
        import webview
    except Exception:
        webview = None

    if webview is None:
        try:
            open_fallback_window(url)
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
        return 0

    saved = load_window_state()
    screen_w, screen_h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    default_w = min(WINDOW_SIZE[0], int(screen_w * 0.9))
    default_h = min(WINDOW_SIZE[1], int(screen_h * 0.86))
    width = int(saved.get("width") or default_w)
    height = int(saved.get("height") or default_h)
    width = max(MIN_SIZE[0], min(width, max(MIN_SIZE[0], screen_w)))
    height = max(MIN_SIZE[1], min(height, max(MIN_SIZE[1], screen_h)))

    window = webview.create_window(
        APP_TITLE,
        url,
        width=width,
        height=height,
        min_size=MIN_SIZE,
        text_select=True,
        confirm_close=False,
        background_color="#0d141d",
    )

    def style_window() -> None:
        """等窗口出现后再设置深色标题栏和居中，避开启动时的时序竞争。"""
        hwnd = find_hwnd(APP_TITLE)
        if not hwnd:
            return
        center_window(hwnd)
        ensure_dark_titlebar(hwnd)
        if saved.get("maximized"):
            user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
        window.events.closing += lambda: save_window_state(snapshot_window(hwnd))

    def on_ready() -> None:
        threading.Thread(target=style_window, daemon=True).start()

    try:
        webview.start(on_ready, debug=False)
    except Exception as exc:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            open_fallback_window(url)
            while True:
                time.sleep(0.5)
        except Exception:
            fatal(f"无法创建桌面窗口：\n{exc}")
            return 1
    finally:
        try:
            server.shutdown()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
