import './style.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const state = {
  mode: null, // null | 'plain' | 'matcher' — decided by whether a CV was uploaded on screen 1
  candidateProfile: null,
  results: [],
  runId: '',
  jobsById: {},
  feedbackByJobId: {},
  skillsCatalog: null,
}

const SENIORITY_LEVELS = ['intern', 'junior', 'mid', 'senior', 'lead', 'manager', 'director', 'executive']
const LANGUAGE_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'Native']
const EMPLOYMENT_TYPES = [['intern', 'Intern'], ['full_time', 'Full-time'], ['part_time', 'Part-time'], ['contract', 'Contract']]

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
          <div class="panel search-panel" id="search-filters">
            <div class="panel-heading"><div><span class="section-number">02</span><h3>Shape the search</h3></div><span class="panel-caption">FILTERS</span></div>
            <p class="panel-copy" id="search-panel-copy">Tell the agent what a good next role looks like. Role is the only thing required.</p>
            <div class="field-grid">
              <div class="field full"><label for="role">Role <span>required</span></label><input id="role" placeholder="e.g. Backend Engineer" /></div>
              <div class="field"><label for="location">Location</label><input id="location" placeholder="e.g. Berlin" /></div>
              <div class="field"><label for="keywords">Keywords</label><input id="keywords" placeholder="python, APIs" /></div>
              <div class="field"><label for="company">Company</label><input id="company" placeholder="e.g. Stripe" /></div>
              <div class="field"><label for="industry">Industry</label><input id="industry" placeholder="e.g. fintech" /></div>
              <div class="field"><label for="language">Language</label><input id="language" placeholder="e.g. German" /></div>
              <div class="field"><label for="remote-type">Remote</label><select id="remote-type"><option value="">Any</option><option value="onsite">Onsite</option><option value="hybrid">Hybrid</option><option value="remote">Remote</option></select></div>
              <div class="field"><label for="employment">Employment type</label><select id="employment"><option value="">Any employment type</option>${EMPLOYMENT_TYPES.map(([value, label]) => `<option value="${value}">${label}</option>`).join('')}</select></div>
              <div class="field"><label for="seniority">Seniority</label><select id="seniority"><option value="">Any seniority</option>${SENIORITY_LEVELS.map((level) => `<option value="${level}">${level[0].toUpperCase()}${level.slice(1)}</option>`).join('')}</select></div>
              <div class="field"><label for="min-score">Min score</label><input type="number" id="min-score" min="0" max="100" placeholder="0" /></div>
            </div>
            <div class="limit-row"><label for="limit">Results <span>1–200</span></label><input type="number" id="limit" min="1" max="200" value="25" /></div>
            <fieldset class="source-filter"><legend>Sources</legend><div class="source-actions"><button type="button" class="text-button" id="select-all-sources">Select all</button><button type="button" class="text-button" id="deselect-all-sources">Deselect all</button></div><div class="source-options">${[
              ['arbeitnow', 'Arbeitnow'],
              ['adzuna', 'Adzuna'],
              ['jooble', 'Jooble'],
              ['bundesagentur', 'Bundesagentur'],
              ['greenhouse', 'Greenhouse'],
              ['lever', 'Lever'],
            ].map(([value, label]) => `<label><input type="checkbox" name="source" value="${value}" checked /><span>${label}</span></label>`).join('')}</div></fieldset>
            <button class="primary-button" id="run-search">Run search <span>↗</span></button>
          </div>
        </section>

        <section class="results-section" id="results-section"><div class="results-header"><div><span class="section-number">03</span><h3 id="results-heading">Recommended for you</h3></div><span class="result-count" id="result-count">Waiting for your first search</span></div><div class="results-grid" id="results-grid"><div class="empty-results"><span class="empty-mark">✦</span><strong>Your shortlist will appear here.</strong><span>Run a search to see ranked roles.</span></div></div></section>
      </div>

      <section class="results-section" id="health-section"><div class="results-header"><div><span class="section-number">04</span><h3>Source health</h3></div><span class="result-count" id="health-count">Checking...</span></div><div class="health-list" id="health-list"><div class="empty-results"><span class="empty-mark">·</span><strong>No checks yet.</strong><span>A background agent tests every source automatically and reports here.</span></div></div></section>
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
  $('search-screen-subtitle').textContent = isMatcher
    ? 'Filters run against your extracted profile, on top of jobs fetched live.'
    : "Let's make your next move a considered one."
  $('search-panel-copy').textContent = isMatcher
    ? 'Jobs are fetched live for this role, then ranked against your extracted profile. Everything below is optional.'
    : 'Tell the agent what a good next role looks like. Role is the only thing required.'
  setActiveStep(1)
}

