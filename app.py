"""PLC 故障诊断模拟平台 · 后端（源码版）

与原 PLC故障诊断平台.exe 内嵌的 app 模块逻辑一致，但现在是可读可改的 Python 源码。
想加故障类型，只要往 FAULTS 里加一项，再到 static/script.js 的 FAULT_BUTTONS 加一个按钮即可。

字段说明
- name         故障名称，前端显示在「故障」处
- alarm        报警代码 + 描述，显示在「报警信息」面板
- message      停机说明，显示在设备总览下方
- motor        电机状态文字
- sensor       传感器状态文字（可选，不写则沿用运行正常时的值）
- temperature  故障时的温度，单位 °C（可选，不写则沿用运行正常时的值）
- io           PLC 点位状态，X0 入料传感器 / X1 急停回路 / Y0 电机启动输出 / M100 电机保护反馈
- causes       可能原因，前端渲染成有序列表
- steps        标准排查步骤，前端渲染成有序列表
"""

from copy import deepcopy

import random
import time

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# ---------------------------------------------------------------- 正常运行状态
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

# ---------------------------------------------------------------- 故障库
FAULTS = {
    "sensor": {
        "name": "传感器断线",
        "alarm": "E101 · 入料传感器信号异常",
        "message": "检测信号丢失，输送线已停止以防止误动作。",
        "motor": "停止",
        "sensor": "断线",
        "io": {"X0": 0, "X1": 1, "Y0": 0, "M100": 1},
        "causes": [
            "传感器电缆断线或接头松动",
            "传感器供电 24VDC 异常",
            "输入模块 X0 通道损坏",
        ],
        "steps": [
            "检查 PLC 输入模块 X0 指示灯是否熄灭",
            "检查传感器接线端子及 24VDC 供电",
            "使用万用表测量传感器输出信号",
            "修复后确认 X0 信号恢复",
        ],
    },
    "overload": {
        "name": "电机过载",
        "alarm": "E202 · 电机热继电器保护动作",
        "message": "电机保护动作，输送线无法启动。",
        "motor": "过载保护",
        "temperature": 78,
        "io": {"X0": 1, "X1": 1, "Y0": 0, "M100": 0},
        "causes": [
            "输送带卡料或机械阻力过大",
            "电机负载超过额定值",
            "热继电器整定值偏低或接线松动",
        ],
        "steps": [
            "检查输送带和滚筒是否有卡料",
            "检查电机电流及热继电器状态",
            "确认 M100 电机保护反馈信号",
            "排除机械故障后复位热继电器",
        ],
    },
    "emergency": {
        "name": "急停触发",
        "alarm": "E001 · 急停回路断开",
        "message": "急停触发，安全回路锁定，输送线无法启动。",
        "motor": "停止",
        "io": {"X0": 1, "X1": 0, "Y0": 0, "M100": 1},
        "causes": [
            "急停按钮被按下",
            "急停回路接线松动或断线",
            "安全继电器未复位",
        ],
        "steps": [
            "检查现场急停按钮是否按下",
            "检查 X1 急停输入状态",
            "确认安全继电器已复位",
            "解除急停后执行启动确认",
        ],
    },
    "communication": {
        "name": "通讯故障",
        "alarm": "E301 · PLC 与变频器通讯超时",
        "message": "变频器通讯中断，PLC 禁止输出启动命令。",
        "motor": "状态未知",
        "io": {"X0": 1, "X1": 1, "Y0": 0, "M100": 1},
        "causes": [
            "通讯电缆松动、断线或屏蔽不良",
            "变频器掉电或通讯参数不匹配",
            "PLC 通讯模块异常",
        ],
        "steps": [
            "检查 PLC 和变频器通讯指示灯",
            "检查通讯线缆与终端电阻",
            "核对站号、波特率和协议参数",
            "恢复通讯后确认故障代码清除",
        ],
    },
}

# ---------------------------------------------------------------- 运行时状态
state = deepcopy(BASE_STATE)

# 考核模式：出题后后端会把报警码与诊断结论裁掉，学员只能靠 I/O 和梯形图判断
EXAM = {
    "active": False,
    "answer": None,
    "started": None,
    "answered": False,
    "result": None,
    "score": 0,
    "total": 0,
}


