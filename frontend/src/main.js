import './style.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const state = {
  mode: null, // null | 'plain' | 'matcher' — decided by whether a CV was uploaded on screen 1
  candidateProfile: null,
  results: [],
  runId: '',
  jobsById: {},
}

const SENIORITY_LEVELS = ['intern', 'junior', 'mid', 'senior', 'lead', 'manager', 'director', 'executive']

const app = document.querySelector('#app')

app.innerHTML = `
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">J</span><span>jobhunter</span></div>
      <div class="side-intro">
        <span class="eyebrow">PERSONAL SEARCH DESK</span>
        <h1>Find the work that fits.</h1>
        <p>Your CV, tuned searches, and the roles worth a closer look.</p>
      </div>
      <nav class="steps" aria-label="Search steps">
        <div class="step" id="step-1"><span>01</span><div><strong>Add your CV</strong><small>Optional, sharpens the match</small></div></div>
        <div class="step" id="step-2"><span>02</span><div><strong>Shape the search</strong><small>Filters for role or fit</small></div></div>
        <div class="step" id="step-3"><span>03</span><div><strong>Review matches</strong><small>Open roles ranked for you</small></div></div>
      </nav>
      <div class="side-note"><span class="status-dot"></span><span>Local workspace<br><small>Your data stays on this machine.</small></span></div>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <div><span class="eyebrow">SEARCH / NEW RUN</span><p class="date-line">Wednesday, September 2, 2026</p></div>
        <button class="icon-button" id="health-button" title="Check API status" aria-label="Check API status"><span class="pulse"></span>API status</button>
      </header>

      <div id="screen-upload">
        <section class="welcome-row"><div><h2>Add your CV<span class="accent">.</span></h2><p>Optional — skip it to search on role alone, or upload it to get ranked, explained matches.</p></div></section>

        <section class="workspace-grid single">
          <div class="panel profile-panel">
            <div class="panel-heading"><div><span class="section-number">01</span><h3>Upload your CV</h3></div><span class="panel-caption">OPTIONAL</span></div>
            <p class="panel-copy">We extract a full structured profile — work history, skills, education, languages — so a match can explain itself. Skip this to just search by role.</p>
            <div class="drop-zone" id="cm-drop-zone"><input type="file" id="cm-cv-file" accept=".pdf,.docx,.txt" hidden /><div class="upload-icon">↑</div><strong id="cm-file-label">Drop your CV here</strong><span>PDF, DOCX or TXT · max 5 MB</span><button class="outline-button" id="cm-choose-file">Choose file</button></div>
            <div class="profile-status" id="cm-upload-status" aria-live="polite"></div>

            <div class="cm-summary" id="cm-summary" hidden></div>
            <div id="cm-review" hidden>
              <label class="field-label" for="cm-profile-json">Extracted profile <span>editable JSON</span></label>
              <textarea id="cm-profile-json" class="json-editor" rows="10" placeholder="Upload a CV to see the extracted profile here."></textarea>
              <button class="outline-button" id="cm-save-json">Save changes</button>
              <div class="profile-status" id="cm-json-status" aria-live="polite"></div>
            </div>

            <div class="screen-actions">
              <button type="button" class="text-button" id="skip-upload">Skip — search by role instead</button>
              <button type="button" class="primary-button" id="continue-to-search" hidden>Continue to search <span>→</span></button>
            </div>
          </div>
        </section>
      </div>

      <div id="screen-search" hidden>
        <button type="button" class="back-link" id="back-to-upload">← Change CV</button>

        <section class="welcome-row"><div><h2>Shape the search<span class="accent">.</span></h2><p id="search-screen-subtitle">Let's make your next move a considered one.</p></div><div class="run-lookup"><label for="run-id" id="run-lookup-label">Retrieve a saved run</label><div class="lookup-line"><input id="run-id" placeholder="Paste run ID" /><button class="text-button" id="load-run">Load</button></div></div></section>

        <section class="workspace-grid single">
          <div class="panel search-panel" id="plain-filters">
            <div class="panel-heading"><div><span class="section-number">02</span><h3>Shape the search</h3></div><span class="panel-caption">FILTERS</span></div>
            <p class="panel-copy">Tell the agent what a good next role looks like. Role is the only thing required.</p>
            <div class="field-grid"><div class="field full"><label for="role">Role <span>required</span></label><input id="role" placeholder="e.g. Backend Engineer" /></div><div class="field"><label for="location">Location</label><input id="location" placeholder="e.g. Berlin" /></div><div class="field"><label for="keywords">Keywords</label><input id="keywords" placeholder="python, APIs" /></div></div>
            <div class="toggle-row"><div><strong>Remote only</strong><small>Only show roles that can be worked remotely</small></div><label class="switch"><input type="checkbox" id="remote-only" /><span></span></label></div>
            <div class="field"><label for="employment">Employment type</label><select id="employment"><option value="">Any employment type</option><option value="full_time">Full time</option><option value="part_time">Part time</option><option value="contract">Contract</option><option value="intern">Internship</option></select></div>
            <div class="limit-row"><label for="limit">Results <span>1–200</span></label><input type="number" id="limit" min="1" max="200" value="25" /></div>
            <fieldset class="source-filter"><legend>Sources</legend><div class="source-actions"><button type="button" class="text-button" id="select-all-sources">Select all</button><button type="button" class="text-button" id="deselect-all-sources">Deselect all</button></div><div class="source-options">${[
              ['arbeitnow', 'Arbeitnow'],
              ['adzuna', 'Adzuna'],
              ['jooble', 'Jooble'],
              ['bundesagentur', 'Bundesagentur'],
              ['greenhouse', 'Greenhouse'],
              ['lever', 'Lever'],
              ['glassdoor', 'Glassdoor'],
            ].map(([value, label]) => `<label><input type="checkbox" name="source" value="${value}" checked /><span>${label}</span></label>`).join('')}</div></fieldset>
            <button class="primary-button" id="run-search">Run search <span>↗</span></button>
          </div>

          <div class="panel search-panel" id="matcher-filters" hidden>
            <div class="panel-heading"><div><span class="section-number">02</span><h3>Match filters</h3></div><span class="panel-caption">FILTERS</span></div>
            <p class="panel-copy">Narrow the shortlist against your extracted profile. Everything here is optional.</p>
            <div class="field-grid">
              <div class="field"><label for="cm-min-score">Min score</label><input type="number" id="cm-min-score" min="0" max="100" placeholder="0" /></div>
              <div class="field"><label for="cm-location">Location</label><input id="cm-location" placeholder="e.g. Berlin" /></div>
              <div class="field"><label for="cm-seniority">Seniority</label><select id="cm-seniority"><option value="">Any seniority</option>${SENIORITY_LEVELS.map((level) => `<option value="${level}">${level[0].toUpperCase()}${level.slice(1)}</option>`).join('')}</select></div>
              <div class="field"><label for="cm-industry">Industry</label><input id="cm-industry" placeholder="e.g. fintech" /></div>
              <div class="field"><label for="cm-remote-type">Remote type</label><select id="cm-remote-type"><option value="">Any</option><option value="onsite">Onsite</option><option value="hybrid">Hybrid</option><option value="remote">Remote</option></select></div>
              <div class="field"><label for="cm-language">Language</label><input id="cm-language" placeholder="e.g. German" /></div>
              <div class="field"><label for="cm-employment">Employment type</label><select id="cm-employment"><option value="">Any employment type</option><option value="full_time">Full time</option><option value="part_time">Part time</option><option value="contract">Contract</option><option value="intern">Internship</option></select></div>
              <div class="field"><label for="cm-top-k">Results</label><input type="number" id="cm-top-k" min="1" max="100" value="20" /></div>
            </div>
            <button class="primary-button" id="cm-run-match">Run match <span>↗</span></button>
          </div>
        </section>

        <section class="results-section" id="results-section"><div class="results-header"><div><span class="section-number">03</span><h3 id="results-heading">Recommended for you</h3></div><span class="result-count" id="result-count">Waiting for your first search</span></div><div class="results-grid" id="results-grid"><div class="empty-results"><span class="empty-mark">✦</span><strong>Your shortlist will appear here.</strong><span>Run a search to see ranked roles.</span></div></div></section>
      </div>

      <footer>JOBHUNTER <span>·</span> A considered way to look for work</footer>
    </main>
  </div>
`