// --- Screen 1: CV upload (optional) ---

function syncProfileJson() {
  $('cm-profile-json').value = JSON.stringify(state.candidateProfile, null, 2)
}

function levelToCanonical(level) {
  const key = (level || '').trim().toLowerCase()
  const map = {
    a1: 'A1', a2: 'A2', basic: 'A2',
    b1: 'B1', intermediate: 'B1', conversational: 'B1',
    b2: 'B2', professional: 'B2', 'working proficiency': 'B2', 'professional working proficiency': 'B2',
    c1: 'C1', advanced: 'C1', fluent: 'C1',
    c2: 'C2', native: 'Native', bilingual: 'Native', 'mother tongue': 'Native',
  }
  return map[key] || ''
}

async function ensureSkillsCatalog() {
  if (state.skillsCatalog) return state.skillsCatalog
  try {
    const response = await fetch(`${API_URL}/api/skills-catalog`)
    state.skillsCatalog = response.ok ? await response.json() : []
  } catch { state.skillsCatalog = [] }
  return state.skillsCatalog
}

function renderCandidateSummary(profile) {
  const summary = $('cm-summary')
  summary.hidden = false
  const seniorityOptions = ['', ...SENIORITY_LEVELS].map((level) => `<option value="${level}" ${level === (profile.seniority_level || '') ? 'selected' : ''}>${level ? `${level[0].toUpperCase()}${level.slice(1)}` : 'Not set'}</option>`).join('')
  const levelOptions = (selected) => ['', ...LANGUAGE_LEVELS].map((level) => `<option value="${level}" ${level === selected ? 'selected' : ''}>${level || 'Not set'}</option>`).join('')

  const skillsHtml = (profile.skills || []).map((skill, index) => `<span class="cm-tag">${skill.normalized_name}<button type="button" class="cm-tag-remove" data-skill-index="${index}" aria-label="Remove ${skill.normalized_name}">×</button></span>`).join('')
  const languagesHtml = (profile.languages || []).map((language, index) => `<div class="cm-lang-row"><span>${language.language}</span><select class="cm-lang-level-select" data-lang-index="${index}">${levelOptions(levelToCanonical(language.level))}</select><button type="button" class="cm-tag-remove" data-lang-index-remove="${index}" aria-label="Remove ${language.language}">×</button></div>`).join('')

  const employmentOptions = (selected) => ['', ...EMPLOYMENT_TYPES.map(([value]) => value)].map((value) => {
    const label = value ? EMPLOYMENT_TYPES.find(([v]) => v === value)[1] : 'Not set'
    return `<option value="${value}" ${value === (selected || '') ? 'selected' : ''}>${label}</option>`
  }).join('')
  const manualEntries = (profile.experience || []).map((entry, index) => ({ entry, index })).filter(({ entry }) => entry.evidence && entry.evidence.source_text === 'Added manually')
  const extraHtml = manualEntries.map(({ entry, index }) => `<div class="cm-exp-entry-row"><select class="cm-exp-type-select" data-exp-index="${index}">${employmentOptions(entry.employment_type)}</select><div class="cm-years-field"><input type="number" class="cm-exp-years-input" data-exp-index="${index}" min="0" step="0.1" value="${entry.duration_months ? Math.round((entry.duration_months / 12) * 10) / 10 : ''}" placeholder="0" /><span>yrs</span></div><button type="button" class="cm-tag-remove" data-exp-index-remove="${index}" aria-label="Remove entry">×</button></div>`).join('')

  summary.innerHTML = `
    <strong>${profile.full_name || 'Unnamed candidate'}</strong>${profile.headline ? `<span>${profile.headline}</span>` : ''}
    <div class="cm-subsection">
      <h5>Experience</h5>
      <div class="cm-exp-row">
        <select id="cm-seniority-select">${seniorityOptions}</select>
        <div class="cm-years-field"><input type="number" id="cm-years-input" min="0" step="0.1" value="${profile.years_of_experience_total ?? ''}" placeholder="0" /><span>years</span></div>
      </div>
      <div class="cm-exp-list" id="cm-exp-list">${extraHtml}</div>
      <button type="button" class="text-button" id="cm-exp-add-btn">+ Add employment type</button>
    </div>
    <div class="cm-subsection">
      <h5>Skills</h5>
      <div class="cm-tag-list" id="cm-skills-list">${skillsHtml}</div>
      <div class="cm-tag-search">
        <input type="text" id="cm-skill-search" placeholder="Add a skill..." autocomplete="off" />
        <div class="cm-tag-suggestions" id="cm-skill-suggestions" hidden></div>
      </div>
    </div>
    <div class="cm-subsection">
      <h5>Languages</h5>
      <div class="cm-lang-list" id="cm-lang-list">${languagesHtml}</div>
      <div class="cm-lang-add">
        <input type="text" id="cm-lang-new-name" placeholder="Add a language..." />
        <select id="cm-lang-new-level">${levelOptions('')}</select>
        <button type="button" class="outline-button" id="cm-lang-add-btn">Add</button>
      </div>
    </div>
  `

  wireCandidateSummaryEvents()
}

