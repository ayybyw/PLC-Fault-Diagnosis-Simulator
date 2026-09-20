# PLC Fault Diagnosis Simulator

一个用于工业自动化售后与维修培训的网页版 PLC 故障诊断模拟平台。项目以“自动输送线”为对象，通过模拟 PLC I/O 信号变化，演示从报警到故障定位的现场排查流程。

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white) ![Flask](https://img.shields.io/badge/Flask-3.0%2B-000000?logo=flask&logoColor=white) ![License](https://img.shields.io/badge/license-MIT-green)

## 功能

- 实时展示输送线、电机、传感器、温度和运行时长状态
- 模拟传感器断线、电机过载、急停触发、PLC 与变频器通讯故障
- 根据故障自动更新 PLC 输入/输出状态（X0、X1、Y0、M100）
- 输出对应的报警、可能原因和标准排查步骤
- 一键恢复设备正常状态

## 项目结构

```text
PLC-Fault-Diagnosis-Simulator/
├── app.py
├── requirements.txt
├── static/
│   ├── style.css
│   └── script.js
├── templates/
│   └── index.html
├── screenshots/
│   └── README.md
└── README.md
```

## 快速开始

```bash
git clone https://github.com/ayybyw/PLC-Fault-Diagnosis-Simulator.git
cd PLC-Fault-Diagnosis-Simulator
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:5000`。

## 诊断逻辑

四类故障各自对应的关键 PLC 信号与典型排查方向：

- 传感器断线 —— 关键信号：X0 = OFF。排查方向：传感器供电、接线、输入模块
- 电机过载 —— 关键信号：M100 = OFF，Y0 = OFF。排查方向：卡料、电机电流、热继电器
- 急停触发 —— 关键信号：X1 = OFF，Y0 = OFF。排查方向：急停按钮、安全继电器、安全回路
- 通讯故障—— 关键信号：Y0 = OFF。排查方向：通讯线缆、站号、波特率、变频器状态

## 已知限制与后续计划

### 已知限制

- 未接入真实 PLC：所有 I/O 状态均为内存模拟，尚未对接 Modbus TCP、S7 等协议，因此无法体现真实扫描周期下的信号抖动与时序
- 点位覆盖有限：只抽象了 X0、X1、Y0、M100 四个关键点，真实产线的 I/O 数量通常在几十到上百
- 单故障假设：一次只能注入一个故障，没有考虑多故障并发与连锁停机等现场常见情况
- 无状态持久化：设备状态存放在进程内存中，重启即复位，也没有训练过程记录

### 后续计划

- 用 Modbus TCP 对接真实 PLC 或仿真器，把模拟点位换成实采数据
- 引入故障演化模型（间歇性故障、由轻到重），替代当前的瞬时切换
- 记录学员的排查路径与耗时，生成训练评分报告
- 支持多人同时训练时，把设备状态改为按 session 隔离

## License

MIT