def apply_fault(fault_key: str) -> None:
    """把某个故障写入运行时状态。"""
    fault = FAULTS[fault_key]
    state.update(
        {
            "line_status": "故障停机",
            "line_message": fault["message"],
            "motor": fault["motor"],
            "sensor": fault.get("sensor", BASE_STATE["sensor"]),
            "temperature": fault.get("temperature", BASE_STATE["temperature"]),
            "alarm": fault["alarm"],
            "io": deepcopy(fault["io"]),
            "fault": fault["name"],
            "diagnosis": {
                "causes": list(fault["causes"]),
                "steps": list(fault["steps"]),
            },
        }
    )


def reset_state() -> None:
    state.clear()
    state.update(deepcopy(BASE_STATE))


def public_state():
    """对外暴露的状态快照；考核模式下隐藏答案。"""
    snapshot = dict(state)
    snapshot["io"] = dict(state["io"])

    if EXAM["active"]:
        snapshot["alarm"] = "*** 故障已发生，请根据 I/O 判断 ***"
        snapshot["diagnosis"] = None
        snapshot["fault"] = "考核中"
        snapshot["line_message"] = "设备已停机，请判断故障原因。"
        # 「传感器断线」会直接把答案写在设备总览里，考核时统一显示为异常
        if snapshot.get("sensor") not in (None, "正常"):
            snapshot["sensor"] = "异常"

    snapshot["exam"] = {
        "active": EXAM["active"],
        "pending": bool(EXAM["answer"]) and not EXAM["answered"],
        "answered": EXAM["answered"],
        "score": EXAM["score"],
        "total": EXAM["total"],
        "result": EXAM["result"],
    }
    return snapshot


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify(public_state())


@app.route("/api/fault/<fault_key>", methods=["POST"])
def simulate_fault(fault_key):
    """注入指定故障，整机进入停机状态。"""
    if EXAM["active"]:
        return jsonify({"error": "考核进行中，不能手动注入"}), 400
    if fault_key not in FAULTS:
        return jsonify({"error": "未知故障类型"}), 404

    apply_fault(fault_key)
    return jsonify(public_state())


@app.route("/api/reset", methods=["POST"])
def reset():
    """一键复位，恢复初始运行状态。"""
    reset_state()
    return jsonify(public_state())


# ---------------------------------------------------------------- 考核模式
@app.route("/api/exam/enter", methods=["POST"])
def exam_enter():
    """进入考核模式，成绩清零。"""
    reset_state()
    EXAM.update(
        {
            "active": True,
            "answer": None,
            "started": None,
            "answered": False,
            "result": None,
            "score": 0,
            "total": 0,
        }
    )
    return jsonify(public_state())


@app.route("/api/exam/start", methods=["POST"])
def exam_start():
    """随机抽一个故障出题。"""
    key = random.choice(list(FAULTS))
    apply_fault(key)
    EXAM.update(
        {
            "active": True,
            "answer": key,
            "started": time.time(),
            "answered": False,
            "result": None,
        }
    )
    return jsonify(public_state())


@app.route("/api/exam/answer", methods=["POST"])
def exam_answer():
    """提交答案并判分。"""
    if not EXAM["active"] or not EXAM["answer"] or EXAM["answered"]:
        return jsonify({"error": "当前没有待答题目"}), 400

    data = request.get_json(silent=True) or {}
    pick = data.get("key")
    if pick not in FAULTS:
        return jsonify({"error": "无效的故障类型"}), 400

    answer_key = EXAM["answer"]
    correct = pick == answer_key
    elapsed = max(0.0, time.time() - (EXAM["started"] or time.time()))

    EXAM["total"] += 1
    if correct:
        EXAM["score"] += 1
    EXAM["answered"] = True
    EXAM["result"] = {
        "correct": correct,
        "pick_key": pick,
        "answer_key": answer_key,
        "answer_name": FAULTS[answer_key]["name"],
        "elapsed": round(elapsed, 1),
    }
    return jsonify(public_state())


@app.route("/api/exam/exit", methods=["POST"])
def exam_exit():
    """退出考核，回到练习模式。"""
    EXAM.update(
        {"active": False, "answer": None, "started": None, "answered": False, "result": None}
    )
    reset_state()
    return jsonify(public_state())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
