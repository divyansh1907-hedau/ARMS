// ===================== State =====================
let currentProjectId = null;
let currentProjectTitle = '';
let subjects = [];
let students = [];
let metaFields = [];
let lastComputedRows = [];
let lastStats = null;
let currentChartType = 'bar';
let currentChartInstance = null;

const TEMPLATES = {
  basic: {
    title: 'Basic School Grades',
    subjects: [
      { name: 'English', max_marks: 100, weight: 1.0 },
      { name: 'Mathematics', max_marks: 100, weight: 1.0 },
      { name: 'Science', max_marks: 100, weight: 1.0 },
    ],
  },
  college: {
    title: 'College Transcript',
    subjects: [
      { name: 'Core Subject 1', max_marks: 100, weight: 1.0 },
      { name: 'Core Subject 2', max_marks: 100, weight: 1.0 },
      { name: 'Elective', max_marks: 100, weight: 1.0 },
      { name: 'Lab / Practical', max_marks: 50, weight: 0.5 },
    ],
  },
  unit_test: {
    title: 'Unit Test Results',
    subjects: [
      { name: 'Unit Test', max_marks: 25, weight: 1.0 },
    ],
  },
};

// ===================== View switching =====================
function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById('view-' + name)?.classList.add('active');
  // Keep sidebar pills in sync with the visible view
  document.querySelectorAll('[data-nav]').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.nav === name));
}

function slugify(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') +
    '-' + Date.now().toString(36).slice(-5);
}

// Escape user-entered values before injecting into generated markup.
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function gradeBadgeClass(pct) {
  if (pct === null || pct === undefined) return 'badge-ghost';
  if (pct < 40) return 'badge-soft-error';
  if (pct < 60) return 'badge-soft-warning';
  return 'badge-soft-success';
}

const BTN_GRAD = 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white border-none shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30';

// ===================== Home view actions =====================
async function openProject(projectId) {
  const res = await fetch(`/api/project/${projectId}`);
  if (!res.ok) return alert('Could not load project');
  const data = await res.json();
  currentProjectId = projectId;
  currentProjectTitle = data.title || projectId;
  subjects = data.subjects || [];
  students = data.students || [];
  metaFields = data.meta_fields || [];
  renderTable();
  showView('sheet');
}

async function deleteProject(projectId) {
  if (!confirm(`Delete project "${projectId}"?\n\nThis permanently removes the marksheet. Results already published to student portals are NOT affected.`)) return;
  const res = await fetch(`/api/project/${encodeURIComponent(projectId)}`, { method: 'DELETE' });
  if (!res.ok) return alert('Could not delete the project.');
  location.reload(); // re-render the server-side project list without the deleted entry
}

function useTemplate(key) {
  const tpl = TEMPLATES[key];
  currentProjectTitle = tpl.title + ' - ' + new Date().toLocaleDateString();
  currentProjectId = slugify(tpl.title);
  subjects = JSON.parse(JSON.stringify(tpl.subjects));
  students = [];
  metaFields = [];
  renderTable();
  saveSheet();
  showView('sheet');
}

async function importFromHome() {
  const fileInput = document.getElementById('home-import-file');
  if (!fileInput.files.length) return;
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const res = await fetch('/api/import/sheet', { method: 'POST', body: formData });
  const data = await res.json();
  if (data.error) return alert(data.error);
  currentProjectTitle = 'Imported Sheet - ' + new Date().toLocaleDateString();
  currentProjectId = slugify('imported-sheet');
  subjects = data.subjects;
  students = data.students;
  metaFields = [];
  renderTable();
  saveSheet();
  showView('sheet');
}

