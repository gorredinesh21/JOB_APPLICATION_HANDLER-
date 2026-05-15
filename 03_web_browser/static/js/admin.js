let selectedRunId = null;
let runPollTimer = null;
let dbOffset = 0;
const dbLimit = 50;

document.addEventListener('DOMContentLoaded', () => {
    setDefaultPipelineDates();

    document.querySelectorAll('.stage-button').forEach((button) => {
        button.addEventListener('click', () => runStage(button.dataset.stage));
    });

    document.getElementById('refresh-runs-btn').addEventListener('click', loadRuns);
    document.getElementById('db-apply-btn').addEventListener('click', () => {
        dbOffset = 0;
        loadDbRows();
    });
    document.getElementById('db-prev-btn').addEventListener('click', () => {
        dbOffset = Math.max(0, dbOffset - dbLimit);
        loadDbRows();
    });
    document.getElementById('db-next-btn').addEventListener('click', () => {
        dbOffset += dbLimit;
        loadDbRows();
    });

    document.getElementById('db-search').addEventListener('input', debounce(() => {
        dbOffset = 0;
        loadDbRows();
    }, 300));

    loadRuns();
    loadDbRows();
    runPollTimer = setInterval(() => {
        loadRuns();
        if (selectedRunId) {
            loadRunDetail(selectedRunId);
        }
    }, 2500);
});

async function runStage(stage) {
    setStageButtons(false);
    const startDate = document.getElementById('pipeline-start-date').value;
    const endDate = document.getElementById('pipeline-end-date').value || startDate;

    try {
        const response = await fetch('/api/admin/pipeline/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stage,
                start_date: startDate,
                end_date: endDate
            })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to start run');
        }

        selectedRunId = data.id;
        await loadRuns();
        await loadRunDetail(selectedRunId);
    } catch (error) {
        setLogText(`Error: ${error.message}`);
    } finally {
        setStageButtons(true);
    }
}

function setDefaultPipelineDates() {
    const today = new Date().toISOString().slice(0, 10);
    document.getElementById('pipeline-start-date').value = today;
    document.getElementById('pipeline-end-date').value = today;
}

async function loadRuns() {
    const response = await fetch('/api/admin/pipeline/runs');
    const data = await response.json();
    renderRuns(data.runs || []);
}

function renderRuns(runs) {
    const container = document.getElementById('run-list');
    if (!runs.length) {
        container.innerHTML = '<div class="muted-panel">No runs yet.</div>';
        return;
    }

    container.innerHTML = runs.map((run) => {
        const active = run.id === selectedRunId ? ' active' : '';
        return `
            <button class="run-item${active}" data-run-id="${escapeHtml(run.id)}">
                <span>
                    <strong>${escapeHtml(run.label)}</strong>
                    <small>${escapeHtml(run.started_at || 'Queued')}</small>
                </span>
                <span class="status-pill status-${escapeHtml(run.status)}">${escapeHtml(run.status)}</span>
            </button>
        `;
    }).join('');

    container.querySelectorAll('.run-item').forEach((item) => {
        item.addEventListener('click', () => {
            selectedRunId = item.dataset.runId;
            loadRunDetail(selectedRunId);
            renderRuns(runs);
        });
    });

    if (!selectedRunId && runs[0]) {
        selectedRunId = runs[0].id;
        loadRunDetail(selectedRunId);
    }
}

async function loadRunDetail(runId) {
    const response = await fetch(`/api/admin/pipeline/runs/${encodeURIComponent(runId)}`);
    if (!response.ok) {
        return;
    }

    const run = await response.json();
    document.getElementById('selected-run-label').textContent = `${run.label} · ${run.status}`;
    setLogText((run.logs || run.log_tail || []).join('\n') || 'No log output yet.');
}

function setLogText(text) {
    const log = document.getElementById('run-log');
    log.textContent = text;
    log.scrollTop = log.scrollHeight;
}

async function loadDbRows() {
    const params = new URLSearchParams({
        limit: String(dbLimit),
        offset: String(dbOffset)
    });

    const search = document.getElementById('db-search').value.trim();
    const source = document.getElementById('db-source').value;
    const resume = document.getElementById('db-resume').value;
    const minScore = document.getElementById('db-min-score').value;
    const maxScore = document.getElementById('db-max-score').value;

    if (search) params.set('search', search);
    if (source) params.set('source', source);
    if (resume) params.set('resume', resume);
    if (minScore) params.set('min_score', minScore);
    if (maxScore) params.set('max_score', maxScore);

    const response = await fetch(`/api/admin/jobs?${params.toString()}`);
    const data = await response.json();
    renderSourceOptions(data.sources || [], source);
    renderDbRows(data.jobs || [], data.total || 0);
}

function renderSourceOptions(sources, selected) {
    const select = document.getElementById('db-source');
    const options = ['<option value="">All Sources</option>'].concat(
        sources.map((source) => `<option value="${escapeHtml(source)}">${escapeHtml(source)}</option>`)
    );
    select.innerHTML = options.join('');
    select.value = selected;
}

function renderDbRows(jobs, total) {
    const body = document.getElementById('db-table-body');
    document.getElementById('db-count').textContent = `${total} rows`;
    document.getElementById('db-page-label').textContent = `Rows ${dbOffset + 1}-${dbOffset + jobs.length}`;
    document.getElementById('db-prev-btn').disabled = dbOffset === 0;
    document.getElementById('db-next-btn').disabled = dbOffset + dbLimit >= total;

    if (!jobs.length) {
        body.innerHTML = '<tr><td colspan="7" class="text-center">No matching jobs.</td></tr>';
        return;
    }

    body.innerHTML = jobs.map((job) => {
        const jobId = encodeURIComponent(job.job_unique_id || '');
        const score = job.score ?? 'N/A';
        return `
            <tr>
                <td><span class="score-mini">${escapeHtml(score)}</span></td>
                <td>
                    <strong>${escapeHtml(job.job_title || 'Untitled')}</strong>
                    <div class="table-subtext">${escapeHtml(job.location || 'Not specified')}</div>
                </td>
                <td>${escapeHtml(job.company_name || 'Unknown')}</td>
                <td>${escapeHtml(job.source || 'Unknown')}</td>
                <td>${escapeHtml(job.fetched_at || job.published_date || '-')}</td>
                <td>${job.resume_exists ? '<span class="status-pill status-completed">ready</span>' : '<span class="status-pill status-queued">missing</span>'}</td>
                <td><a class="btn btn-sm btn-outline-light" href="/job/${jobId}">Open</a></td>
            </tr>
        `;
    }).join('');
}

function setStageButtons(enabled) {
    document.querySelectorAll('.stage-button').forEach((button) => {
        button.disabled = !enabled;
    });
}

function debounce(func, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