const $ = (id) => document.getElementById(id)
const setStatusEl = (id, message, type = '') => { $(id).textContent = message; $(id).className = `profile-status ${type}` }
const apiError = async (response) => { try { const body = await response.json(); return body.detail || 'Something went wrong.' } catch { return 'Could not reach the API.' } }

// --- Screen navigation ---

function setActiveStep(index) {
  ;['step-1', 'step-2', 'step-3'].forEach((id, stepIndex) => $(id).classList.toggle('active', stepIndex === index))
}

function goToUploadScreen() {
  $('screen-search').hidden = true
  $('screen-upload').hidden = false
  setActiveStep(0)
}

function goToSearchScreen() {
  $('screen-upload').hidden = true
  $('screen-search').hidden = false
  const isMatcher = state.mode === 'matcher'
  $('plain-filters').hidden = isMatcher
  $('matcher-filters').hidden = !isMatcher
  $('run-lookup-label').textContent = isMatcher ? 'Retrieve a saved match' : 'Retrieve a saved run'
  $('search-screen-subtitle').textContent = isMatcher
    ? 'Filters run against your extracted profile.'
    : "Let's make your next move a considered one."
  setActiveStep(1)
}

// --- Screen 1: CV upload (optional) ---

function renderCandidateSummary(profile) {
  const summary = $('cm-summary')
  const topSkills = (profile.skills || []).slice(0, 8).map((skill) => skill.normalized_name).join(', ')
  const languages = (profile.languages || []).map((language) => `${language.language} (${language.level})`).join(', ')
  summary.hidden = false
  summary.innerHTML = `<strong>${profile.full_name || 'Unnamed candidate'}</strong>${profile.headline ? `<span>${profile.headline}</span>` : ''}<div class="cm-summary-tags">${profile.seniority_level ? `<span>${profile.seniority_level}</span>` : ''}${profile.years_of_experience_total != null ? `<span>${profile.years_of_experience_total} yrs</span>` : ''}${topSkills ? `<span>${topSkills}</span>` : ''}${languages ? `<span>${languages}</span>` : ''}</div>`
}