// ===================== Custom Blank Sheet modal =====================
function openBlankSheetModal() {
  document.getElementById('blank-sheet-modal').classList.add('open');
}
function closeBlankSheetModal() {
  document.getElementById('blank-sheet-modal').classList.remove('open');
}
function createBlankSheet() {
  const checked = Array.from(document.querySelectorAll('#blank-sheet-modal input[type=checkbox]'))
    .filter(cb => cb.checked).map(cb => cb.value);
  metaFields = checked.filter(v => v !== 'Student Name' && v !== 'College Id');
  currentProjectTitle = 'New Sheet - ' + new Date().toLocaleDateString();
  currentProjectId = slugify('new-sheet');
  subjects = [];
  students = [];
  closeBlankSheetModal();
  renderTable();
  showView('sheet');
}

// ===================== Detect Students modal =====================
function openDetectStudents() {
  document.getElementById('detect-modal').classList.add('open');
}
function closeDetectModal() {
  document.getElementById('detect-modal').classList.remove('open');
}
function runDetectStudents() {
  const raw = document.getElementById('detect-textarea').value.trim();
  if (!raw) return closeDetectModal();
  const rows = raw.split('\n').map(r => r.split(/\t|,/).map(c => c.trim())).filter(r => r.length > 1);
  if (!rows.length) return alert('No rows detected.');

  // Heuristic: first row could be a header if it contains non-numeric text matching known keywords
  let header = rows[0];
  let dataRows = rows;
  const looksLikeHeader = header.some(h => /id|roll|name|subject/i.test(h));
  if (looksLikeHeader) dataRows = rows.slice(1);
  else header = null;

  const detected = [];
  dataRows.forEach((r, idx) => {
    const student = { student_id: r[0] || `AUTO${idx + 1}`, name: r[1] || `Student ${idx + 1}`, marks: {} };
    for (let i = 2; i < r.length; i++) {
      const subjName = header && header[i] ? header[i] : `Subject ${i - 1}`;
      student.marks[subjName] = parseFloat(r[i]) || 0;
      if (!subjects.find(s => s.name === subjName)) {
        subjects.push({ name: subjName, max_marks: 100, weight: 1.0 });
      }
    }
    detected.push(student);
  });

  students = students.concat(detected);
  closeDetectModal();
  document.getElementById('detect-textarea').value = '';
  renderTable();
  alert(`Detected and imported ${detected.length} student rows.`);
}

// ===================== Sheet editor =====================
function renderTable() {
  const table = document.getElementById('sheet-table');
  let html = '<thead><tr><th>Student ID</th><th>Name</th>';
  metaFields.forEach(f => html += `<th>${esc(f)}</th>`);
  html += '<th>Attendance %</th>';
  subjects.forEach(s => html += `<th>${esc(s.name)} (${s.max_marks})</th>`);
  html += '<th></th></tr></thead><tbody>';

  students.forEach((stu, rowIdx) => {
    html += `<tr>
      <td><input class="input input-bordered input-xs w-full min-w-[7rem]" value="${esc(stu.student_id || '')}" onchange="updateStudentField(${rowIdx},'student_id',this.value)"></td>
      <td><input class="input input-bordered input-xs w-full min-w-[8rem]" value="${esc(stu.name || '')}" onchange="updateStudentField(${rowIdx},'name',this.value)"></td>`;
    metaFields.forEach(f => {
      const val = (stu.meta && stu.meta[f]) || '';
      html += `<td><input class="input input-bordered input-xs w-full min-w-[7rem]" value="${esc(val)}" onchange="updateMeta(${rowIdx},'${f}',this.value)"></td>`;
    });
    const attVal = stu.attendance !== undefined && stu.attendance !== null ? stu.attendance : '';
    html += `<td><input class="input input-bordered input-xs attendance-input w-20" type="number" min="0" max="100" value="${attVal}" onchange="updateAttendance(${rowIdx},this.value)"></td>`;
    subjects.forEach(s => {
      const val = (stu.marks && stu.marks[s.name] !== undefined) ? stu.marks[s.name] : '';
      html += `<td><input type="number" class="input input-bordered input-xs w-20" value="${val}" onchange="updateMark(${rowIdx},'${s.name}',this.value)"></td>`;
    });
    html += `<td><button class="btn btn-ghost btn-xs text-error" onclick="removeStudentRow(${rowIdx})">✕</button></td></tr>`;
  });
  html += '</tbody>';
  table.innerHTML = html;
}

