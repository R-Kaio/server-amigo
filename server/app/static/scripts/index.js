const statusIndicator = document.getElementById("status-indicator");
const statusText = document.getElementById("status-text");
const cpuValueEl = document.getElementById("cpu-value");
const memoryValueEl = document.getElementById("memory-value");
const diskValueEl = document.getElementById("disk-value");
const diskReadEl = document.getElementById("disk-read-value");
const diskWriteEl = document.getElementById("disk-write-value");
const yearEl = document.getElementById("current-year-footer");
yearEl.textContent = new Date().getFullYear();

function setStatus(connected) {
  statusIndicator.classList.toggle("connected", connected);
  statusIndicator.classList.toggle("disconnected", !connected);
  statusText.textContent = connected ? "Conectado" : "Desconectado";
}

const HISTORY_LENGTH = 30;

function createChart(ctx, color) {
  return new Chart(ctx, {
    type: "line",
    data: {
      labels: Array(HISTORY_LENGTH).fill(""),
      datasets: [
        {
          data: Array(HISTORY_LENGTH).fill(null),
          borderColor: color,
          backgroundColor: "transparent",
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { min: 0, max: 100, ticks: { stepSize: 20 } },
      },
    },
  });
}

const cpuChart = createChart(
  document.getElementById("cpuChart").getContext("2d"),
  "#ff6384"
);
const memoryChart = createChart(
  document.getElementById("memoryChart").getContext("2d"),
  "#36a2eb"
);
const diskChart = createChart(
  document.getElementById("diskChart").getContext("2d"),
  "#ffcd56"
);

function pushToChart(chart, value) {
  chart.data.datasets[0].data.push(value);
  if (chart.data.datasets[0].data.length > HISTORY_LENGTH) {
    chart.data.datasets[0].data.shift();
  }
  chart.update("none");
}

function fmtBytesPerSec(n) {
  if (n === null || n === undefined) return "---";
  const abs = Math.abs(n);
  if (abs >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(2)} MB/s`;
  if (abs >= 1024) return `${(n / 1024).toFixed(2)} KB/s`;
  return `${n.toFixed(0)} B/s`;
}

async function initWs() {
  try {
    const res = await fetch("/config.json");
    if (!res.ok) throw new Error("Falha ao obter /config.json");
    const cfg = await res.json();
    const wsUrl = cfg.wsUrl;
    if (!wsUrl) throw new Error("wsUrl não encontrada em /config.json");

    const ws = new WebSocket(wsUrl);

    ws.addEventListener("open", () => {
      setStatus(true);
      console.log("WebSocket conectado:", wsUrl);
    });

    ws.addEventListener("message", (ev) => {
      try {
        const metrics = JSON.parse(ev.data);

        if (typeof metrics.cpu === "number") {
          cpuValueEl.textContent = `${metrics.cpu}%`;
          pushToChart(cpuChart, metrics.cpu);
        }
        if (typeof metrics.memory === "number") {
          memoryValueEl.textContent = `${metrics.memory}%`;
          pushToChart(memoryChart, metrics.memory);
        }
        if (typeof metrics.disk === "number") {
          diskValueEl.textContent = `${metrics.disk}%`;
          pushToChart(diskChart, metrics.disk);
        }
        if (typeof metrics.disk_read === "number") {
          diskReadEl.textContent = fmtBytesPerSec(metrics.disk_read);
        }
        if (typeof metrics.disk_write === "number") {
          diskWriteEl.textContent = fmtBytesPerSec(metrics.disk_write);
        }
      } catch (e) {
        console.error("Erro ao processar mensagem WS:", e);
      }
    });

    ws.addEventListener("close", () => {
      setStatus(false);
      console.log("WebSocket desconectado. Tentando reconectar em 3s...");
      setTimeout(initWs, 3000);
    });

    ws.addEventListener("error", (err) => {
      console.error("WebSocket erro", err);
      try {
        ws.close();
      } catch (e) {}
    });
  } catch (err) {
    console.error("Erro ao inicializar WebSocket", err);
    setStatus(false);
    setTimeout(initWs, 3000);
  }
}

document.addEventListener("DOMContentLoaded", initWs);
