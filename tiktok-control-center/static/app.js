const API = "";

async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Erreur API");
  }
  return res.json();
}

async function refreshStatus() {
  const data = await fetchJSON("/api/status");
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  const startBtn = document.getElementById("startBtn");
  const stopBtn = document.getElementById("stopBtn");

  if (data.running) {
    dot.classList.add("running");
    text.textContent = `Session en cours (PID ${data.pid})`;
    startBtn.disabled = true;
    stopBtn.disabled = false;
  } else {
    dot.classList.remove("running");
    text.textContent = "Aucune session active";
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }
}

async function loadProfiles() {
  const profiles = await fetchJSON("/api/profiles");
  const select = document.getElementById("profile");
  const grid = document.getElementById("profilesList");
  const desc = document.getElementById("profileDesc");

  select.innerHTML = profiles
    .map((p) => `<option value="${p.name}">${p.name}</option>`)
    .join("");

  grid.innerHTML = profiles
    .map(
      (p) => `
    <div class="profile-chip">
      <strong>${p.name}</strong>
      <span>${p.description}</span>
      <span>Like: ${(p.like_probability * 100).toFixed(0)}% · ${p.session_duration_minutes} min</span>
    </div>`
    )
    .join("");

  function updateDesc() {
    const selected = profiles.find((p) => p.name === select.value);
    desc.textContent = selected ? selected.description : "";
  }
  select.addEventListener("change", updateDesc);
  updateDesc();
}

async function loadSessions() {
  const sessions = await fetchJSON("/api/sessions");
  const list = document.getElementById("sessionsList");

  if (!sessions.length) {
    list.innerHTML = '<p class="empty">Aucune session enregistrée</p>';
    return;
  }

  list.innerHTML = sessions
    .map(
      (s) => `
    <div class="session-item">
      <div>
        <strong>${s.profile}</strong>
        <div class="session-stats">
          ${s.videos_watched} vidéos · ${s.likes} likes · ${Math.round(s.duration_seconds / 60)} min
        </div>
      </div>
      <span class="session-stats">${s.filename}</span>
    </div>`
    )
    .join("");
}

document.getElementById("startForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const profile = document.getElementById("profile").value;
  const duration = parseInt(document.getElementById("duration").value, 10) || 0;

  try {
    await fetchJSON("/api/sessions/start", {
      method: "POST",
      body: JSON.stringify({ profile, duration_minutes: duration }),
    });
    await refreshStatus();
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("stopBtn").addEventListener("click", async () => {
  try {
    await fetchJSON("/api/sessions/stop", { method: "POST" });
    await refreshStatus();
    setTimeout(loadSessions, 2000);
  } catch (err) {
    alert(err.message);
  }
});

async function init() {
  await loadProfiles();
  await refreshStatus();
  await loadSessions();
  setInterval(refreshStatus, 5000);
}

init();