function updateAttendance(idx, value) {
  students[idx].attendance = value === '' ? null : parseFloat(value);
}

function updateStudentField(idx, field, value) { students[idx][field] = value; }
function updateMeta(idx, field, value) {
  if (!students[idx].meta) students[idx].meta = {};
  students[idx].meta[field] = value;
}
function updateMark(idx, subjectName, value) {
  if (!students[idx].marks) students[idx].marks = {};
  students[idx].marks[subjectName] = value;
}

function addSubject() {
  const name = document.getElementById('subject-name').value.trim();
  const max = parseFloat(document.getElementById('subject-max').value) || 100;
  if (!name) return;
  subjects.push({ name, max_marks: max, weight: 1.0 });
  document.getElementById('subject-name').value = '';
  renderTable();
}

function addStudentRow() {
  students.push({ student_id: '', name: '', marks: {}, meta: {} });
  renderTable();
}

function removeStudentRow(idx) {
  students.splice(idx, 1);
  renderTable();
}

async function saveSheet() {
  if (!currentProjectId) return alert('Create or open a project first');
  const payload = {
    title: currentProjectTitle || currentProjectId,
    session: 'default-session',
    subjects, students, meta_fields: metaFields,
  };
  const res = await fetch(`/api/project/${currentProjectId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  // Re-render an open report preview so the graph tracks sheet edits
  if (currentChartInstance) {
    const sel = document.getElementById('report-student-select');
    const fresh = sel && (data.computed || []).find(r => r.student_id === sel.value);
    if (fresh && document.getElementById('report-chart')) renderChart(fresh);
  }
  const issuesEl = document.getElementById('issues');
  if ((data.issues || []).length) {
    issuesEl.innerHTML =
      `<div role="alert" class="alert alert-warning mt-3 py-2 text-sm"><span>${data.issues.map(esc).join(' &nbsp;•&nbsp; ')}</span></div>`;
  } else {
    issuesEl.innerHTML = '';
  }
  lastComputedRows = data.computed || [];
  lastStats = data.stats;
  renderStats(data.stats);
  renderAtRisk(data.at_risk || []);
  return data;
}

function renderAtRisk(list) {
  const box = document.getElementById('at-risk-list');
  if (!box) return;
  if (!list.length) {
    box.innerHTML = '<p class="rounded-lg bg-success/10 px-3 py-2 text-sm text-success">No students currently flagged as at-risk.</p>';
    return;
  }
  box.innerHTML = list.map(s => {
    const badge = s.risk_level === 'High' ? 'badge-soft-error' : s.risk_level === 'Medium' ? 'badge-soft-warning' : 'badge-soft-success';
    return `
      <div class="flex items-center justify-between gap-2 rounded-lg bg-base-200/60 px-3 py-2">
        <span class="truncate text-sm font-medium">${esc(s.name)} <span class="ml-1 text-xs font-normal opacity-60">${esc(s.student_id)}</span></span>
        <span class="badge badge-sm shrink-0 font-semibold ${badge}">${s.risk_level} · ${s.risk_score}</span>
      </div>`;
  }).join('');
}

function renderStats(stats) {
  if (!stats) return;
  const tile = (label, value) =>
    `<div class="stat px-3 py-2"><div class="stat-title text-xs">${label}</div><div class="stat-value text-lg">${value}</div></div>`;
  document.getElementById('stats').innerHTML = `
    <div class="stats stats-vertical bg-base-200/60 sm:stats-horizontal">
      ${tile('Mean', `${stats.mean}%`)}
      ${tile('Median', `${stats.median}%`)}
      ${tile('Std Dev', stats.std_dev)}
      ${tile('Highest', `${stats.highest}%`)}
      ${tile('Lowest', `${stats.lowest}%`)}
    </div>`;
}

// ===================== Advanced Calculations panel =====================
const FUNCTIONS = {
  aggregate: [
    { name: 'Total', desc: 'Sum of all subject marks for each student.' },
    { name: 'Class Average', desc: 'Mean percentage across the whole class. Example: 72.4%' },
    { name: 'Highest Score', desc: 'Highest overall percentage in the class.' },
    { name: 'Lowest Score', desc: 'Lowest overall percentage in the class.' },
  ],
  grading: [
    { name: 'Letter Grade', desc: 'Converts each percentage into a letter grade (A+ to F).' },
    { name: 'GPA', desc: 'Weighted grade-point average per student, on a 10-point scale.' },
  ],
  ranking: [
    { name: 'Rank', desc: 'Class rank based on overall percentage, highest first.' },
    { name: 'Percentile', desc: 'Percentage of classmates a student scored above.' },
  ],
};

function populateFunctions() {
  const type = document.getElementById('func-type').value;
  const funcSelect = document.getElementById('func-name');
  funcSelect.innerHTML = '<option value="">Choose function...</option>';
  (FUNCTIONS[type] || []).forEach(f => {
    const opt = document.createElement('option');
    opt.value = f.name;
    opt.textContent = f.name;
    funcSelect.appendChild(opt);
  });
  showFuncDesc();
}

function showFuncDesc() {
  const type = document.getElementById('func-type').value;
  const name = document.getElementById('func-name').value;
  const fn = (FUNCTIONS[type] || []).find(f => f.name === name);
  document.getElementById('func-desc').textContent = fn ? fn.desc : 'Select a function to see description and example.';
}

async function applyFunction() {
  const name = document.getElementById('func-name').value;
  if (!name) return alert('Choose a function first.');
  const data = await saveSheet();
  if (!data) return;
  const rows = data.computed;
  if (!rows || !rows.length) return alert('No students to calculate on yet.');

  let msg = '';
  if (name === 'Class Average') msg = `Class Average: ${data.stats.mean}%`;
  else if (name === 'Highest Score') msg = `Highest Score: ${data.stats.highest}%`;
  else if (name === 'Lowest Score') msg = `Lowest Score: ${data.stats.lowest}%`;
  else if (name === 'Total') msg = rows.map(r => `${r.name}: ${r.total_obtained}/${r.total_max}`).join('\n');
  else if (name === 'Letter Grade') msg = rows.map(r => `${r.name}: ${r.grade}`).join('\n');
  else if (name === 'GPA') msg = rows.map(r => `${r.name}: ${r.gpa}`).join('\n');
  else if (name === 'Rank') msg = rows.map(r => `#${r.rank} ${r.name}`).sort().join('\n');
  else if (name === 'Percentile') msg = rows.map(r => `${r.name}: ${r.percentile} percentile`).join('\n');

  alert(`${name}\n\n${msg}`);
}

// ===================== Report Generator =====================
async function goToReportGenerator() {
  const data = await saveSheet();
  if (!data) return;
  const select = document.getElementById('report-student-select');
  select.innerHTML = '';
  (data.computed || []).forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.student_id;
    opt.textContent = `${r.name} (${r.student_id})`;
    select.appendChild(opt);
  });
  showView('report');
}