function setCandidateProfile(profile) {
  state.candidateProfile = profile
  renderCandidateSummary(profile)
  $('cm-review').hidden = false
  $('cm-profile-json').value = JSON.stringify(profile, null, 2)
  $('continue-to-search').hidden = false
}

async function uploadCandidateCv() {
  const file = $('cm-cv-file').files[0]
  if (!file) { setStatusEl('cm-upload-status', 'Choose a CV file first.', 'error'); return }
  setStatusEl('cm-upload-status', 'Extracting profile...')
  try {
    const form = new FormData(); form.append('cv_file', file)
    const response = await fetch(`${API_URL}/api/candidates/upload-file`, { method: 'POST', body: form })
    if (!response.ok) throw new Error(await apiError(response))
    setCandidateProfile(await response.json())
    setStatusEl('cm-upload-status', 'Profile extracted — review and edit below, then continue.', 'success')
  } catch (error) { setStatusEl('cm-upload-status', error.message, 'error') }
}

async function saveCandidateProfileEdits() {
  if (!state.candidateProfile) return
  let edited
  try { edited = JSON.parse($('cm-profile-json').value) } catch { setStatusEl('cm-json-status', 'That JSON is not valid — fix it and try again.', 'error'); return }
  setStatusEl('cm-json-status', 'Saving...')
  try {
    const response = await fetch(`${API_URL}/api/candidates/${state.candidateProfile.profile_id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(edited) })
    if (!response.ok) throw new Error(await apiError(response))
    setCandidateProfile(await response.json())
    setStatusEl('cm-json-status', 'Changes saved.', 'success')
  } catch (error) { setStatusEl('cm-json-status', error.message, 'error') }
}

// --- Screen 2: search/filter + results grid ---

function renderResultCard(result, index) {
  const rank = String(index + 1).padStart(2, '0')
  if (state.mode === 'matcher') {
    const job = state.jobsById[result.job_id]
    const reasons = (result.match_reasons || []).map((reason) => `<span>${reason}</span>`).join('')
    const gaps = (result.gap_reasons || []).map((reason) => `<span>${reason}</span>`).join('')
    const subscores = Object.entries(result.subscores || {}).map(([name, value]) => `<span>${name}: ${Math.round(value * 100)}%</span>`).join('')
    return `<article class="job-card"><div class="job-card-top"><span class="rank">${rank}</span><span class="match-score">${Math.round(result.overall_fit)}% fit</span></div><span class="source">${job ? job.company : result.job_id}</span><h4>${job ? job.title : 'Job details unavailable'}</h4>${job ? `<p class="company">${job.company} <span>·</span> ${job.location || 'Unspecified'}</p>` : ''}${reasons ? `<div class="job-tags">${reasons}</div>` : ''}${gaps ? `<div class="job-tags gap-tags">${gaps}</div>` : ''}${subscores ? `<details class="cm-subscores"><summary>Subscores &amp; evidence</summary><div class="job-tags">${subscores}</div></details>` : ''}</article>`
  }
  const reasons = (result.reasons || []).slice(0, 3).map((reason) => `<span>${reason}</span>`).join('')
  return `<article class="job-card"><div class="job-card-top"><span class="rank">${rank}</span><span class="match-score">${Math.round(result.score * 100)}% match</span></div><span class="source">${result.job.source}</span><h4>${result.job.title}</h4><p class="company">${result.job.company} <span>·</span> ${result.job.location}</p><div class="job-tags"><span>${result.job.is_remote ? 'Remote' : result.job.location}</span><span>${result.job.employment_type.replace('_', ' ')}</span>${reasons}</div><a class="open-job" href="${result.job.url}" target="_blank" rel="noreferrer">Open posting ↗</a></article>`
}

function renderResultsGrid(items) {
  const grid = $('results-grid')
  if (!items.length) { grid.innerHTML = '<div class="empty-results"><span class="empty-mark">—</span><strong>No matching roles yet.</strong><span>Try loosening the filters.</span></div>'; return }
  grid.innerHTML = items.map((result, index) => renderResultCard(result, index)).join('')
}

function renderResults(response) {
  state.results = response.results
  state.runId = response.run_id
  $('run-id').value = state.runId
  $('result-count').textContent = `${state.results.length} match${state.results.length === 1 ? '' : 'es'} · run saved`
  renderResultsGrid(state.results)
  setActiveStep(2)
  $('results-section').scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function loadJobsById() {
  try {
    const response = await fetch(`${API_URL}/api/jobs`)
    if (!response.ok) return
    state.jobsById = Object.fromEntries((await response.json()).map((job) => [job.job_id, job]))
  } catch { /* best effort — results still render, falling back to job_id where a title would go */ }
}

async function runSearch() {
  const role = $('role').value.trim()
  if (!role) { $('result-count').textContent = 'Enter a role to search for.'; $('role').focus(); return }
  const sources = [...document.querySelectorAll('input[name="source"]:checked')].map((input) => input.value)
  if (!sources.length) { $('result-count').textContent = 'Select at least one source.'; return }
  $('run-search').disabled = true; $('run-search').innerHTML = 'Searching... <span>·</span>'
  const employment = $('employment').value
  const criteria = { role, location: $('location').value.trim() || null, keywords: $('keywords').value.split(',').map((item) => item.trim()).filter(Boolean), remote_only: $('remote-only').checked, employment_types: employment ? [employment] : [], limit: Number($('limit').value) || 25, sources }
  try {
    const response = await fetch(`${API_URL}/api/searches`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ criteria }) })
    if (!response.ok) throw new Error(await apiError(response))
    renderResults(await response.json())
  } catch (error) { $('result-count').textContent = error.message } finally { $('run-search').disabled = false; $('run-search').innerHTML = 'Run search <span>↗</span>' }
}

async function loadRun() {
  const runId = $('run-id').value.trim(); if (!runId) return
  $('result-count').textContent = 'Loading saved run...'
  try {
    const response = await fetch(`${API_URL}/api/searches/${encodeURIComponent(runId)}`)
    if (!response.ok) throw new Error(await apiError(response))
    renderResults(await response.json())
  } catch (error) { $('result-count').textContent = error.message }
}

async function runMatch() {
  if (!state.candidateProfile) return
  $('cm-run-match').disabled = true; $('cm-run-match').innerHTML = 'Matching... <span>·</span>'
  const filters = {
    min_score: Number($('cm-min-score').value) || 0,
    location: $('cm-location').value.trim() || null,
    seniority: $('cm-seniority').value || null,
    industry: $('cm-industry').value.trim() || null,
    remote_type: $('cm-remote-type').value || null,
    language: $('cm-language').value.trim() || null,
    employment_type: $('cm-employment').value || null,
    top_k: Number($('cm-top-k').value) || 20,
  }
  try {
    await loadJobsById()
    const response = await fetch(`${API_URL}/api/candidates/${state.candidateProfile.profile_id}/match`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(filters) })
    if (!response.ok) throw new Error(await apiError(response))
    renderResults(await response.json())
  } catch (error) { $('result-count').textContent = error.message } finally { $('cm-run-match').disabled = false; $('cm-run-match').innerHTML = 'Run match <span>↗</span>' }
}

async function loadMatchRun() {
  const runId = $('run-id').value.trim(); if (!runId) return
  $('result-count').textContent = 'Loading saved match...'
  try {
    await loadJobsById()
    const response = await fetch(`${API_URL}/api/match-runs/${encodeURIComponent(runId)}`)
    if (!response.ok) throw new Error(await apiError(response))
    renderResults(await response.json())
  } catch (error) { $('result-count').textContent = error.message }
}

// --- Wiring ---

$('cm-choose-file').addEventListener('click', () => $('cm-cv-file').click())
$('cm-cv-file').addEventListener('change', () => { if ($('cm-cv-file').files[0]) { $('cm-file-label').textContent = $('cm-cv-file').files[0].name; uploadCandidateCv() } })
$('cm-drop-zone').addEventListener('dragover', (event) => { event.preventDefault(); $('cm-drop-zone').classList.add('dragging') })
$('cm-drop-zone').addEventListener('dragleave', () => $('cm-drop-zone').classList.remove('dragging'))
$('cm-drop-zone').addEventListener('drop', (event) => { event.preventDefault(); $('cm-drop-zone').classList.remove('dragging'); if (event.dataTransfer.files[0]) { $('cm-cv-file').files = event.dataTransfer.files; $('cm-file-label').textContent = event.dataTransfer.files[0].name; uploadCandidateCv() } })
$('cm-save-json').addEventListener('click', saveCandidateProfileEdits)

$('skip-upload').addEventListener('click', () => { state.mode = 'plain'; goToSearchScreen() })
$('continue-to-search').addEventListener('click', () => { state.mode = 'matcher'; goToSearchScreen() })
$('back-to-upload').addEventListener('click', goToUploadScreen)

$('select-all-sources').addEventListener('click', () => { document.querySelectorAll('input[name="source"]').forEach((input) => { input.checked = true }) })
$('deselect-all-sources').addEventListener('click', () => { document.querySelectorAll('input[name="source"]').forEach((input) => { input.checked = false }) })
$('run-search').addEventListener('click', runSearch)
$('cm-run-match').addEventListener('click', runMatch)
$('load-run').addEventListener('click', () => { if (state.mode === 'matcher') loadMatchRun(); else loadRun() })
$('health-button').addEventListener('click', async () => { try { const response = await fetch(`${API_URL}/health`); $('health-button').innerHTML = `<span class="pulse good"></span>${response.ok ? 'API connected' : 'API issue'}` } catch { $('health-button').innerHTML = '<span class="pulse bad"></span>API offline' } })

setActiveStep(0)
