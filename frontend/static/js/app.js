/* ApexView — app.js */
'use strict';

// ---------------------------------------------------------------
// State
// ---------------------------------------------------------------
const state = {
  file: null,
  angle: 30,
  outW: 800,
  outH: 600,
  mode: 'auto',
  corners: [],        // [{x, y}, ...]
  jobId: null,
  pollTimer: null,
  previewSrc: null,   // object URL for original
};

const API = '';   // same origin; change to http://localhost:8000 for dev

// ---------------------------------------------------------------
// Init
// ---------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  bindDrop();
  bindAngleSelector();
  bindResSelector();
  bindCornerCanvas();
  checkApi();
  document.getElementById('custom-angle-slider').addEventListener('input', e => {
    state.angle = parseFloat(e.target.value);
    document.getElementById('custom-angle-val').textContent = state.angle + '°';
  });
  document.getElementById('remove-btn').addEventListener('click', e => {
    e.stopPropagation();
    clearFile();
  });
});

// ---------------------------------------------------------------
// API health
// ---------------------------------------------------------------
async function checkApi() {
  const dot = document.getElementById('api-dot');
  try {
    const r = await fetch(`${API}/api/status/ping`);
    // any response from server = alive (404 is fine)
    dot.classList.add('online');
  } catch {
    dot.classList.add('error');
  }
}

// ---------------------------------------------------------------
// File handling
// ---------------------------------------------------------------
function bindDrop() {
  const zone = document.getElementById('drop-zone');
  const input = document.getElementById('file-input');

  zone.addEventListener('click', () => {
    if (!state.file) input.click();
  });
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  });
  input.addEventListener('change', () => {
    if (input.files[0]) setFile(input.files[0]);
  });
}