function selectChartType(type) {
  currentChartType = type;
  document.querySelectorAll('.chart-type-btn').forEach(b => b.classList.toggle('active', b.dataset.type === type));
  // Live re-render: if a preview chart is already showing, redraw it in the new form
  if (currentChartInstance) {
    const row = findSelectedRow();
    if (row && document.getElementById('report-chart')) renderChart(row);
  }
}

function findSelectedRow() {
  const sid = document.getElementById('report-student-select').value;
  return lastComputedRows.find(r => r.student_id === sid);
}

async function generatePreview() {
  const row = findSelectedRow();
  if (!row) return alert('No student selected / no computed data. Save the sheet first.');

  const container = document.getElementById('report-card-container');
  const passed = row.percentage >= 40;
  const toneCls = passed ? 'text-success' : 'text-error';
  const attendanceHtml = (row.attendance !== null && row.attendance !== undefined)
    ? `<div class="rounded-lg bg-base-200/60 px-3 py-2">
         <div class="text-[11px] opacity-60">Attendance</div>
         <div class="text-base font-semibold ${row.attendance < 75 ? 'text-error' : ''}">${row.attendance}%</div>
       </div>`
    : '';

  let subjectRows = '';
  Object.entries(row.subjects).forEach(([name, s]) => {
    subjectRows += `<tr>
      <td>${esc(name)}</td>
      <td>${s.score}/${s.max_marks}</td>
      <td>${s.percentage}%</td>
      <td><span class="badge badge-sm font-semibold ${gradeBadgeClass(s.percentage)}">${s.grade}</span></td>
    </tr>`;
  });

  const tile = (label, value, cls = '') =>
    `<div class="rounded-lg bg-base-200/60 px-3 py-2">
       <div class="text-[11px] opacity-60">${label}</div>
       <div class="text-base font-semibold ${cls}">${value}</div>
     </div>`;

  container.innerHTML = `
    <div class="rounded-2xl border border-base-300 bg-base-100 p-6 shadow-sm">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="flex items-center gap-3">
          <span class="flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 text-lg font-extrabold text-primary">${esc((row.name || '?').charAt(0).toUpperCase())}</span>
          <div>
            <div class="font-bold">${esc(row.name)}</div>
            <div class="text-xs opacity-60">${esc(row.student_id)} · ${esc(currentProjectTitle || 'Report Card')}</div>
          </div>
        </div>
        <span class="badge badge-lg font-bold ${gradeBadgeClass(row.percentage)}">${row.grade}</span>
      </div>

      <div class="mt-4 overflow-x-auto rounded-xl border border-base-300">
        <table class="table table-sm">
          <thead><tr><th>Subject</th><th>Marks</th><th>%</th><th>Grade</th></tr></thead>
          <tbody>${subjectRows}</tbody>
        </table>
      </div>

      <div class="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
        ${tile('Total Score', `${row.total_obtained}/${row.total_max}`)}
        ${tile('Percentage', `${row.percentage}%`)}
        ${tile('GPA', row.gpa)}
        ${tile('Class Rank', `#${row.rank}`)}
        ${tile('Status', passed ? 'Pass' : 'Fail', toneCls)}
        ${attendanceHtml}
      </div>

      <canvas id="report-chart" class="mt-4" height="140"></canvas>

      <div class="insights-box mt-4 rounded-xl bg-base-200/70 p-4 text-sm leading-relaxed" id="insights-box">Loading insights...</div>
    </div>
  `;

  renderChart(row);

  const res = await fetch('/api/result/insights', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(row),
  });
  const insights = await res.json();
  document.getElementById('insights-box').innerHTML =
    `<div class="mb-1 flex items-center gap-1.5 font-semibold">💡 Performance Insights</div>` +
    insights.highlights.map(h => `<p>${esc(h)}</p>`).join('') +
    `<p class="mt-1 opacity-80">${esc(insights.summary)}</p>`;
}

function renderChart(row) {
  const ctx = document.getElementById('report-chart');
  if (!ctx || !window.Chart) return;
  applyChartTheme();
  if (currentChartInstance) currentChartInstance.destroy();
  const v = armsViz();
  const labels = Object.keys(row.subjects);
  const scores = labels.map(l => row.subjects[l].score);
  const maxes = labels.map(l => row.subjects[l].max_marks);

  if (currentChartType === 'pie') {
    // Fixed categorical order (validated palette); >8 subjects fold onto the last slot.
    const palette = labels.slice(0, v.cat.length).map((_, i) => v.cat[i]);
    while (palette.length < labels.length) palette.push(v.cat[v.cat.length - 1]);
    currentChartInstance = new Chart(ctx, {
      type: 'pie',
      data: {
        labels,
        datasets: [{ data: scores, backgroundColor: palette, borderColor: v.surface, borderWidth: 2 }],
      },
      options: { responsive: true, plugins: { legend: { position: 'right', labels: { boxWidth: 10, boxHeight: 10 } } } },
    });
    return;
  }

  currentChartInstance = new Chart(ctx, {
    type: currentChartType,
    data: {
      labels,
      datasets: [
        { label: 'Score', data: scores, backgroundColor: v.series1, borderColor: v.series1,
          borderRadius: 4, borderSkipped: 'start', maxBarThickness: 24,
          tension: .3, pointRadius: 4, pointBackgroundColor: v.series1, pointBorderColor: v.surface, pointBorderWidth: 2 },
        { label: 'Max', data: maxes, backgroundColor: v.refGray, borderColor: v.refGray,
          borderRadius: 4, borderSkipped: 'start', maxBarThickness: 24,
          tension: .3, pointRadius: 4, pointBackgroundColor: v.refGray, pointBorderColor: v.surface, pointBorderWidth: 2 },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10 } } },
      scales: {
        x: { grid: { display: false }, border: { color: v.grid } },
        y: { beginAtZero: true, grid: { color: v.grid }, border: { display: false } },
      },
    },
  });
}

async function downloadReportPdf() {
  const row = findSelectedRow();
  if (!row) return alert('Generate a preview first.');
  const res = await fetch('/api/pdf/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ row, project_title: currentProjectTitle }),
  });
  const blob = await res.blob();
  triggerDownload(blob, `${row.student_id}_report.pdf`);
}

async function downloadReportExcel() {
  if (!lastComputedRows.length) return alert('Save the sheet first.');
  const res = await fetch('/api/export/sheet', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: lastComputedRows, format: 'xlsx' }),
  });
  const blob = await res.blob();
  triggerDownload(blob, 'results_export.xlsx');
}

async function summarizeResults() {
  const res = await fetch('/api/result/summarize', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subjects, students }),
  });
  const data = await res.json();
  alert('Class Summary:\n\n' + data.summary);
}

async function generateAllStudents() {
  if (!lastComputedRows.length) return alert('Save the sheet first.');
  const res = await fetch('/api/pdf/preview-bulk', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: lastComputedRows, project_title: currentProjectTitle }),
  });
  const blob = await res.blob();
  triggerDownload(blob, `${currentProjectTitle || 'all'}_reports.pdf`);
}

async function uploadToDatabase() {
  const sessionName = document.getElementById('db-session-name').value.trim() || 'default-session';
  const examName = document.getElementById('db-exam-name').value.trim() || currentProjectId;
  const res = await fetch('/api/result/publish', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session: sessionName, exam_name: examName, subjects, students }),
  });
  const data = await res.json();
  alert(`Uploaded results for ${data.published} students to the database.`);
}

function triggerDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  window.URL.revokeObjectURL(url);
}

// ===================== Academic Records (transcript) =====================
let transcriptChartInstance = null;

function openTranscriptSearch() {
  document.getElementById('transcript-search-modal').classList.add('open');
}
function closeTranscriptSearch() {
  document.getElementById('transcript-search-modal').classList.remove('open');
}

async function loadTranscript() {
  const collegeId = document.getElementById('transcript-search-id').value.trim();
  if (!collegeId) return alert('Enter a College ID.');
  const res = await fetch(`/api/student/${collegeId}/transcript`);
  if (!res.ok) {
    alert('No student found with that College ID.');
    return;
  }
  const data = await res.json();
  closeTranscriptSearch();
  renderTranscript(data, collegeId);
  showView('transcript');
}

function renderTranscript(data, collegeId) {
  document.getElementById('transcript-crumb').textContent =
    `Academic Record: ${data.student.name || collegeId}`;

  const container = document.getElementById('transcript-container');
  if (!data.semesters.length) {
    container.innerHTML = `<p class="py-10 text-center text-sm opacity-60">No results recorded yet for ${esc(data.student.name || collegeId)}.</p>`;
    return;
  }

  let rows = '';
  data.semesters.forEach(sem => {
    sem.exams.forEach(exam => {
      const attOk = exam.attendance !== null && exam.attendance !== undefined;
      rows += `<tr>
        <td>${esc(sem.session_name)}</td>
        <td>${esc(exam.exam_name)}</td>
        <td>${exam.percentage}%</td>
        <td><span class="badge badge-sm font-semibold ${gradeBadgeClass(exam.percentage)}">${exam.grade}</span></td>
        <td>${exam.gpa}</td>
        <td class="${attOk && exam.attendance < 75 ? 'font-semibold text-error' : ''}">${attOk ? exam.attendance + '%' : '-'}</td>
      </tr>`;
    });
  });

  container.innerHTML = `
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold tracking-tight">${esc(data.student.name)} <span class="ml-1 text-sm font-normal opacity-60">(${esc(data.student.college_id)})</span></h2>
        <p class="mt-0.5 text-sm opacity-60">Consolidated across ${data.total_semesters} semester(s)</p>
      </div>
      <div class="rounded-xl bg-primary/10 px-4 py-2 text-center">
        <div class="text-[11px] font-semibold uppercase tracking-wide text-primary opacity-80">CGPA</div>
        <div class="text-2xl font-extrabold text-primary">${data.cgpa}</div>
      </div>
    </div>

    <canvas id="transcript-chart" class="mt-4" height="90"></canvas>

    <div class="mt-4 overflow-x-auto rounded-xl border border-base-300">
      <table class="table table-sm table-zebra">
        <thead><tr><th>Semester</th><th>Exam</th><th>%</th><th>Grade</th><th>GPA</th><th>Attendance</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>

    <a class="btn btn-outline btn-sm mt-4" href="/api/pdf/transcript/${encodeURIComponent(data.student.college_id)}">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Download Full Transcript (PDF)
    </a>
  `;

  renderTranscriptChart(data);
}

// Chart construction is isolated from renderTranscript so a CDN failure
// can never break the transcript table or the view switch again.
function renderTranscriptChart(data) {
  if (!window.Chart) return;
  applyChartTheme();
  const v = armsViz();
  if (transcriptChartInstance) transcriptChartInstance.destroy();
  transcriptChartInstance = new Chart(document.getElementById('transcript-chart'), {
    type: 'line',
    data: {
      labels: data.semesters.map(s => s.session_name),
      datasets: [{
        label: 'GPA per Semester',
        data: data.semesters.map(s => s.gpa),
        borderColor: v.series1, backgroundColor: hexAlpha(v.series1, .1), fill: true, tension: 0.3,
        borderWidth: 2, pointRadius: 4, pointBackgroundColor: v.series1,
        pointBorderColor: v.surface, pointBorderWidth: 2,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 10, grid: { color: v.grid }, border: { display: false } },
        x: { grid: { display: false }, border: { color: v.grid } },
      }
    },
  });
}

// ===================== AI Assistant widget =====================
function toggleAiWidget() {
  document.getElementById('ai-widget').classList.toggle('open');
}

function appendChat(who, text) {
  const log = document.getElementById('chat-log');
  const div = document.createElement('div');
  div.className = who === 'You' ? 'me' : 'bot';
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function sendTeacherChat() {
  const input = document.getElementById('chat-input');
  const question = input.value.trim();
  if (!question) return;
  appendChat('You', question);
  input.value = '';
  const res = await fetch('/api/chatbot/teacher', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }),
  });
  const data = await res.json();
  appendChat('Edu-AI', data.reply || data.error || 'No response.');
}

document.getElementById('chat-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') sendTeacherChat();
});
