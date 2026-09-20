from copy import deepcopy

from flask import Flask, jsonify, render_template

app = Flask(__name__)

BASE_STATE = {
    "line_status": "运行中",
    "line_message": "输送线运行正常，等待工件。",
    "motor": "运行",
    "sensor": "正常",
    "temperature": 35,
    "runtime": 125,
    "alarm": "无",
    "io": {"X0": 1, "X1": 1, "Y0": 1, "M100": 1},
    "fault": None,
    "diagnosis": None,
}

# 四类故障的差异只体现在数据上（报警码、IO 位、原因与步骤清单），
# 处理逻辑完全一致，所以用配置化字典描述，新增故障只加配置、不用改代码。
FAULTS = {
    "sensor": {
        "name": "传感器断线",
        "alarm": "E101 · 入料传感器信号异常",
        "message": "检测信号丢失，输送线已停止以防止误动作。",
        "sensor": "断线",
        "io": {"X0": 0, "X1": 1, "Y0": 0, "M100": 1},
        "causes": ["传感器电缆断线或接头松动", "传感器供电 24VDC 异常", "输入模块 X0 通道损坏"],
        "steps": ["检查 X0 输入指示灯是否熄灭", "检查传感器接线端子及 24VDC 供电", "使用万用表测量传感器输出信号", "修复后确认 X0 信号恢复"],
    },
    "overload": {
        "name": "电机过载",
        "alarm": "E202 · 电机热继电器保护动作",
        "message": "电机保护动作，输送线无法启动。",
        "motor": "过载保护",
        "io": {"X0": 1, "X1": 1, "Y0": 0, "M100": 0},
        "causes": ["输送带卡料或机械阻力过大", "电机负载超过额定值", "热继电器整定值偏低或接线松动"],
        "steps": ["检查输送带和滚筒是否有卡料", "检查电机电流及热继电器状态", "确认 M100 电机保护反馈信号", "排除机械故障后复位热继电器"],
    },
    "emergency": {
        "name": "急停触发",
        "alarm": "E001 · 急停回路断开",
        "message": "急停触发，安全回路锁定，输送线无法启动。",
        "motor": "停止",
        "io": {"X0": 1, "X1": 0, "Y0": 0, "M100": 1},
        "causes": ["急停按钮被按下", "急停回路接线松动或断线", "安全继电器未复位"],
        "steps": ["检查现场急停按钮是否按下", "检查 X1 急停输入状态", "确认安全继电器已复位", "解除急停后执行启动确认"],
    },
    "communication": {
        "name": "通讯故障",
        "alarm": "E301 · PLC 与变频器通讯超时",
        "message": "变频器通讯中断，PLC 禁止输出启动命令。",
        "motor": "通讯中断",
        "io": {"X0": 1, "X1": 1, "Y0": 0, "M100": 1},
        "causes": ["通讯电缆松动、断线或屏蔽不良", "变频器掉电或通讯参数不匹配", "PLC 通讯模块异常"],
        "steps": ["检查 PLC 和变频器通讯指示灯", "检查通讯线缆与终端电阻", "核对站号、波特率和协议参数", "恢复通讯后确认故障代码清除"],
    },
}

# 单用户演示定位，设备状态直接放模块级变量；若要支持多人同时训练，这里需要改成按 session 隔离。
state = deepcopy(BASE_STATE)


def public_state():
    return state


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify(public_state())


@app.post("/api/fault/<fault_key>")
def simulate_fault(fault_key):
    if fault_key not in FAULTS:
        return jsonify({"error": "未知故障类型"}), 404

    fault = FAULTS[fault_key]
    # 先回到干净基线再叠加故障，否则上一次的故障字段会残留
    state.update(deepcopy(BASE_STATE))
    state.update({
        "line_status": "故障停机",
        "line_message": fault["message"],
        "fault": fault["name"],
        "alarm": fault["alarm"],
        "diagnosis": {"causes": fault["causes"], "steps": fault["steps"]},
    })
    for field in ("motor", "sensor"):
        if field in fault:
            state[field] = fault[field]
    state["io"] = fault["io"]
    return jsonify(public_state())


@app.post("/api/reset")
def reset():
    state.clear()
    state.update(deepcopy(BASE_STATE))
    return jsonify(public_state())


if __name__ == "__main__":
    app.run(debug=True)
