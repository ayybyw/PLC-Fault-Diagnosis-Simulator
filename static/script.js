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

/* ---------- 渲染：控制回路梯形图 ---------- */
// 固定回路：X1 急停常闭 +（X0 入料 并 Y0 自锁）+ M100 保护常闭 + COMM 通讯使能 → Y0 输出
// 每一段导线的颜色由它前面所有条件是否满足决定，故障时能一眼看出断在哪一级。
const LD_ON = "#4da3ff";
const LD_OFF = "#39485c";
const LD_FAULT = "#ff5d5d";
const LD_COIL = "#2ecc71";

function ldWire(x1, y1, x2, y2, energized) {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${energized ? LD_ON : LD_OFF}" stroke-width="1.6" />`;
}

function ldContact(x, y, closed, addr, desc, isNC) {
  const c = closed ? LD_ON : LD_FAULT;
  const slash = isNC
    ? `<line x1="${x}" y1="${y + 10}" x2="${x + 26}" y2="${y - 10}" stroke="${c}" stroke-width="1.4" />`
    : "";
  return `
    <line x1="${x}" y1="${y - 10}" x2="${x}" y2="${y + 10}" stroke="${c}" stroke-width="1.6" />
    <line x1="${x + 26}" y1="${y - 10}" x2="${x + 26}" y2="${y + 10}" stroke="${c}" stroke-width="1.6" />
    ${slash}
    <text x="${x + 13}" y="${y + 26}" text-anchor="middle" class="ld-addr" fill="${closed ? "#9fc4e8" : "#ff9b9b"}">${addr}</text>
    <text x="${x + 13}" y="${y + 40}" text-anchor="middle" class="ld-desc">${desc}</text>`;
}

function ldCoil(x, y, on, addr) {
  const c = on ? LD_COIL : "#55667a";
  return `
    <path d="M${x},${y - 12} A12 12 0 0 0 ${x},${y + 12}" stroke="${c}" stroke-width="1.6" fill="none" />
    <path d="M${x + 24},${y - 12} A12 12 0 0 1 ${x + 24},${y + 12}" stroke="${c}" stroke-width="1.6" fill="none" />
    <text x="${x + 12}" y="${y + 4}" text-anchor="middle" class="ld-coil" fill="${on ? LD_COIL : "#7c8fa6"}">${addr}</text>`;
}