function wireCandidateSummaryEvents() {
  $('cm-seniority-select').addEventListener('change', (event) => {
    state.candidateProfile.seniority_level = event.target.value || null
    syncProfileJson()
  })
  $('cm-years-input').addEventListener('change', (event) => {
    state.candidateProfile.years_of_experience_total = event.target.value === '' ? null : Number(event.target.value)
    syncProfileJson()
  })

  document.querySelectorAll('.cm-exp-type-select[data-exp-index]').forEach((select) => {
    select.addEventListener('change', () => {
      state.candidateProfile.experience[Number(select.dataset.expIndex)].employment_type = select.value || null
      syncProfileJson()
    })
  })
  document.querySelectorAll('.cm-exp-years-input[data-exp-index]').forEach((input) => {
    input.addEventListener('change', () => {
      const years = input.value === '' ? 0 : Number(input.value)
      state.candidateProfile.experience[Number(input.dataset.expIndex)].duration_months = Math.round(years * 12)
      syncProfileJson()
    })
  })
  document.querySelectorAll('.cm-tag-remove[data-exp-index-remove]').forEach((button) => {
    button.addEventListener('click', () => {
      state.candidateProfile.experience.splice(Number(button.dataset.expIndexRemove), 1)
      renderCandidateSummary(state.candidateProfile)
      syncProfileJson()
    })
  })
  $('cm-exp-add-btn').addEventListener('click', () => {
    state.candidateProfile.experience = state.candidateProfile.experience || []
    state.candidateProfile.experience.push({
      title: 'Experience',
      normalized_title: 'Experience',
      company: 'Not specified',
      company_normalized: 'Not specified',
      employment_type: null,
      duration_months: 0,
      evidence: { source_text: 'Added manually', confidence: 1.0 },
    })
    renderCandidateSummary(state.candidateProfile)
    syncProfileJson()
  })

  document.querySelectorAll('.cm-tag-remove[data-skill-index]').forEach((button) => {
    button.addEventListener('click', () => {
      state.candidateProfile.skills.splice(Number(button.dataset.skillIndex), 1)
      renderCandidateSummary(state.candidateProfile)
      syncProfileJson()
    })
  })

  const skillSearch = $('cm-skill-search')
  const skillSuggestions = $('cm-skill-suggestions')
  skillSearch.addEventListener('input', async () => {
    const query = skillSearch.value.trim().toLowerCase()
    if (!query) { skillSuggestions.hidden = true; return }
    const catalog = await ensureSkillsCatalog()
    const existing = new Set((state.candidateProfile.skills || []).map((skill) => skill.normalized_name.toLowerCase()))
    const matches = catalog.filter((term) => term.toLowerCase().includes(query) && !existing.has(term.toLowerCase())).slice(0, 8)
    if (!matches.length) { skillSuggestions.hidden = true; return }
    skillSuggestions.hidden = false
    skillSuggestions.innerHTML = matches.map((term) => `<button type="button" class="cm-suggestion" data-term="${term}">${term}</button>`).join('')
    skillSuggestions.querySelectorAll('.cm-suggestion').forEach((button) => {
      button.addEventListener('click', () => {
        state.candidateProfile.skills.push({
          name: button.dataset.term,
          normalized_name: button.dataset.term,
          category: 'other',
          is_soft_skill: false,
          evidence: [],
        })
        skillSearch.value = ''
        skillSuggestions.hidden = true
        renderCandidateSummary(state.candidateProfile)
        syncProfileJson()
      })
    })
  })

  document.querySelectorAll('.cm-lang-level-select[data-lang-index]').forEach((select) => {
    select.addEventListener('change', () => {
      state.candidateProfile.languages[Number(select.dataset.langIndex)].level = select.value || 'unspecified'
      syncProfileJson()
    })
  })
  document.querySelectorAll('.cm-tag-remove[data-lang-index-remove]').forEach((button) => {
    button.addEventListener('click', () => {
      state.candidateProfile.languages.splice(Number(button.dataset.langIndexRemove), 1)
      renderCandidateSummary(state.candidateProfile)
      syncProfileJson()
    })
  })
  $('cm-lang-add-btn').addEventListener('click', () => {
    const name = $('cm-lang-new-name').value.trim()
    if (!name) return
    state.candidateProfile.languages.push({
      language: name,
      level: $('cm-lang-new-level').value || 'unspecified',
      evidence: { source_text: 'Added manually', confidence: 1.0 },
    })
    renderCandidateSummary(state.candidateProfile)
    syncProfileJson()
  })
}

