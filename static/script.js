/* ===== PLC 故障诊断模拟平台 · 前端交互 ===== */

const IO_META = {
  X0: "入料传感器",
  X1: "急停回路",
  Y0: "电机启动输出",
  M100: "电机保护反馈",
};

// 与后端 FAULTS 字典一一对应；后端新增故障时，这里同步加一项即可。
const FAULT_BUTTONS = [
  { key: "sensor", label: "传感器断线" },
  { key: "overload", label: "电机过载" },
  { key: "emergency", label: "急停触发" },
  { key: "communication", label: "通讯故障" },
];

const POLL_INTERVAL = 1500;

const $ = (id) => document.getElementById(id);
let activeFaultKey = null;

/* ---------- 渲染：PLC I/O 指示灯 ---------- */
function buildIoGrid() {
  const grid = $("io-grid");
  grid.innerHTML = "";
  Object.entries(IO_META).forEach(([point, desc]) => {
    const cell = document.createElement("div");
    cell.className = "io-cell";
    cell.id = `io-${point}`;
    cell.innerHTML = `
      <span class="io-lamp"></span>
      <span class="io-name">${point}</span>
      <span class="io-desc">${desc}</span>
      <span class="io-val">--</span>`;
    grid.appendChild(cell);
  });
}

function renderIo(io) {
  Object.keys(IO_META).forEach((point) => {
    const cell = $(`io-${point}`);
    if (!cell) return;
    const value = io && io[point] !== undefined ? io[point] : null;
    const isOn = value === 1;
    cell.classList.toggle("is-on", isOn);
    cell.classList.toggle("is-off", value === 0);
    cell.querySelector(".io-val").textContent = value === null ? "--" : value;
  });
}

/* ---------- 渲染：故障注入按钮 ---------- */
function buildFaultButtons() {
  const wrap = $("fault-buttons");
  wrap.innerHTML = "";
  FAULT_BUTTONS.forEach(({ key, label }) => {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.dataset.key = key;
    btn.addEventListener("click", () => injectFault(key));
    wrap.appendChild(btn);
  });
}

/* ---------- 渲染：诊断结果 ---------- */
function renderDiagnosis(diagnosis) {
  const box = $("diagnosis");
  if (!diagnosis) {
    box.className = "diagnosis diagnosis-empty";
    box.textContent = "当前无故障，设备运行正常。";
    return;
  }

  box.className = "diagnosis";
  const causes = (diagnosis.causes || [])
    .map((c) => `<li>${c}</li>`)
    .join("");
  const steps = (diagnosis.steps || [])
    .map((s) => `<li>${s}</li>`)
    .join("");

  box.innerHTML = `
    <div class="diag-block">
      <h3>可能原因</h3>
      <ol>${causes}</ol>
    </div>
    <div class="diag-block">
      <h3>标准排查步骤</h3>
      <ol>${steps}</ol>
    </div>`;
}

/* ---------- 渲染：整页状态 ---------- */
function formatRuntime(minutes) {
  if (typeof minutes !== "number") return "--";
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h} h ${m} min`;
}

function render(state) {
  const isFault = Boolean(state.fault);

  $("line-status").textContent = state.line_status || "--";
  $("line-badge").classList.toggle("is-fault", isFault);

  $("m-motor").textContent = state.motor || "--";
  $("m-sensor").textContent = state.sensor || "--";
  $("m-temperature").textContent =
    state.temperature !== undefined ? `${state.temperature} °C` : "--";
  $("m-runtime").textContent = formatRuntime(state.runtime);

  $("line-message").textContent = state.line_message || "--";

  renderIo(state.io);

  const alarmBox = $("alarm");
  alarmBox.textContent = state.alarm || "无";
  alarmBox.classList.toggle("is-fault", isFault);

  renderDiagnosis(state.diagnosis);

  // 高亮当前激活的故障按钮
  activeFaultKey = state.fault ? activeFaultKey : null;
  document.querySelectorAll("#fault-buttons button").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.key === activeFaultKey);
  });
}

/* ---------- 数据请求 ---------- */
async function fetchStatus() {
  const res = await fetch("/api/status");
  if (!res.ok) throw new Error(`状态查询失败: ${res.status}`);
  return res.json();
}

async function injectFault(key) {
  activeFaultKey = key;
  const res = await fetch(`/api/fault/${key}`, { method: "POST" });
  if (!res.ok) {
    console.error("故障注入失败", res.status);
    return;
  }
  render(await res.json());
}

async function resetDevice() {
  activeFaultKey = null;
  const res = await fetch("/api/reset", { method: "POST" });
  if (!res.ok) {
    console.error("复位失败", res.status);
    return;
  }
  render(await res.json());
}

/* ---------- 轮询 ---------- */
async function poll() {
  try {
    render(await fetchStatus());
  } catch (err) {
    console.error(err);
    $("line-status").textContent = "连接中断";
    $("line-badge").classList.add("is-fault");
  }
}

/* ---------- 初始化 ---------- */
function init() {
  buildIoGrid();
  buildFaultButtons();
  $("btn-reset").addEventListener("click", resetDevice);
  poll();
  setInterval(poll, POLL_INTERVAL);
}

document.addEventListener("DOMContentLoaded", init);