function setFile(f) {
  state.file = f;
  state.previewSrc = URL.createObjectURL(f);

  document.getElementById('drop-inner').style.display = 'none';
  const sel = document.getElementById('file-selected');
  sel.style.display = 'flex';
  document.getElementById('file-name').textContent = f.name;
  document.getElementById('file-meta').textContent =
    `${(f.size / 1024 / 1024).toFixed(1)} MB · ${f.type || 'video'}`;

  const thumb = document.getElementById('file-thumb');
  thumb.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="3" width="20" height="18" rx="3"/><polygon points="9,8 17,12 9,16" fill="currentColor" stroke="none"/></svg>`;

  // Load preview frame for manual mode
  loadPreviewFrame();
  updateConvertBtn();
}

function clearFile() {
  state.file = null;
  state.corners = [];
  if (state.previewSrc) URL.revokeObjectURL(state.previewSrc);
  state.previewSrc = null;
  document.getElementById('drop-inner').style.display = 'flex';
  document.getElementById('file-selected').style.display = 'none';
  document.getElementById('file-input').value = '';
  updateConvertBtn();
  updateCornerList();
}

// ---------------------------------------------------------------
// Angle selector
// ---------------------------------------------------------------
function bindAngleSelector() {
  document.querySelectorAll('.angle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.angle-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const wrap = document.getElementById('custom-angle-wrap');
      if (btn.dataset.angle === 'custom') {
        wrap.style.display = 'flex';
        state.angle = parseFloat(document.getElementById('custom-angle-slider').value);
      } else {
        wrap.style.display = 'none';
        state.angle = parseFloat(btn.dataset.angle);
      }
    });
  });
}

// ---------------------------------------------------------------
// Resolution selector
// ---------------------------------------------------------------
function bindResSelector() {
  document.querySelectorAll('.res-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.res-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.outW = parseInt(btn.dataset.w);
      state.outH = parseInt(btn.dataset.h);
    });
  });
}

// ---------------------------------------------------------------
// Mode toggle
// ---------------------------------------------------------------
function setMode(m) {
  state.mode = m;
  document.getElementById('mode-auto').classList.toggle('active', m === 'auto');
  document.getElementById('mode-manual').classList.toggle('active', m === 'manual');
  document.getElementById('mode-badge').textContent = m === 'auto' ? 'Auto' : 'Manual';
  document.getElementById('corner-picker').style.display = m === 'manual' ? 'block' : 'none';
  if (m === 'manual') loadPreviewFrame();
}

// ---------------------------------------------------------------
// Manual corner picker
// ---------------------------------------------------------------
function bindCornerCanvas() {
  const canvas = document.getElementById('preview-canvas');
  canvas.addEventListener('click', e => {
    if (state.mode !== 'manual') return;
    if (state.corners.length >= 4) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width  / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top)  * scaleY);
    state.corners.push({ x, y });
    drawCorners();
    updateCornerList();
    updateConvertBtn();
  });
}

function loadPreviewFrame() {
  if (!state.previewSrc) return;
  const canvas = document.getElementById('preview-canvas');
  const video = document.createElement('video');
  video.src = state.previewSrc;
  video.muted = true;
  video.addEventListener('loadeddata', () => {
    video.currentTime = 0.5;
  });
  video.addEventListener('seeked', () => {
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    drawCorners();
  });
}

function drawCorners() {
  const canvas = document.getElementById('preview-canvas');
  const ctx = canvas.getContext('2d');
  // Redraw from video not to lose the image
  const video = document.createElement('video');
  video.src = state.previewSrc;
  video.muted = true;
  video.addEventListener('loadeddata', () => { video.currentTime = 0.5; });
  video.addEventListener('seeked', () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(video, 0, 0);

    const pts = state.corners;
    const colors = ['#00e5a0', '#f5a623', '#ff5f5f', '#5b8fff'];
    const labels = ['TL', 'TR', 'BR', 'BL'];

    if (pts.length >= 2) {
      ctx.strokeStyle = 'rgba(0,229,160,0.7)';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.beginPath();
      pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
      if (pts.length === 4) ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);
    }

    pts.forEach((p, i) => {
      ctx.fillStyle = colors[i];
      ctx.beginPath(); ctx.arc(p.x, p.y, 8, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#0a0b0d';
      ctx.font = 'bold 10px monospace';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(labels[i], p.x, p.y);
    });

    document.getElementById('corner-count').textContent = `${pts.length} / 4 corners`;
  });
}

function updateCornerList() {
  const list = document.getElementById('corner-list');
  const labels = ['TL', 'TR', 'BR', 'BL'];
  list.innerHTML = state.corners.map((p, i) =>
    `<span class="corner-item">${labels[i]} ${p.x},${p.y}</span>`
  ).join('');
}

function clearCorners() {
  state.corners = [];
  updateCornerList();
  document.getElementById('corner-count').textContent = '0 / 4 corners';
  loadPreviewFrame();
  updateConvertBtn();
}

// ---------------------------------------------------------------
// Convert button state
// ---------------------------------------------------------------
function updateConvertBtn() {
  const btn = document.getElementById('convert-btn');
  const hint = document.getElementById('action-hint');
  const ready = state.file &&
    (state.mode === 'auto' || (state.mode === 'manual' && state.corners.length === 4));
  btn.disabled = !ready;
  if (!state.file) {
    hint.textContent = 'Upload a video to get started';
  } else if (state.mode === 'manual' && state.corners.length < 4) {
    hint.textContent = `Click ${4 - state.corners.length} more corner(s) on the preview`;
  } else {
    hint.textContent = `Ready — ${state.outW}×${state.outH} @ ${state.angle}° elevation`;
  }
}

// ---------------------------------------------------------------
// Conversion
// ---------------------------------------------------------------
async function startConversion() {
  if (!state.file) return;

  const form = new FormData();
  form.append('file', state.file);
  form.append('angle', state.angle);
  form.append('output_width', state.outW);
  form.append('output_height', state.outH);
  form.append('corner_mode', state.mode);
  if (state.mode === 'manual' && state.corners.length === 4) {
    form.append('corners', JSON.stringify(state.corners.map(p => [p.x, p.y])));
  }

  showProgress();
  log('Uploading video…');

  try {
    const res = await fetch(`${API}/api/upload`, { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    const data = await res.json();
    state.jobId = data.job_id;
    document.getElementById('job-id-label').textContent = `JOB ${data.job_id}`;
    log(`Job created: ${data.job_id}`);
    pollJob();
  } catch (err) {
    logErr(`Upload error: ${err.message}`);
    setChip('error');
  }
}

function showProgress() {
  document.getElementById('progress-panel').style.display = 'block';
  document.getElementById('result-panel').style.display = 'none';
  document.getElementById('convert-btn').disabled = true;
  document.getElementById('progress-bar').style.width = '0%';
  setChip('queued');
}

function pollJob() {
  state.pollTimer = setInterval(async () => {
    if (!state.jobId) return;
    try {
      const res = await fetch(`${API}/api/status/${state.jobId}`);
      const data = await res.json();
      updateProgress(data);
      if (data.status === 'done') {
        clearInterval(state.pollTimer);
        showResult(data);
      } else if (data.status === 'error') {
        clearInterval(state.pollTimer);
        logErr(`Error: ${data.error_msg}`);
        setChip('error');
        document.getElementById('convert-btn').disabled = false;
      }
    } catch (e) {
      logErr('Poll error: ' + e.message);
    }
  }, 800);
}

function updateProgress(data) {
  const pct = Math.round(data.progress * 100);
  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('prog-pct').textContent = pct + '%';
  document.getElementById('prog-frames').textContent =
    `${data.processed_frames} / ${data.total_frames} frames`;
  document.getElementById('prog-fps').textContent =
    data.fps > 0 ? `${data.fps.toFixed(1)} fps` : '—';
  setChip(data.status);

  if (data.status === 'processing' && data.processed_frames % 30 === 0) {
    log(`Processing… ${pct}% (${data.processed_frames}/${data.total_frames} frames)`);
  }
}

function showResult(data) {
  log('✓ Processing complete!', 'ok');
  setChip('done');
  document.getElementById('progress-bar').style.width = '100%';

  const panel = document.getElementById('result-panel');
  panel.style.display = 'block';
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Original video
  const origVid = document.getElementById('orig-video');
  origVid.src = state.previewSrc;

  // Result video
  const resVid = document.getElementById('result-video');
  resVid.src = `${API}${data.output_url}`;
}

async function downloadResult() {
  window.location.href = `${API}/api/download/${state.jobId}`;
}

function resetApp() {
  clearInterval(state.pollTimer);
  clearFile();
  state.jobId = null;
  document.getElementById('progress-panel').style.display = 'none';
  document.getElementById('result-panel').style.display = 'none';
  document.getElementById('log-box').innerHTML = '';
  document.getElementById('convert-btn').disabled = true;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ---------------------------------------------------------------
// Log + chip helpers
// ---------------------------------------------------------------
function log(msg, cls = '') {
  const box = document.getElementById('log-box');
  const line = document.createElement('span');
  line.className = 'log-line' + (cls ? ' ' + cls : '');
  line.textContent = `> ${msg}`;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}
function logErr(msg) { log(msg, 'err'); }

function setChip(status) {
  const chip = document.getElementById('status-chip');
  chip.textContent = status;
  chip.className = `status-chip ${status}`;
  const prog = document.getElementById('progress-panel');
  prog.classList.toggle('processing', status === 'processing');
}