function setCandidateProfile(profile) {
  state.candidateProfile = profile
  renderCandidateSummary(profile)
  ensureSkillsCatalog()
  $('cm-review').hidden = false
  syncProfileJson()
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
  const job = state.jobsById[result.job_id]
  const reasons = (result.match_reasons || []).map((reason) => `<span>${reason}</span>`).join('')
  const gaps = (result.gap_reasons || []).map((reason) => `<span>${reason}</span>`).join('')
  const subscores = Object.entries(result.subscores || {}).map(([name, value]) => `<span>${name}: ${Math.round(value * 100)}%</span>`).join('')
  const rating = state.feedbackByJobId[result.job_id] || null
  const feedbackHtml = `<div class="job-card-actions"><button type="button" class="feedback-btn like-btn${rating === 'like' ? ' is-active' : ''}" data-job-id="${result.job_id}" data-rating="like" aria-label="Like this job" aria-pressed="${rating === 'like'}">👍</button><button type="button" class="feedback-btn dislike-btn${rating === 'dislike' ? ' is-active' : ''}" data-job-id="${result.job_id}" data-rating="dislike" aria-label="Dislike this job" aria-pressed="${rating === 'dislike'}">👎</button></div>`
  return `<article class="job-card" data-job-id="${result.job_id}"><div class="job-card-top"><span class="rank">${rank}</span><span class="match-score">${Math.round(result.overall_fit)}% match</span></div>${feedbackHtml}<span class="source">${job ? job.source || job.company : result.job_id}</span><h4>${job ? job.title : 'Job details unavailable'}</h4>${job ? `<p class="company">${job.company} <span>·</span> ${job.location || 'Unspecified'}</p>` : ''}${job ? `<div class="job-tags"><span>${job.remote_type === 'remote' ? 'Remote' : job.location || 'Unspecified'}</span><span>${(job.employment_type || '').replace('_', ' ')}</span></div>` : ''}${reasons ? `<div class="job-tags">${reasons}</div>` : ''}${gaps ? `<div class="job-tags gap-tags">${gaps}</div>` : ''}${subscores ? `<details class="cm-subscores"><summary>Subscores &amp; evidence</summary><div class="job-tags">${subscores}</div></details>` : ''}${job && job.url ? `<a class="open-job" href="${job.url}" target="_blank" rel="noreferrer">Open posting ↗</a>` : ''}</article>`
}

