/* Training JS */

var MATCHES_API = "/matches";
var SIMULATE_API = "/simulate";

var matchSelect = document.getElementById("matchSelect");
var simBtn = document.getElementById("simBtn");
var stopBtn = document.getElementById("stopBtn");
var statusText = document.getElementById("simStatus");

var abortController = null;

async function loadMatches() {
  try {
    var r = await fetch(MATCHES_API);
    var arr = await r.json();
    matchSelect.innerHTML = '<option value="all">-- All Dataset Matches (Full Engine Run) --</option>';
    for (var i = 0; i < arr.length; i++) {
        matchSelect.innerHTML += '<option value="' + arr[i].match_id + '">' + arr[i].label + '</option>';
    }
  } catch (e) {
    matchSelect.innerHTML = '<option value="">Network error - Check backend</option>';
  }
}

function renderTable(arr) {
  var tbody = document.getElementById("simTableBody");
  if (!arr || arr.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;" class="muted">No predictions generated.</td></tr>';
      return;
  }
  
  var html = "";
  for (var i = 0; i < arr.length; i++) {
      var p = arr[i];
      var isOk = (String(p.result).toLowerCase() === 'correct');
      var tagCls = isOk ? "tag-ok" : "tag-err";
      var tagTxt = isOk ? "Correct" : "Wrong";
      
      html += '<tr>' +
        '<td>' + p.inning + '</td>' +
        '<td>' + p.current_over + 'ov <span class="muted" style="margin:0 4px">→</span> <strong style="color:var(--primary)">' + p.target_over + 'ov</strong></td>' +
        '<td><strong style="font-size:1.1rem">' + (p.predicted_score != null ? p.predicted_score : '--') + '</strong></td>' +
        '<td class="muted">' + p.actual_score + '</td>' +
        '<td>' + (p.error != null ? p.error.toFixed(1) : '--') + '</td>' +
        '<td><span class="tag ' + tagCls + '">' + tagTxt + '</span></td>' +
      '</tr>';
  }
  tbody.innerHTML = html;
}

async function runSim() {
  var mId = matchSelect.value;
  var payload = {};
  if (mId && mId !== "all") {
      payload.match_id = parseInt(mId, 10);
  }

  simBtn.classList.add("btn-disabled");
  stopBtn.classList.remove("btn-disabled");
  simBtn.textContent = "Running Engine...";
  statusText.textContent = "Locking matrices...";
  statusText.style.color = "var(--primary)";
  document.getElementById("simTableBody").innerHTML = '<tr><td colspan="6" style="text-align:center;" class="muted">Awaiting stream...</td></tr>';
  
  abortController = new AbortController();

  try {
      var r = await fetch(SIMULATE_API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: abortController.signal
      });
      if (!r.ok) throw new Error(await r.text());
      var data = await r.json();
      
      document.getElementById("totP").textContent = data.total_predictions;
      document.getElementById("totC").textContent = data.correct;
      document.getElementById("totA").textContent = data.accuracy.toFixed(1) + "%";
      
      renderTable(data.predictions);
      statusText.textContent = "Simulation completed.";
      statusText.style.color = "var(--tertiary)";
  } catch (e) {
      if (e.name === "AbortError") {
          statusText.textContent = "Override: Run aborted.";
          document.getElementById("simTableBody").innerHTML = '<tr><td colspan="6" style="text-align:center;" class="muted">Aborted.</td></tr>';
      } else {
          statusText.textContent = "Engine Fault: " + e.message;
          statusText.style.color = "var(--error)";
      }
  } finally {
      simBtn.classList.remove("btn-disabled");
      stopBtn.classList.add("btn-disabled");
      simBtn.textContent = "▶ Run Simulation";
      abortController = null;
  }
}

simBtn.addEventListener("click", runSim);
stopBtn.addEventListener("click", function() {
    if(abortController) abortController.abort();
});

loadMatches();
