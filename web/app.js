/* MedRetrieve frontend — vanilla JS, no dependencies. */
(function () {
  "use strict";

  var config = window.MEDRETRIEVE_CONFIG || {};
  var API_BASE = (config.API_BASE || "http://localhost:8000/api/v1").replace(/\/$/, "");
  var ANALYZE_URL = API_BASE + "/transcript-icd/";
  var HEALTH_URL = API_BASE.replace(/\/api\/v1\/?$/, "") + "/health";
  var TIMEOUT_MS = 30000;
  var AUTO_DELAY_MS = 900;
  var HEALTH_POLL_MS = 30000;
  var FEEDBACK_KEY = "medretrieve_feedback_v1";
  var HISTORY_KEY = "medretrieve_history_v1";
  var AUTO_KEY = "medretrieve_auto_v1";
  var HISTORY_MAX = 10;

  var $ = function (id) { return document.getElementById(id); };
  var transcriptEl = $("transcript");
  var charCountEl = $("charCount");
  var liveStateEl = $("liveState");
  var autoCheckbox = $("autoAnalyze");
  var analyzeBtn = $("analyzeBtn");
  var clearBtn = $("clearBtn");
  var errorBanner = $("errorBanner");
  var resultsEl = $("results");
  var toolbar = $("toolbar");
  var filterbar = $("filterbar");
  var resultSearch = $("resultSearch");
  var entityFilter = $("entityFilter");
  var sortSelect = $("sortSelect");
  var resultCount = $("resultCount");
  var statusDot = $("statusDot");
  var statusText = $("statusText");
  var latencyText = $("latencyText");
  var preview = $("transcriptPreview");
  var chipsEl = $("entityChips");
  var historyWrap = $("historyWrap");
  var historyList = $("historyList");
  var historyCount = $("historyCount");
  var toastEl = $("toast");

  $("endpointLabel").textContent = ANALYZE_URL;
  $("apiBaseLabel").textContent = API_BASE;

  var lastResponse = null;
  var currentView = [];
  var activeEntity = "";
  var autoTimer = null;
  var currentController = null;
  var requestSeq = 0;
  var toastTimer = null;

  var SAMPLES = {
    pleural: "Chest X-ray shows moderate right-sided pleural effusion with compressive atelectasis. No pneumothorax seen.",
    cardiac: "Cardiomegaly with bilateral pleural effusion and pulmonary edema. Findings suggest congestive cardiac failure.",
    neuro: "MRI brain shows acute infarct in the right MCA territory with mild midline shift and cerebral edema."
  };

  try {
    autoCheckbox.checked = localStorage.getItem(AUTO_KEY) !== "off";
  } catch (e) { /* ignore */ }

  /* ---------- storage ---------- */

  function getFeedbackStore() {
    try {
      return JSON.parse(localStorage.getItem(FEEDBACK_KEY) || "{}");
    } catch (e) {
      return {};
    }
  }

  function setFeedback(code, value) {
    var store = getFeedbackStore();
    if (store[code] === value) {
      delete store[code];
    } else {
      store[code] = value;
    }
    try {
      localStorage.setItem(FEEDBACK_KEY, JSON.stringify(store));
    } catch (e) { /* ignore */ }
    return store;
  }

  function submitFeedback() {
    return Promise.resolve(); // stub for future backend endpoint
  }

  function getHistory() {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    } catch (e) {
      return [];
    }
  }

  function saveHistory(entry) {
    var h = getHistory();
    if (h.length > 0 && h[0].transcript === entry.transcript) return h;
    h.unshift(entry);
    if (h.length > HISTORY_MAX) h.length = HISTORY_MAX;
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(h));
    } catch (e) { /* ignore */ }
    return h;
  }

  /* ---------- helpers ---------- */

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.hidden = false;
    requestAnimationFrame(function () { toastEl.classList.add("show"); });
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.classList.remove("show");
      setTimeout(function () { toastEl.hidden = true; }, 160);
    }, 1600);
  }

  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.hidden = false;
  }

  function hideError() {
    errorBanner.hidden = true;
    errorBanner.textContent = "";
  }

  function setLive(text, busy) {
    liveStateEl.textContent = text;
    liveStateEl.className = "live-state" + (busy ? " busy" : "");
  }

  function setLoading(isLoading) {
    analyzeBtn.disabled = isLoading;
    analyzeBtn.textContent = isLoading ? "Analyzing…" : "Analyze";
  }

  function updateCounts() {
    var len = transcriptEl.value.length;
    var words = transcriptEl.value.trim() === "" ? 0 : transcriptEl.value.trim().split(/\s+/).length;
    charCountEl.textContent = words + (words === 1 ? " word · " : " words · ") + len + " / 8000";
  }

  function scoreWidth(score) {
    var n = Number(score);
    if (!isFinite(n)) return 0;
    return Math.max(0, Math.min(100, Math.round(n * 100)));
  }

  function timeAgo(ts) {
    var s = Math.floor((Date.now() - ts) / 1000);
    if (s < 10) return "just now";
    if (s < 60) return s + "s ago";
    var m = Math.floor(s / 60);
    if (m < 60) return m + "m ago";
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  /* ---------- rendering ---------- */

  function renderLoading() {
    toolbar.hidden = true;
    filterbar.hidden = true;
    resultCount.hidden = true;
    resultsEl.innerHTML =
      '<div class="loading" aria-label="Loading">' +
      '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>' +
      "</div>";
  }

  function renderEmpty(reason) {
    toolbar.hidden = true;
    filterbar.hidden = true;
    resultCount.hidden = true;
    resultsEl.innerHTML =
      '<div class="empty"><p>No ICD-10 codes found.</p>' +
      '<p class="hint">' + escapeHtml(reason || "The backend returns only matches with score \u2265 0.85. Try a more specific clinical phrase.") + "</p></div>";
  }

  function renderChips(entities) {
    if (!entities || entities.length === 0) {
      preview.hidden = true;
      chipsEl.innerHTML = "";
      return;
    }
    preview.hidden = false;
    chipsEl.innerHTML = entities.map(function (en) {
      return '<button type="button" class="chip" data-entity="' + escapeHtml(en) + '" aria-pressed="' + (activeEntity === en) + '">' + escapeHtml(en) + "</button>";
    }).join("");
  }

  function syncEntityFilter(entities) {
    var prev = entityFilter.value;
    entityFilter.innerHTML = '<option value="">All terms</option>' + (entities || []).map(function (en) {
      return '<option value="' + escapeHtml(en) + '">' + escapeHtml(en) + "</option>";
    }).join("");
    if (prev && (entities || []).indexOf(prev) !== -1) {
      entityFilter.value = prev;
    } else {
      entityFilter.value = "";
    }
  }

  function applyView() {
    if (!lastResponse) return;
    var all = Array.isArray(lastResponse.matches) ? lastResponse.matches : [];
    var q = resultSearch.value.trim().toLowerCase();
    var entity = entityFilter.value;

    var filtered = all.filter(function (m) {
      if (entity && m.entity !== entity) return false;
      if (q && (String(m.code || "").toLowerCase().indexOf(q) === -1 &&
                String(m.description || "").toLowerCase().indexOf(q) === -1)) return false;
      return true;
    });

    if (sortSelect.value === "code") {
      filtered.sort(function (a, b) { return String(a.code).localeCompare(String(b.code)); });
    } else {
      filtered.sort(function (a, b) { return Number(b.score) - Number(a.score); });
    }

    currentView = filtered;
    var store = getFeedbackStore();

    if (filtered.length === 0) {
      resultCount.textContent = "0 of " + all.length;
      resultCount.hidden = false;
      resultsEl.innerHTML =
        '<div class="empty"><p>No codes match this filter.</p>' +
        '<p class="hint">Clear the search or term filter to see all ' + all.length + " codes.</p></div>";
      return;
    }

    resultCount.textContent = filtered.length + (filtered.length === 1 ? " code" : " codes");
    resultCount.hidden = false;

    var html = '<ul class="result-list">';
    filtered.forEach(function (m, i) {
      var code = String(m.code || "");
      var vote = store[code] || 0;
      var considerations = Array.isArray(m.considerations) ? m.considerations : [];
      html +=
        '<li class="result enter" style="animation-delay:' + Math.min(i * 25, 200) + 'ms">' +
        '<div class="result-top"><span class="code">' + escapeHtml(code) + "</span>" +
        '<span class="desc">' + escapeHtml(m.description || "") + "</span>" +
        (m.entity ? '<span class="entity-tag">' + escapeHtml(m.entity) + "</span>" : "") +
        "</div>" +
        '<div class="score-row"><div class="score-bar"><div class="score-fill" data-w="' +
        scoreWidth(m.score) + '" style="width:0"></div></div>' +
        '<span class="score-num">' + escapeHtml(Number(m.score).toFixed(3)) + "</span></div>" +
        '<div class="result-actions">' +
        '<button type="button" class="btn btn-small" data-copy-code="' + i + '">Copy</button>' +
        '<button type="button" class="vote" data-vote="1" data-code="' + escapeHtml(code) + '" aria-pressed="' + (vote === 1) + '" title="This code looks correct">Yes</button>' +
        '<button type="button" class="vote" data-vote="-1" data-code="' + escapeHtml(code) + '" aria-pressed="' + (vote === -1) + '" title="This code looks wrong">No</button>' +
        "</div>";
      if (considerations.length > 0) {
        html += "<details><summary>Why this match (" + considerations.length + ")</summary><ul>";
        considerations.forEach(function (c) {
          html += "<li>" + escapeHtml(c) + "</li>";
        });
        html += "</ul></details>";
      }
      html += "</li>";
    });
    resultsEl.innerHTML = html + "</ul>";

    // animate score bars after paint
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        resultsEl.querySelectorAll(".score-fill").forEach(function (el) {
          el.style.width = el.getAttribute("data-w") + "%";
        });
      });
    });
  }

  function renderResults(data, opts) {
    opts = opts || {};
    lastResponse = data;
    activeEntity = "";
    resultSearch.value = "";
    var matches = Array.isArray(data.matches) ? data.matches : [];

    if (matches.length === 0) {
      renderChips(data.entities);
      syncEntityFilter(data.entities);
      renderEmpty();
      return;
    }

    toolbar.hidden = false;
    filterbar.hidden = false;
    renderChips(data.entities);
    syncEntityFilter(data.entities);
    applyView();

    if (opts.saveHistory !== false) {
      var h = saveHistory({
        transcript: transcriptEl.value.trim(),
        response: data,
        at: Date.now()
      });
      renderHistory(h);
    }
  }

  function renderHistory(h) {
    h = h || getHistory();
    if (h.length === 0) {
      historyWrap.hidden = true;
      return;
    }
    historyWrap.hidden = false;
    historyCount.textContent = h.length;
    historyList.innerHTML = h.map(function (entry, i) {
      var n = entry.response && entry.response.matches ? entry.response.matches.length : 0;
      var snippet = entry.transcript.length > 70 ? entry.transcript.slice(0, 70) + "…" : entry.transcript;
      return '<li><button type="button" data-history="' + i + '">' +
        '<span class="h-text">' + escapeHtml(snippet) + "</span>" +
        '<span class="h-meta">' + n + " codes · " + escapeHtml(timeAgo(entry.at)) + "</span>" +
        "</button></li>";
    }).join("");
  }

  /* ---------- analysis ---------- */

  function analyze(source) {
    var text = transcriptEl.value.trim();
    if (text.length < 10) {
      if (source === "manual") {
        showError("Please enter at least 10 characters of clinical text.");
        transcriptEl.focus();
      }
      return;
    }
    hideError();

    if (currentController) currentController.abort();
    var controller = new AbortController();
    currentController = controller;
    var mySeq = ++requestSeq;

    renderLoading();
    setLoading(true);
    setLive(source === "auto" ? "Auto-analyzing…" : "Analyzing…", true);

    var timer = setTimeout(function () { controller.abort(); }, TIMEOUT_MS);

    fetch(ANALYZE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: text }),
      signal: controller.signal
    })
      .then(function (res) {
        if (!res.ok) {
          return res.text().then(function (body) {
            throw new Error("Backend returned " + res.status + (body ? ": " + body.slice(0, 200) : ""));
          });
        }
        return res.json();
      })
      .then(function (data) {
        if (mySeq !== requestSeq) return; // superseded by newer request
        renderResults(data);
        setLive("Updated " + timeAgo(Date.now()), false);
      })
      .catch(function (err) {
        if (mySeq !== requestSeq) return;
        if (err && err.name === "AbortError") {
          // aborted in favor of newer keystroke — stay silent
          if (controller.signal.aborted && mySeq !== requestSeq) return;
          showError("Request timed out after 30s. The embedding model may still be warming up — try again.");
        } else {
          showError("Could not reach the backend. Is it running at " + API_BASE + "? (" + (err.message || err) + ")");
        }
        renderEmpty("Analysis failed — fix the connection and try again.");
        setLive("", false);
      })
      .finally(function () {
        clearTimeout(timer);
        if (mySeq === requestSeq) {
          setLoading(false);
          currentController = null;
        }
      });
  }

  function scheduleAuto() {
    clearTimeout(autoTimer);
    if (!autoCheckbox.checked) return;
    if (transcriptEl.value.trim().length < 10) return;
    setLive("Typing…", false);
    autoTimer = setTimeout(function () { analyze("auto"); }, AUTO_DELAY_MS);
  }

  /* ---------- clipboard / export ---------- */

  function copyText(text, okMsg) {
    var done = function () { toast(okMsg || "Copied"); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { showError("Copy failed — select the text manually."); });
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        done();
      } catch (e) {
        showError("Copy is not supported in this browser.");
      }
      document.body.removeChild(ta);
    }
  }

  /* ---------- health ---------- */

  function checkHealth() {
    var t0 = performance.now();
    fetch(HEALTH_URL, { method: "GET" })
      .then(function (res) {
        if (!res.ok) throw new Error("status " + res.status);
        return res.json();
      })
      .then(function () {
        statusDot.className = "dot dot-ok";
        statusText.textContent = "Backend online";
        latencyText.hidden = false;
        latencyText.textContent = "· " + Math.round(performance.now() - t0) + "ms";
      })
      .catch(function () {
        statusDot.className = "dot dot-bad";
        statusText.textContent = "Backend unreachable";
        latencyText.hidden = true;
      });
  }

  /* ---------- events ---------- */

  transcriptEl.addEventListener("input", function () {
    updateCounts();
    scheduleAuto();
  });

  autoCheckbox.addEventListener("change", function () {
    try {
      localStorage.setItem(AUTO_KEY, autoCheckbox.checked ? "on" : "off");
    } catch (e) { /* ignore */ }
    clearTimeout(autoTimer);
    if (autoCheckbox.checked) {
      scheduleAuto();
      toast("Auto-analyze on");
    } else {
      setLive("", false);
      toast("Auto-analyze off");
    }
  });

  document.querySelectorAll("[data-sample]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      transcriptEl.value = SAMPLES[btn.getAttribute("data-sample")] || "";
      updateCounts();
      transcriptEl.focus();
      analyze("manual");
    });
  });

  analyzeBtn.addEventListener("click", function () { analyze("manual"); });
  transcriptEl.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") analyze("manual");
  });

  clearBtn.addEventListener("click", function () {
    if (currentController) currentController.abort();
    clearTimeout(autoTimer);
    transcriptEl.value = "";
    updateCounts();
    lastResponse = null;
    currentView = [];
    activeEntity = "";
    preview.hidden = true;
    hideError();
    setLive("", false);
    renderEmpty("Enter a transcript — analysis runs automatically as you type.");
    transcriptEl.focus();
  });

  chipsEl.addEventListener("click", function (e) {
    var chip = e.target.closest("[data-entity]");
    if (!chip) return;
    var en = chip.getAttribute("data-entity");
    activeEntity = (activeEntity === en) ? "" : en;
    entityFilter.value = activeEntity;
    chipsEl.querySelectorAll(".chip").forEach(function (c) {
      c.setAttribute("aria-pressed", String(c.getAttribute("data-entity") === activeEntity));
    });
    applyView();
  });

  resultSearch.addEventListener("input", applyView);
  entityFilter.addEventListener("change", function () {
    activeEntity = entityFilter.value;
    chipsEl.querySelectorAll(".chip").forEach(function (c) {
      c.setAttribute("aria-pressed", String(c.getAttribute("data-entity") === activeEntity));
    });
    applyView();
  });
  sortSelect.addEventListener("change", applyView);

  historyList.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-history]");
    if (!btn) return;
    var h = getHistory();
    var entry = h[Number(btn.getAttribute("data-history"))];
    if (!entry) return;
    transcriptEl.value = entry.transcript;
    updateCounts();
    hideError();
    renderResults(entry.response, { saveHistory: false });
    setLive("Restored from history", false);
    toast("Restored");
  });

  $("clearHistoryBtn").addEventListener("click", function () {
    try {
      localStorage.removeItem(HISTORY_KEY);
    } catch (e) { /* ignore */ }
    renderHistory([]);
  });

  $("copyCodesBtn").addEventListener("click", function () {
    if (!lastResponse || !lastResponse.matches || lastResponse.matches.length === 0) return;
    var lines = lastResponse.matches.map(function (m) {
      return m.code + " - " + m.description;
    });
    copyText(lines.join("\n"), "Codes copied");
  });

  $("copyJsonBtn").addEventListener("click", function () {
    if (!lastResponse) return;
    copyText(JSON.stringify(lastResponse, null, 2), "JSON copied");
  });

  $("exportBtn").addEventListener("click", function () {
    if (!lastResponse) return;
    var blob = new Blob([JSON.stringify(lastResponse, null, 2)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "medretrieve-icd10.json";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      document.body.removeChild(a);
    }, 500);
    toast("Exported");
  });

  resultsEl.addEventListener("click", function (e) {
    var copyBtn = e.target.closest("[data-copy-code]");
    if (copyBtn) {
      var m = currentView[Number(copyBtn.getAttribute("data-copy-code"))];
      if (m) copyText(m.code + " - " + m.description, "Copied");
      return;
    }
    var voteBtn = e.target.closest("[data-vote]");
    if (voteBtn) {
      var code = voteBtn.getAttribute("data-code");
      var value = Number(voteBtn.getAttribute("data-vote"));
      var store = setFeedback(code, value);
      submitFeedback(code, value);
      resultsEl.querySelectorAll('[data-code="' + code.replace(/"/g, "") + '"]').forEach(function (b) {
        b.setAttribute("aria-pressed", String(store[code] === Number(b.getAttribute("data-vote"))));
      });
    }
  });

  /* ---------- init ---------- */

  updateCounts();
  renderHistory();
  checkHealth();
  setInterval(checkHealth, HEALTH_POLL_MS);
})();
