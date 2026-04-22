const API_BASE = "http://localhost:8000";

// State
let currentTaskId = null;

// UI Elements
const els = {
    topic: document.getElementById('topicInput'),
    papers: document.getElementById('papersRange'),
    topN: document.getElementById('topRange'),
    autoCluster: document.getElementById('autoCluster'),
    genBullets: document.getElementById('genBullets'),
    file: document.getElementById('csvUpload'),

    statusBar: document.getElementById('statusBar'),
    statusText: document.getElementById('statusText'),
    progressBar: document.getElementById('progressBar'),
    statusPercent: document.getElementById('statusPercent'),

    resultsGrid: document.getElementById('resultsGrid'),
    btnExportPdf: document.getElementById('btnExportPdf'),
    btnExportCsv: document.getElementById('btnExportCsv')
};

// Helper: Update Status UI
function updateStatus(percent, message, visible = true) {
    if (visible) els.statusBar.classList.add('visible');
    els.progressBar.style.width = `${percent}%`;
    els.statusPercent.innerText = `${percent}%`;
    if (message) els.statusText.innerText = message;
}

// Helper: Create Result Card HTML
function createCard(paper, keyPoints = null) {
    let keyPointsHtml = '';
    if (keyPoints && typeof keyPoints === 'string') {
        // Parse bullets if they are a single string or array
        // The backend returns a single string with newlines/dashes usually, or we might clean it up.
        // Let's assume it's a string that needs splitting.
        const points = keyPoints.split('\n')
            .map(p => p.trim())
            .filter(p => p.length > 0)
            .map(p => p.replace(/^[•-]\s*/, '')); // Remove existing bullets

        if (points.length > 0) {
            keyPointsHtml = `
            <div class="key-points-section">
                <h4 class="kp-title"><i class="fas fa-lightbulb"></i> Key Insights</h4>
                <ul class="kp-list">
                    ${points.map(p => `<li class="kp-item"><i class="fas fa-check-circle kp-icon"></i><span>${p}</span></li>`).join('')}
                </ul>
            </div>
            `;
        }
    }

    return `
    <div class="result-card">
        <div class="card-header">
            <h3 class="card-title">${paper.title}</h3>
            <span class="relevance-badge">${(paper.relevance * 100).toFixed(0)}% Match</span>
        </div>
        <div class="card-meta">
            <span class="meta-item"><i class="fas fa-user-friends"></i> ${paper.authors || 'Unknown'}</span>
            <span class="meta-item"><i class="fas fa-calendar"></i> ${paper.published || 'N/A'}</span>
        </div>
        <div class="card-abstract">${paper.abstract}</div>
        ${keyPointsHtml}
        <div class="card-actions">
            <a href="${paper.url}" target="_blank" class="read-link">
                Read Paper <i class="fas fa-external-link-alt"></i>
            </a>
        </div>
    </div>
    `;
}

// Main Job Function
window.startJob = async function () {
    const topic = els.topic.value.trim();
    if (!topic) {
        alert("Please enter a research topic.");
        return;
    }

    // Reset UI
    els.resultsGrid.innerHTML = '';
    updateStatus(0, "Starting...", true);
    els.btnExportPdf.disabled = true;
    els.btnExportCsv.disabled = true;

    // Prepare Payload
    const payload = {
        topic: topic,
        max_papers: parseInt(els.papers.value),
        top_n: parseInt(els.topN.value),
        auto_cluster: els.autoCluster.checked,
        generate_bullets: els.genBullets.checked
    };

    try {
        // 1. Start Job
        const res = await fetch(`${API_BASE}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("Failed to start job");
        const data = await res.json();
        currentTaskId = data.task_id;

        // 2. Connect SSE
        const evtSource = new EventSource(`${API_BASE}/events/${currentTaskId}`);

        evtSource.onmessage = function (event) {
            const msg = JSON.parse(event.data);

            // Update Progress
            updateStatus(msg.progress, msg.stage);

            // Render Partial Results if available
            if (msg.partial_top && msg.partial_top.length > 0 && els.resultsGrid.children.length === 0) {
                els.resultsGrid.innerHTML = msg.partial_top.map(p => createCard(p)).join('');
            }

            // Done?
            if (msg.status === 'done') {
                evtSource.close();
                finishJob();
            } else if (msg.status === 'error') {
                evtSource.close();
                updateStatus(100, "Error occurred");
                alert("Job failed: " + (msg.messages ? msg.messages.join(', ') : "Unknown error"));
            }
        };

        evtSource.onerror = function (err) {
            console.error("SSE Error:", err);
            evtSource.close();
        };

    } catch (e) {
        console.error(e);
        alert("Error starting job: " + e.message);
        updateStatus(0, "Error", false);
    }
};

async function finishJob() {
    updateStatus(100, "Complete!");

    try {
        const res = await fetch(`${API_BASE}/results/${currentTaskId}`);
        const data = await res.json();

        // Render Final Results (sorted by relevance)
        if (data.papers_df) {
            const perpaper = data.perpaper || {};
            els.resultsGrid.innerHTML = data.papers_df
                .sort((a, b) => b.relevance - a.relevance)
                .map(paper => createCard(paper, perpaper[paper.id]))
                .join('');
        }

        // Enable Exports
        els.btnExportPdf.disabled = false;
        els.btnExportCsv.disabled = false;

        els.btnExportPdf.onclick = () => window.open(`${API_BASE}/export/${currentTaskId}/pdf`, '_blank');
        els.btnExportCsv.onclick = () => window.open(`${API_BASE}/export/${currentTaskId}/csv`, '_blank');

    } catch (e) {
        console.error("Error fetching final results:", e);
    }
}
