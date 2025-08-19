// const API_BASE = "http://127.0.0.1:8080";

// Use backend on 8080 explicitly
const API_BASE = "http://localhost:8080";
console.log("API_BASE =", API_BASE);


const els = {
  buildingId: document.getElementById("buildingId"),
  histHours: document.getElementById("histHours"),
  fcHours: document.getElementById("fcHours"),
  co2Factor: document.getElementById("co2Factor"),
  loadBtn: document.getElementById("loadBtn"),
  status: document.getElementById("status"),
  healthBox: document.getElementById("healthBox"),
  co2Total: document.getElementById("co2Total"),
  username: document.getElementById("username"),
  password: document.getElementById("password"),
  loginBtn: document.getElementById("loginBtn"),
};

let accessToken = null;
let loadChart, co2Chart;

function fmtTs(ts) {
  return new Date(ts).toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit"
  });
}

async function fetchJSON(url) {
  const headers = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  console.log("Fetching:", url, "with headers", headers);
  const r = await fetch(url, { headers });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${txt}`);
  }
  return r.json();
}

async function loadAll() {
  if (!accessToken) {
    els.status.textContent = "Please log in first.";
    return;
  }

  const b = encodeURIComponent(els.buildingId.value.trim());
  const hHrs = Number(els.histHours.value);
  const fHrs = Number(els.fcHours.value);
  const factor = Number(els.co2Factor.value);

  els.status.textContent = "Loading…";
  try {
    const [health, hist, fc, co2] = await Promise.all([
      fetchJSON(`${API_BASE}/health`),
      fetchJSON(`${API_BASE}/history?building_id=${b}&hours=${hHrs}`),
      fetchJSON(`${API_BASE}/forecast?building_id=${b}&hours=${fHrs}`),
      fetchJSON(`${API_BASE}/carbon?building_id=${b}&hours=${fHrs}&factor_g_per_kwh=${factor}`)
    ]);

    els.healthBox.textContent = JSON.stringify(health, null, 2);

    const histX = hist.map(p => fmtTs(p.ts));
    const histY = hist.map(p => p.q_flow_heat);

    const fcX = fc.ts.map(fmtTs);
    const fcY = fc.q_forecast;
    const piLow = fc.pi_low, piHigh = fc.pi_high;

    const labels = [...histX, ...fcX];
    const actual = [...histY, ...new Array(fcX.length).fill(null)];
    const forecast = [...new Array(histX.length).fill(null), ...fcY];
    const low = [...new Array(histX.length).fill(null), ...piLow];
    const high = [...new Array(histX.length).fill(null), ...piHigh];

    drawLoadChart(labels, actual, forecast, low, high);
    drawCo2Chart(fcX, co2.co2_g);

    const totalKg = co2.total_co2_g / 1000.0;
    els.co2Total.textContent = `${totalKg.toFixed(2)} kg CO₂`;

    els.status.textContent = "Loaded ✓";
  } catch (err) {
    console.error("Load error:", err);
    els.status.textContent = `Error: ${err.message}`;
  }
}

function drawLoadChart(labels, actual, forecast, low, high) {
  const ctx = document.getElementById("loadChart").getContext("2d");
  if (loadChart) loadChart.destroy();
  loadChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Actual", data: actual, borderWidth: 2, pointRadius: 0 },
        { label: "Forecast", data: forecast, borderWidth: 2, pointRadius: 0 },
        { label: "PI Low", data: low, borderWidth: 1, pointRadius: 0 },
        { label: "PI High", data: high, borderWidth: 1, pointRadius: 0 }
      ]
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${Number(ctx.parsed.y).toFixed(2)} kWh`
          }
        }
      },
      scales: {
        y: { title: { display: true, text: "kWh" } },
        x: { ticks: { autoSkip: true, maxTicksLimit: 24 } }
      }
    }
  });
}

function drawCo2Chart(labels, grams) {
  const ctx = document.getElementById("co2Chart").getContext("2d");
  if (co2Chart) co2Chart.destroy();
  co2Chart = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ label: "g CO₂", data: grams }] },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `${Number(ctx.parsed.y).toFixed(0)} g CO₂`
          }
        }
      },
      scales: {
        y: { title: { display: true, text: "grams CO₂" } },
        x: { ticks: { autoSkip: true, maxTicksLimit: 24 } }
      }
    }
  });
}

// --- Login Handling ---
els.loginBtn.addEventListener("click", async () => {
  console.log("Login button clicked");
  const username = els.username.value;
  const password = els.password.value;
  console.log("Trying login with", username);
  try {
    const res = await fetch(`${API_BASE}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
    });
    console.log("Response status:", res.status);
    const txt = await res.text();
    console.log("Raw response:", txt);
    if (!res.ok) throw new Error(`Login failed: ${res.status} ${txt}`);
    const data = JSON.parse(txt);
    accessToken = data.access_token;
    console.log("Got token:", accessToken);
    els.status.textContent = `Logged in as ${username}`;
    // auto-load data after login
    loadAll();
  } catch (err) {
    console.error("Login error:", err);
    els.status.textContent = `Login error: ${err.message}`;
  }
});

els.loadBtn.addEventListener("click", loadAll);