function renderResultsGrid(items) {
  const grid = $('results-grid')
  if (!items.length) { grid.innerHTML = '<div class="empty-results"><span class="empty-mark">—</span><strong>No matching roles yet.</strong><span>Try loosening the filters.</span></div>'; return }
  grid.innerHTML = items.map((result, index) => renderResultCard(result, index)).join('')
  wireResultCardEvents()
}

async function setJobFeedback(jobId, rating) {
  const previous = state.feedbackByJobId[jobId] || null
  const next = previous === rating ? null : rating // clicking the active rating again clears it
  state.feedbackByJobId[jobId] = next
  renderResultsGrid(state.results)
  try {
    const response = await fetch(`${API_URL}/api/jobs/${encodeURIComponent(jobId)}/feedback`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating: next }),
    })
    if (!response.ok) throw new Error(await apiError(response))
  } catch {
    state.feedbackByJobId[jobId] = previous
    renderResultsGrid(state.results)
  }
}

function wireResultCardEvents() {
  document.querySelectorAll('.feedback-btn').forEach((button) => {
    button.addEventListener('click', () => setJobFeedback(button.dataset.jobId, button.dataset.rating))
  })
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

async function loadJobFeedback() {
  try {
    const response = await fetch(`${API_URL}/api/jobs/feedback`)
    if (!response.ok) return
    state.feedbackByJobId = await response.json()
  } catch { /* best effort — cards just render with no rating pre-selected */ }
}

async function runSearch() {
  const role = $('role').value.trim()
  if (!role) { $('result-count').textContent = 'Enter a role to search for.'; $('role').focus(); return }
  const sources = [...document.querySelectorAll('input[name="source"]:checked')].map((input) => input.value)
  if (!sources.length) { $('result-count').textContent = 'Select at least one source.'; return }
  $('run-search').disabled = true; $('run-search').innerHTML = 'Searching... <span>·</span>'
  const payload = {
    candidate_profile_id: state.mode === 'matcher' && state.candidateProfile ? state.candidateProfile.profile_id : null,
    role,
    location: $('location').value.trim() || null,
    keywords: $('keywords').value.split(',').map((item) => item.trim()).filter(Boolean),
    company: $('company').value.trim() || null,
    industry: $('industry').value.trim() || null,
    language: $('language').value.trim() || null,
    remote_type: $('remote-type').value || null,
    employment_type: $('employment').value || null,
    seniority: $('seniority').value || null,
    min_score: Number($('min-score').value) || 0,
    limit: Number($('limit').value) || 25,
    sources,
  }
  try {
    const response = await fetch(`${API_URL}/api/search`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (!response.ok) throw new Error(await apiError(response))
    const result = await response.json()
    await Promise.all([loadJobsById(), loadJobFeedback()])
    renderResults(result)
  } catch (error) { $('result-count').textContent = error.message } finally { $('run-search').disabled = false; $('run-search').innerHTML = 'Run search <span>↗</span>' }
}

async function loadRun() {
  const runId = $('run-id').value.trim(); if (!runId) return
  $('result-count').textContent = 'Loading saved run...'
  try {
    await Promise.all([loadJobsById(), loadJobFeedback()])
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
$('load-run').addEventListener('click', loadRun)
$('health-button').addEventListener('click', async () => { try { const response = await fetch(`${API_URL}/health`); $('health-button').innerHTML = `<span class="pulse good"></span>${response.ok ? 'API connected' : 'API issue'}` } catch { $('health-button').innerHTML = '<span class="pulse bad"></span>API offline' } })

setActiveStep(0)

function timeAgo(iso) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  return `${Math.round(minutes / 60)}h ago`
}

function renderHealth(findings) {
  $('health-count').textContent = `${findings.length} source${findings.length === 1 ? '' : 's'} tracked`
  const list = $('health-list')
  if (!findings.length) return
  list.innerHTML = findings.map((finding) => {
    const pulseClass = finding.status === 'ok' ? 'good' : finding.status === 'error' ? 'bad' : ''
    const detail = finding.status === 'error'
      ? (finding.diagnosis || finding.error_detail || 'Failing, diagnosis pending.')
      : finding.status === 'no_results'
        ? 'No results returned, but no error detected — may just be a quiet source right now.'
        : `${finding.discovered_count} job${finding.discovered_count === 1 ? '' : 's'} found.`
    const diffLines = finding.fix_status === 'proposed' && finding.diff_preview
      ? finding.diff_preview.split('\n').map((line) => `<span class="${line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : ''}">${line.replace(/</g, '&lt;')}</span>`).join('\n')
      : ''
    let actions = ''
    if (finding.fix_status === 'proposed') {
      const diffBlock = `<pre class="health-diff">${diffLines}</pre>`
      if (finding.try_status === 'none') {
        actions = `${diffBlock}<div class="health-actions"><button class="try-fix" data-source="${finding.source}">Try recommended fix</button></div>`
      } else {
        const worked = finding.try_status === 'worked'
        actions = `${diffBlock}<div class="health-try-result ${worked ? 'worked' : 'failed'}">${worked ? '✓ Worked' : '✗ Failed'} — ${finding.try_detail || ''}</div><div class="health-actions"><button class="apply-fix" data-source="${finding.source}">Apply change</button><button class="dismiss-fix" data-source="${finding.source}">Reject change</button></div>`
      }
    } else if (finding.fix_status === 'applied') {
      actions = '<span class="health-fix-status">Fix applied · will reconfirm on next check</span>'
    } else if (finding.fix_status === 'dismissed') {
      actions = '<span class="health-fix-status">Fix rejected</span>'
    }
    return `<article class="health-row"><div class="health-row-top"><span class="health-source"><span class="pulse ${pulseClass}"></span>${finding.source}</span><span class="health-meta">${timeAgo(finding.checked_at)}</span></div><p class="health-detail">${detail}</p>${actions}</article>`
  }).join('')
  list.querySelectorAll('.try-fix').forEach((button) => button.addEventListener('click', () => tryFix(button.dataset.source)))
  list.querySelectorAll('.apply-fix').forEach((button) => button.addEventListener('click', () => applyFix(button.dataset.source)))
  list.querySelectorAll('.dismiss-fix').forEach((button) => button.addEventListener('click', () => dismissFix(button.dataset.source)))
}

async function fetchHealth() {
  try {
    const response = await fetch(`${API_URL}/api/health/sources`)
    if (!response.ok) return
    renderHealth(await response.json())
  } catch { /* background poll, ignore failures */ }
}

async function tryFix(source) {
  const button = document.querySelector(`.try-fix[data-source="${source}"]`)
  if (button) { button.disabled = true; button.textContent = 'Trying...' }
  try { await fetch(`${API_URL}/api/health/sources/${encodeURIComponent(source)}/try-fix`, { method: 'POST' }) } finally { fetchHealth() }
}
async function applyFix(source) { await fetch(`${API_URL}/api/health/sources/${encodeURIComponent(source)}/apply-fix`, { method: 'POST' }); fetchHealth() }
async function dismissFix(source) { await fetch(`${API_URL}/api/health/sources/${encodeURIComponent(source)}/dismiss-fix`, { method: 'POST' }); fetchHealth() }

fetchHealth()
setInterval(fetchHealth, 60000)
