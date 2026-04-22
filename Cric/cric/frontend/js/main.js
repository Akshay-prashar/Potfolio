/* Home page — Live + Upcoming */

var REFRESH = 5000; // 5 seconds for faster updates

function fmtTime(iso) {
  if (!iso) return "TBD";
  var d = new Date(iso);
  return d.toLocaleString("en-IN", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function renderLive(live) {
  var sec = document.getElementById("liveSection");
  var hero = document.getElementById("liveHero");
  if (!live) { sec.style.display = "none"; return; }

  sec.style.display = "block";
  var bats = live.batsmen_at_crease || [];
  var batsHtml = bats.map(function(b) {
    return b.name + " " + (b.runs || 0) + "(" + (b.balls || 0) + ")";
  }).join(" & ");

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

  hero.innerHTML =
    '<a href="./match.html" class="match-card is-live glass" style="padding:0;overflow:hidden;display:block;">' +
      '<div class="score-hero">' +
        '<div style="margin-bottom:0.5rem;"><span class="live-badge">LIVE</span></div>' +
        '<p class="teams">' + live.batting_team + ' vs ' + live.bowling_team +
          (live.match_title ? ' — ' + live.match_title : '') + '</p>' +
        '<p class="score-big">' + (live.runs || 0) +
          '<span class="slash">/' + (live.wickets || 0) + '</span>' +
          ' <span style="font-size:1.5rem;color:var(--text-muted)">(' + (live.overs || 0) + ' ov)</span></p>' +
        (live.target ? '<p class="muted" style="margin-top:0.5rem;">Target: ' + live.target + ' • Need ' + (live.target - live.runs) + ' from ' + Math.round((20 - live.overs) * 6) + ' balls</p>' : '') +
        '<div class="meta-strip">' +
          '<span class="meta-chip">CRR <strong>' + (live.crr || 0) + '</strong></span>' +
          (live.rrr ? '<span class="meta-chip">RRR <strong>' + live.rrr + '</strong></span>' : '') +
          (batsHtml ? '<span class="meta-chip">' + batsHtml + '</span>' : '') +
        '</div>' +
      '</div>' +
      '<div class="pad">' +
        '<p class="label" style="margin-bottom:0.75rem;">Session Predictions</p>' +
        '<div class="stat-grid stat-grid-4">' + cpHtml + '</div>' +
      '</div>' +
    '</a>';
}

function renderUpcoming(list) {
  var grid = document.getElementById("upcomingGrid");
  if (!list || list.length === 0) {
    grid.innerHTML = '<div class="glass pad" style="grid-column:1/-1;text-align:center;"><p class="muted">No upcoming IPL fixtures in the next 48 hours.</p></div>';
    return;
  }
  var html = "";
  for (var i = 0; i < list.length; i++) {
    var m = list[i];
    html += '<div class="match-card">' +
      '<span class="label">UPCOMING</span>' +
      '<h3>' + (m.team1 || "TBD") + ' vs ' + (m.team2 || "TBD") + '</h3>' +
      (m.title ? '<p class="muted" style="font-size:0.85rem;">' + m.title + '</p>' : '') +
      '<div class="card-footer">' +
        '<span style="font-weight:700;font-size:0.9rem;">' + fmtTime(m.start_time) + '</span>' +
        (m.venue ? '<span class="muted" style="font-size:0.8rem;">' + m.venue + '</span>' : '') +
      '</div>' +
    '</div>';
  }
  grid.innerHTML = html;
}

async function refresh() {
  try {
    var r = await fetch("/live");
    if (!r.ok) throw new Error(r.status);
    var data = await r.json();
    renderLive(data.live);
    renderUpcoming(data.upcoming);
  } catch (e) {
    console.error("refresh error:", e);
    document.getElementById("upcomingGrid").innerHTML =
      '<div class="glass pad" style="grid-column:1/-1;text-align:center;"><p style="color:var(--error)">Engine offline: ' + e.message + '</p></div>';
  }
}

refresh();
setInterval(refresh, REFRESH);
