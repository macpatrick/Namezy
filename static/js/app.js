(function () {
  const form = document.getElementById("generate-form");
  const generateBtn = document.getElementById("generate-btn");
  const spinner = document.getElementById("spinner");
  const statusMessage = document.getElementById("status-message");

  const LOADING_PHRASES = [
    "Thinking...",
    "Brainstorming names...",
    "Cogitating...",
    "Consulting the etymology gods...",
    "Checking domain availability...",
    "Crunching brandability scores...",
    "Still working, hang tight...",
    "Almost there...",
  ];
  let loadingInterval = null;

  function startLoading() {
    spinner.classList.remove("hidden");
    let i = 0;
    setStatus(LOADING_PHRASES[0]);
    loadingInterval = setInterval(function () {
      i = (i + 1) % LOADING_PHRASES.length;
      setStatus(LOADING_PHRASES[i]);
    }, 2200);
  }

  function stopLoading() {
    spinner.classList.add("hidden");
    if (loadingInterval) {
      clearInterval(loadingInterval);
      loadingInterval = null;
    }
  }
  const resultsPanel = document.getElementById("results-panel");
  const resultsBody = document.getElementById("results-body");
  const resultCount = document.getElementById("result-count");
  const googleStatus = document.getElementById("google-status");
  const exportLink = document.getElementById("export-link");
  const table = document.getElementById("results-table");

  let candidates = [];
  let currentSort = { key: "score", dir: "desc" };
  let chart = null;

  function setStatus(message, isError) {
    statusMessage.textContent = message || "";
    statusMessage.classList.toggle("error", Boolean(isError));
  }

  function domainLabel(status) {
    if (status === "available") return "Available";
    if (status === "taken") return "Taken";
    if (status === "unknown" || !status) return "?";
    return status;
  }

  function webLabel(status) {
    switch (status) {
      case "clear":
        return "Clear";
      case "conflict":
        return "Conflict";
      case "not_configured":
        return "Not checked";
      case "error":
        return "Error";
      default:
        return "Unchecked";
    }
  }

  function renderTable() {
    resultsBody.innerHTML = "";
    const rows = [...candidates].sort((a, b) => {
      const key = currentSort.key;
      let av = a[key];
      let bv = b[key];
      if (av === null || av === undefined) av = "";
      if (bv === null || bv === undefined) bv = "";
      if (typeof av === "string") av = av.toLowerCase();
      if (typeof bv === "string") bv = bv.toLowerCase();
      if (av < bv) return currentSort.dir === "asc" ? -1 : 1;
      if (av > bv) return currentSort.dir === "asc" ? 1 : -1;
      return 0;
    });

    for (const c of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="col-favorite">
          <span class="favorite-star ${c.favorite ? "active" : ""}" data-id="${c.id}">&#9733;</span>
        </td>
        <td>${escapeHtml(c.candidate)}</td>
        <td>${escapeHtml(c.method || "")}</td>
        <td class="score-cell">${c.score}</td>
        <td class="status-${c.domain_com || "unknown"}">${domainLabel(c.domain_com)}</td>
        <td class="status-${c.domain_io || "unknown"}">${domainLabel(c.domain_io)}</td>
        <td class="status-${c.domain_app || "unknown"}">${domainLabel(c.domain_app)}</td>
        <td class="status-${c.google || "not_configured"}">${webLabel(c.google)}</td>
      `;
      resultsBody.appendChild(tr);
    }

    resultsBody.querySelectorAll(".favorite-star").forEach((el) => {
      el.addEventListener("click", onToggleFavorite);
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function renderChart() {
    const buckets = [0, 0, 0, 0, 0]; // 0-19, 20-39, 40-59, 60-79, 80-100
    for (const c of candidates) {
      const idx = Math.min(4, Math.floor(c.score / 20));
      buckets[idx] += 1;
    }
    const ctx = document.getElementById("score-chart").getContext("2d");
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["0-19", "20-39", "40-59", "60-79", "80-100"],
        datasets: [
          {
            label: "Candidates by brandability score",
            data: buckets,
            backgroundColor: "#5b8def",
            borderRadius: 4,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: "#8b93a3" } },
          y: { beginAtZero: true, ticks: { color: "#8b93a3", precision: 0 } },
        },
      },
    });
  }

  function onToggleFavorite(evt) {
    const id = evt.currentTarget.getAttribute("data-id");
    fetch(`/api/candidates/${id}/favorite`, { method: "PATCH" })
      .then((r) => r.json())
      .then((data) => {
        const candidate = candidates.find((c) => String(c.id) === String(id));
        if (candidate) candidate.favorite = data.favorite;
        renderTable();
      })
      .catch(() => setStatus("Could not update favorite.", true));
  }

  function onSortClick(evt) {
    const th = evt.currentTarget;
    const key = th.getAttribute("data-sort");
    if (currentSort.key === key) {
      currentSort.dir = currentSort.dir === "asc" ? "desc" : "asc";
    } else {
      currentSort = { key, dir: key === "candidate" || key === "method" ? "asc" : "desc" };
    }
    table.querySelectorAll("th").forEach((el) => el.classList.remove("sorted-asc", "sorted-desc"));
    th.classList.add(currentSort.dir === "asc" ? "sorted-asc" : "sorted-desc");
    renderTable();
  }

  table.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", onSortClick);
  });

  function renderResults(payload) {
    candidates = payload.candidates || [];
    resultCount.textContent = `${candidates.length} names`;
    exportLink.href = `/api/projects/${payload.project.id}/export.csv`;

    if (payload.google_configured) {
      googleStatus.textContent = "Web-conflict check: on";
      googleStatus.classList.remove("pill-muted");
    } else {
      googleStatus.textContent = "Web-conflict check: not configured (set GOOGLE_CSE_API_KEY / GOOGLE_CSE_CX)";
      googleStatus.classList.add("pill-muted");
    }

    resultsPanel.classList.remove("hidden");
    renderChart();
    renderTable();
  }

  form.addEventListener("submit", function (evt) {
    evt.preventDefault();
    const description = document.getElementById("description").value.trim();
    const companyName = document.getElementById("company_name").value.trim();
    if (!description) return;

    generateBtn.disabled = true;
    startLoading();
    resultsPanel.classList.add("hidden");

    fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description, company_name: companyName }),
    })
      .then(async (r) => {
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "Something went wrong.");
        return data;
      })
      .then((data) => {
        setStatus("");
        renderResults(data);
      })
      .catch((err) => {
        setStatus(err.message, true);
      })
      .finally(() => {
        generateBtn.disabled = false;
        stopLoading();
      });
  });
})();
