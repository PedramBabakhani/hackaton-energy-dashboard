const API_BASE = "http://localhost:8080";
let TOKEN = null;

// ---------- Utility ----------
async function login() {
  const user = document.getElementById("username").value;
  const pass = document.getElementById("password").value;
  const form = new URLSearchParams();
  form.append("username", user);
  form.append("password", pass);
  const res = await fetch(`${API_BASE}/token`, {
    method: "POST",
    body: form,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  if (!res.ok) {
    setStatus("Login failed");
    return;
  }
  const data = await res.json();
  TOKEN = data.access_token;
  console.log("JWT Token:", TOKEN);
  console.log("JWT Token:", TOKEN);
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "Authorization": `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} — ${await res.text()}`);
  }
  return res.json();
}

function setStatus(msg) {
  document.getElementById("status").innerText = msg;
}

// ---------- Ingest ----------
// ---------- Ingest ----------
function uploadCSV() {
  const file = document.getElementById("csvFile").files[0];
  if (!file) return alert("Choose a CSV first");
  const reader = new FileReader();
  reader.onload = async (e) => {
    const text = e.target.result;
    const [header, ...lines] = text.split(/\r?\n/).filter(Boolean);
    const cols = header.split(",");
    const buildingId = document.getElementById("buildingId").value;

    // --- check headers
    const requiredCols = ["ts", "q_flow_heat", "temperature", "wind_speed", "price"];
    for (const col of requiredCols) {
      if (!cols.includes(col)) {
        alert(`CSV missing required column: ${col}`);
        return;
      }
    }

    // Build records array with correct types
    const recs = lines.map((line) => {
      const vals = line.split(",");
      const rec = {};
      cols.forEach((c, i) => {
        let v = vals[i] ? vals[i].trim() : null;
        if (["q_flow_heat", "temperature", "wind_speed", "price"].includes(c.trim())) {
          v = v ? parseFloat(v) : null;
        }
        rec[c.trim()] = v;
      });
      return rec;
    });

    const payload = { building_id: buildingId, records: recs };

    try {
      await fetchJSON(`${API_BASE}/ingest`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus(`Ingested ${recs.length} rows 📥`);
    } catch (e) {
      setStatus("Upload failed: " + e);
    }
  };
  reader.readAsText(file);
}

// ---------- Ingest (JSON) ----------
async function uploadJSON() {
  const file = document.getElementById("jsonFile").files[0];
  if (!file) return alert("Choose a JSON file first");

  try {
    const text = await file.text();
    const payload = JSON.parse(text);

    // Validate schema
    if (!payload.building_id || !Array.isArray(payload.records)) {
      throw new Error("Invalid JSON: must include building_id and records[]");
    }

    await fetchJSON(`${API_BASE}/ingest`, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setStatus(`Ingested ${payload.records.length} rows 📥`);
  } catch (e) {
    setStatus("Upload failed: " + e);
  }
}

async function fetchExternal() {
  const url = document.getElementById("externalUrl").value;
  if (!url) return alert("Enter an API URL");
  try {
    const data = await (await fetch(url)).json();
    const buildingId = document.getElementById("buildingId").value;

    // If data already wrapped (has .records), unwrap it
    const recs = data.records ? data.records : data;
    const payload = { building_id: buildingId, records: recs };

    await fetchJSON(`${API_BASE}/ingest`, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setStatus(`Fetched & ingested ${recs.length} rows from external 🌍`);
  } catch (e) {
    setStatus("External fetch failed: " + e);
  }
}

// ---------- Train / Forecast / Carbon / History ----------
async function trainModel() {
  const b = document.getElementById("buildingId").value;
  try {
    await fetchJSON(`${API_BASE}/train?building_id=${b}`, { method: "POST" });
    setStatus("Model trained 🏗️");
  } catch (e) {
    setStatus("Train error: " + e);
  }
}

async function loadForecast() {
  const b = document.getElementById("buildingId").value;
  const iw = document.getElementById("histHours").value;
  const ph = document.getElementById("fcHours").value;
  try {
    const data = await fetchJSON(`${API_BASE}/forecast?building_id=${b}&hist=${iw}&hours=${ph}`);
    plotLoad(data);
    setStatus("Forecast loaded 📈");
  } catch (e) {
    setStatus("Forecast error: " + e);
  }
}

async function loadCarbon() {
  const b = document.getElementById("buildingId").value;
  const h = document.getElementById("fcHours").value;
  const f = document.getElementById("co2Factor").value;
  try {
    const data = await fetchJSON(
      `${API_BASE}/carbon?building_id=${b}&hours=${h}&factor_g_per_kwh=${f}`
    );
    plotCO2(data);
    setStatus("Carbon forecast loaded 🌍");
  } catch (e) {
    setStatus("Carbon error: " + e);
  }
}

async function loadHistory() {
  const b = document.getElementById("buildingId").value;
  const h = document.getElementById("histHours").value;
  try {
    const data = await fetchJSON(`${API_BASE}/history?building_id=${b}&hours=${h}`);
    plotHistory(data);
    setStatus("History loaded ⏳");
  } catch (e) {
    setStatus("History error: " + e);
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    document.getElementById("healthBox").innerText = await res.text();
  } catch {
    document.getElementById("healthBox").innerText = "Health check failed ❌";
  }
}

// ---------- Charting ----------
let loadChart, co2Chart;

function plotLoad(data) {
  const ctx = document.getElementById("loadChart").getContext("2d");
  if (loadChart) loadChart.destroy();

  loadChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.timestamps,
      datasets: [
        {
          label: "History",
          data: data.actual,
          borderColor: "blue",
          fill: false,
        },
        {
          label: "Forecast",
          data: data.forecast,
          borderColor: "orange",
          fill: false,
        },
        {
          label: "Low–High",
          data: data.high,
          borderColor: "rgba(0,0,0,0)",
          backgroundColor: "rgba(255,165,0,0.2)",
          fill: "+1", // fills between high and low
        },
        {
          label: "Low",
          data: data.low,
          borderColor: "rgba(0,0,0,0)",
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "top" } },
    },
  });
}


function plotCO2(data) {
  // If backend doesn’t return total, compute it
  const total = data.total !== undefined
    ? data.total
    : data.by_hour.reduce((a, b) => a + b, 0);

  document.getElementById("co2Total").innerText = total.toFixed(1) + " g";

  const ctx = document.getElementById("co2Chart").getContext("2d");
  if (co2Chart) co2Chart.destroy();
  co2Chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.by_hour.map((_, i) => i + 1),
      datasets: [
        { label: "CO₂ (g)", data: data.by_hour, backgroundColor: "green" },
      ],
    },
  });
}

function plotHistory(data) {
  const ctx = document.getElementById("loadChart").getContext("2d");
  if (loadChart) loadChart.destroy();
  loadChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map((d) => d.ts),
      datasets: [{ label: "History", data: data.map((d) => d.q_actual), borderColor: "blue" }],
    },
  });
}

// ---------- Wire up ----------
document.getElementById("loginBtn").onclick = login;
document.getElementById("uploadBtn").onclick = uploadJSON;
document.getElementById("fetchBtn").onclick = fetchExternal;
document.getElementById("trainBtn").onclick = trainModel;
document.getElementById("forecastBtn").onclick = loadForecast;
document.getElementById("carbonBtn").onclick = loadCarbon;
document.getElementById("historyBtn").onclick = loadHistory;

setInterval(checkHealth, 5000);