function ladderSvg(state) {
  const io = state.io || {};
  const X1 = io.X1 === 1;
  const X0 = io.X0 === 1;
  const Y0 = io.Y0 === 1;
  const M100 = io.M100 === 1;
  const COMM = state.fault !== "通讯故障";

  const e1 = X1;
  const eBranch = e1 && (X0 || Y0);
  const eM = eBranch && M100;
  const eComm = eM && COMM;

  const y = 72;
  const y2 = 128;
  return `<svg viewBox="0 0 620 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="输送线起保停控制回路">
    <line x1="30" y1="28" x2="30" y2="186" class="ld-rail" />
    <line x1="592" y1="28" x2="592" y2="186" class="ld-rail" />
    ${ldWire(30, y, 58, y, true)}
    ${ldContact(58, y, X1, "X1", "急停", true)}
    ${ldWire(84, y, 118, y, e1)}
    ${ldWire(118, y, 118, y2, e1)}
    ${ldWire(118, y, 136, y, e1)}
    ${ldContact(136, y, X0, "X0", "入料", false)}
    ${ldWire(162, y, 196, y, e1 && X0)}
    ${ldWire(118, y2, 136, y2, e1)}
    ${ldContact(136, y2, Y0, "Y0", "自锁", false)}
    ${ldWire(162, y2, 196, y2, e1 && Y0)}
    ${ldWire(196, y, 196, y2, eBranch)}
    ${ldWire(196, y, 222, y, eBranch)}
    ${ldContact(222, y, M100, "M100", "保护", true)}
    ${ldWire(248, y, 286, y, eM)}
    ${ldContact(286, y, COMM, "COMM", "通讯", false)}
    ${ldWire(312, y, 398, y, eComm)}
    ${ldCoil(410, y, eComm, "Y0")}
    ${ldWire(446, y, 592, y, eComm)}
  </svg>`;
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
  $("diagnosis-panel").querySelector("h2").textContent = "诊断结果";
  if (!diagnosis) {
    box.className = "diagnosis diagnosis-empty";
    box.textContent = "当前无故障，设备运行正常。";
    return;
  }

  box.className = "diagnosis exam-mode";
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

/* ---------- 考核模式 ---------- */
// 进入考核后后端会把报警码、诊断结论全部裁掉，只留 I/O 与梯形图作为线索，
// 学员据此判断故障类型，答完由后端判分。
function renderExam(state) {
  const box = $("diagnosis");
  const exam = state.exam || {};
  box.className = "diagnosis exam-mode";
  $("diagnosis-panel").querySelector("h2").textContent = "考核答题";

  if (exam.answered && exam.result) {
    const r = exam.result;
    const opts = FAULT_BUTTONS.map(({ key, label }) => {
      let cls = "exam-opt";
      if (key === r.answer_key) cls += " is-right";
      else if (key === r.pick_key) cls += " is-wrong";
      return `<button class="${cls}" disabled>${label}</button>`;
    }).join("");
    box.innerHTML = `
      <div class="exam-options">${opts}</div>
      <div class="exam-result ${r.correct ? "ok" : "bad"}">
        <strong>${r.correct ? "判断正确" : "判断错误"}</strong> · 正确答案：${r.answer_name}
        <div class="exam-meta">
          <span>用时 ${r.elapsed.toFixed(1)} 秒</span>
          <span>累计 ${exam.score} / ${exam.total}</span>
        </div>
      </div>`;
    return;
  }

  if (exam.pending) {
    const opts = FAULT_BUTTONS.map(
      ({ key, label }) => `<button class="exam-opt" data-key="${key}">${label}</button>`
    ).join("");
    box.innerHTML = `
      <p class="exam-hint">请根据 I/O 指示灯与梯形图判断当前故障类型：</p>
      <div class="exam-options">${opts}</div>`;
    box.querySelectorAll(".exam-opt").forEach((btn) => {
      btn.addEventListener("click", () => answerExam(btn.dataset.key));
    });
    return;
  }

  box.innerHTML = `
    <p class="exam-hint">系统会随机注入一个故障，报警码与诊断结论全部隐藏，请根据 I/O 与梯形图判断故障类型。</p>
    <p class="exam-hint">点下方「随机出题」开始。</p>`;
}

function syncExamBar(exam) {
  const on = Boolean(exam.active);
  const toggle = $("btn-exam");
  toggle.classList.toggle("is-on", on);
  toggle.textContent = on ? "退出考核" : "考核模式";
  $("practice-group").hidden = on;
  $("exam-group").hidden = !on;
  const score = $("exam-score");
  score.hidden = !on;
  if (on) score.textContent = `得分 ${exam.score || 0} / ${exam.total || 0}`;
}

async function examAction(path) {
  const res = await fetch(path, { method: "POST" });
  if (!res.ok) throw new Error(`请求失败: ${res.status}`);
  return res.json();
}

async function enterExam() {
  try {
    render(await examAction("/api/exam/enter"));
  } catch (err) {
    showConnectionError(err, $("diagnosis"));
  }
}

async function startExam() {
  try {
    render(await examAction("/api/exam/start"));
  } catch (err) {
    showConnectionError(err, $("diagnosis"));
  }
}

async function exitExam() {
  try {
    render(await examAction("/api/exam/exit"));
  } catch (err) {
    showConnectionError(err, $("diagnosis"));
  }
}

async function answerExam(key) {
  try {
    const res = await fetch("/api/exam/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
    if (!res.ok) throw new Error(`提交失败: ${res.status}`);
    render(await res.json());
  } catch (err) {
    showConnectionError(err, $("diagnosis"));
  }
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
  const exam = state.exam || {};

  $("line-status").textContent = state.line_status || "--";
  $("line-badge").classList.toggle("is-fault", isFault);

  $("m-motor").textContent = state.motor || "--";
  $("m-sensor").textContent = state.sensor || "--";
  $("m-temperature").textContent =
    state.temperature !== undefined ? `${state.temperature} °C` : "--";
  $("m-runtime").textContent = formatRuntime(state.runtime);

  $("line-message").textContent = state.line_message || "--";

  renderIo(state.io);
  $("ladder").innerHTML = ladderSvg(state);

  const alarmBox = $("alarm");
  alarmBox.textContent = state.alarm || "无";
  alarmBox.classList.toggle("is-fault", isFault);

  if (exam.active) {
    renderExam(state);
  } else {
    renderDiagnosis(state.diagnosis);
  }
  syncExamBar(exam);

  // 高亮当前激活的故障按钮
  activeFaultKey = state.fault ? activeFaultKey : null;
  document.querySelectorAll("#fault-buttons button").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.key === activeFaultKey);
  });
}

