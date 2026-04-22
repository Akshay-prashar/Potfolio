/* Match Broadcast Suite JS */

const REFRESH = 5000;

function el(id) { return document.getElementById(id); }

function updateText(id, val) {
  var node = el(id);
  if (!node) return;
  if (node.textContent === String(val)) return;
  node.textContent = val;
}

function updateHtml(id, val) {
  var node = el(id);
  if (!node) return;
  if (node.innerHTML === String(val)) return;
  node.innerHTML = val;
}

function render(data) {
  var live = data.live;
  if (!live) {
    updateText("statusLine", "No live match data available.");
    return;
  }

  // Hero section
  updateText("matchTeams", live.batting_team + " vs " + live.bowling_team + " " + (live.match_title ? "— " + live.match_title : ""));
  updateText("scoreRuns", live.runs);
  updateText("scoreWk", live.wickets);
  updateText("scoreOv", live.overs);

  if (live.target) {
    updateText("targetLine", "Target: " + live.target + " • Need " + (live.target - live.runs) + " from " + Math.round((20 - live.overs) * 6) + " balls");
  } else {
    updateText("targetLine", "Innings 1");
  }

  var meta = "CRR <strong>" + (live.crr || "0.0") + "</strong>";
  if (live.rrr) meta += " &nbsp;|&nbsp; RRR <strong>" + live.rrr + "</strong>";
  updateHtml("metaStrip", meta);

  // Match outlook
  updateText("winnerText", live.predicted_winner ? live.predicted_winner + " (" + live.win_percentage + ")" : "TBD");
  updateText("partnershipText", live.partnership || "");

  // Session Predictions
  var sp = live.session_predictions || {};
  var cpHtml = "";
  var checkpoints = [6, 10, 15, 20];
  for (var i = 0; i < checkpoints.length; i++) {
    var cp = checkpoints[i];
    var val = sp[String(cp)];
    var isActive = live.overs < cp && (i === 0 || live.overs >= checkpoints[i - 1]);
    cpHtml += '<div class="stat-box' + (isActive ? ' active-cp' : '') + '">' +
      '<span class="label">' + cp + ' OV</span>' +
      '<span class="val' + (isActive ? ' green-val' : '') + '">' + (val != null ? val : '--') + '</span>' +
    '</div>';
  }
  updateHtml("sessionGrid", cpHtml);

  // Batsmen
  var bats = live.batsmen_at_crease || [];
  if (bats.length === 0) {
    updateHtml("batsmenPanel", '<p class="muted">No current batsmen.</p>');
  } else {
    var bHtml = "";
    for (var i = 0; i < bats.length; i++) {
        var b = bats[i];
        bHtml += '<div class="player-row">' +
          '<div class="player-name">' + (b.name || "Unknown") + (b.is_batting ? '<span class="striker">●</span>' : '') + '</div>' +
          '<div class="player-stats"><strong>' + (b.runs || 0) + '</strong> (' + (b.balls || 0) + ') &nbsp;' +
          'SR: ' + (b.strike_rate || 0) + ' &nbsp;' + (b.fours || 0) + 'x4 ' + (b.sixes || 0) + 'x6</div>' +
        '</div>';
    }
    updateHtml("batsmenPanel", bHtml);
  }

  // Bowlers
  var bowls = live.current_bowlers || [];
  if (bowls.length === 0) {
    updateHtml("bowlersPanel", '<p class="muted">No current bowler.</p>');
  } else {
    var boHtml = "";
    for (var i = 0; i < bowls.length; i++) {
        var bo = bowls[i];
        boHtml += '<div class="player-row">' +
          '<div class="player-name">' + (bo.name || "Unknown") + '</div>' +
          '<div class="player-stats"><strong>' + (bo.runs || 0) + '-' + (bo.wickets || 0) + '</strong> (' + (bo.overs || 0) + 'ov) &nbsp;' +
          'Econ: ' + (bo.economy || 0) + ' &nbsp;' + (bo.maidens ? bo.maidens + 'm' : '') + '</div>' +
        '</div>';
    }
    updateHtml("bowlersPanel", boHtml);
  }

  // Recent balls
  var balls = live.recent_balls || [];
  if (balls.length === 0) {
    updateHtml("recentBalls", '<p class="muted">Waiting for deliveries...</p>');
  } else {
    var blHtml = "";
    for (var i = 0; i < balls.length; i++) {
      var bb = balls[i];
      var runs = bb.runs;
      var cName = "ball";
      var t = runs;
      if (bb.is_wicket) { cName += " b-wicket"; t = "W"; }
      else if (bb.is_four) { cName += " b-four"; }
      else if (bb.is_six) { cName += " b-six"; }
      else if (runs === 0) { cName += " b-dot"; }
      blHtml += '<div class="' + cName + '" title="' + (bb.text || '') + '">' + t + '</div>';
    }
    updateHtml("recentBalls", blHtml);
  }

  // Prev Innings
  var inngs = live.innings || [];
  var piHtml = "";
  for(var i = 0; i < inngs.length; i++) {
    var inn = inngs[i];
    if (inn.is_current) continue;
    piHtml += '<div class="player-row" style="padding-bottom:0.5rem;margin-bottom:0.5rem;">' +
      '<span class="player-name">' + (inn.team_name) + '</span>' +
      '<span style="font-weight:700;color:var(--text);">' + inn.runs + '/' + inn.wickets + ' <span class="muted" style="font-weight:400">(' + inn.overs + 'ov)</span></span>' +
    '</div>';
  }
  if (!piHtml) piHtml = '<p class="muted">No completed innings.</p>';
  updateHtml("prevInnings", piHtml);

  // Playing XI
  var xi = live.playing_xi || {};
  var keys = Object.keys(xi);
  if (keys.length > 0) {
      updateText("xi1Title", keys[0] + " XI");
      var xi1Html = xi[keys[0]].map(function(p) { return "<li>" + p.name + " <span style='font-size:0.7rem'>(" + (p.batting_style || 'N/A') + ")</span></li>"; }).join('');
      updateHtml("xi1List", xi1Html);
      
      if (keys.length > 1) {
          updateText("xi2Title", keys[1] + " XI");
          var xi2Html = xi[keys[1]].map(function(p) { return "<li>" + p.name + " <span style='font-size:0.7rem'>(" + (p.batting_style || 'N/A') + ")</span></li>"; }).join('');
          updateHtml("xi2List", xi2Html);
      }
  } else {
      updateHtml("xi1List", "<li>TBD</li>");
      updateHtml("xi2List", "<li>TBD</li>");
  }

  updateText("statusLine", "Data updated: " + new Date().toLocaleTimeString());
}

async function refresh() {
  try {
    var r = await fetch("/live");
    if (!r.ok) throw new Error("HTTP " + r.status);
    var data = await r.json();
    if (data.status === "live") {
        render(data);
    } else {
        updateText("statusLine", "No live match currently active.");
        el("liveBadge").style.display = "none";
    }
  } catch (e) {
    updateText("statusLine", "Error pulling data: " + e.message);
  }
}

refresh();
setInterval(refresh, REFRESH);