/* ---------- 连接异常提示 ---------- */
// 原实现里注入/复位失败只写了 console.error，页面上没有任何反馈，
// 服务未启动时看起来就像"按钮点不动"。这里把失败显式画到界面上。
function showConnectionError(err, target) {
  console.error(err);
  $("line-status").textContent = "连接中断";
  $("line-badge").classList.add("is-fault");
  if (target) {
    target.className = "diagnosis";
    target.innerHTML = `
      <div class="diag-block">
        <h3>无法连接服务</h3>
        <ol>
          <li>请确认启动时弹出的那个黑色命令窗口还开着（关掉它服务就停了）</li>
          <li>确认浏览器地址是 http://127.0.0.1:5000</li>
          <li>若窗口已关闭，重新双击 start.bat 启动即可</li>
        </ol>
      </div>`;
  }
}

/* ---------- 渲染调度：只接受最新一次请求的结果 ---------- */
// 轮询（每 1.5 秒一次）和按钮点击会并发发出请求。如果不做序号保护，
// 先发出、后返回的旧状态会把刚点出来的新故障覆盖掉，看起来就像"点了不切换"。
let latestRequestId = 0;

async function applyLatest(factory) {
  const id = ++latestRequestId;
  const state = await factory();
  if (id !== latestRequestId) return; // 已有更新的请求，丢弃这次旧结果
  render(state);
}

/* ---------- 数据请求 ---------- */
async function fetchStatus() {
  const res = await fetch("/api/status");
  if (!res.ok) throw new Error(`状态查询失败: ${res.status}`);
  return res.json();
}

async function injectFault(key) {
  activeFaultKey = key;
  try {
    await applyLatest(async () => {
      const res = await fetch(`/api/fault/${key}`, { method: "POST" });
      if (!res.ok) throw new Error(`故障注入失败: ${res.status}`);
      return res.json();
    });
  } catch (err) {
    showConnectionError(err, $("diagnosis"));
  }
}

async function resetDevice() {
  if ($("btn-exam").classList.contains("is-on")) {
    return exitExam();
  }
  activeFaultKey = null;
  try {
    await applyLatest(async () => {
      const res = await fetch("/api/reset", { method: "POST" });
      if (!res.ok) throw new Error(`复位失败: ${res.status}`);
      return res.json();
    });
  } catch (err) {
    showConnectionError(err, $("diagnosis"));
  }
}

/* ---------- 轮询 ---------- */
async function poll() {
  try {
    await applyLatest(fetchStatus);
  } catch (err) {
    showConnectionError(err, null);
  }
}

/* ---------- 初始化 ---------- */
function init() {
  buildIoGrid();
  buildFaultButtons();
  $("btn-reset").addEventListener("click", resetDevice);
  $("btn-exam").addEventListener("click", () => {
    $("btn-exam").classList.contains("is-on") ? exitExam() : enterExam();
  });
  $("btn-exam-start").addEventListener("click", startExam);
  poll();
  setInterval(poll, POLL_INTERVAL);
}

document.addEventListener("DOMContentLoaded", init);
