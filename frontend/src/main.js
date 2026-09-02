import './style.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const state = {
  profile: null,
  results: [],
  runId: '',
  busy: false,
}

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
        <div class="step active"><span>01</span><div><strong>Your profile</strong><small>Upload a CV to begin</small></div></div>
        <div class="step"><span>02</span><div><strong>Shape the search</strong><small>Set your ideal parameters</small></div></div>
        <div class="step"><span>03</span><div><strong>Review matches</strong><small>Open roles ranked for you</small></div></div>
      </nav>
      <div class="side-note"><span class="status-dot"></span><span>Local workspace<br><small>Your data stays on this machine.</small></span></div>
    </aside>

    <main class="main-content">
      <header class="topbar"><div><span class="eyebrow">SEARCH / NEW RUN</span><p class="date-line">Wednesday, September 2, 2026</p></div><button class="icon-button" id="health-button" title="Check API status" aria-label="Check API status"><span class="pulse"></span>API status</button></header>

      <section class="welcome-row"><div><h2>Good morning<span class="accent">.</span></h2><p>Let's make your next move a considered one.</p></div><div class="run-lookup"><label for="run-id">Retrieve a saved run</label><div class="lookup-line"><input id="run-id" placeholder="Paste run ID" /><button class="text-button" id="load-run">Load</button></div></div></section>

      <section class="workspace-grid">
        <div class="panel profile-panel">
          <div class="panel-heading"><div><span class="section-number">01</span><h3>Build your profile</h3></div><span class="panel-caption">CV / PROFILE</span></div>
          <p class="panel-copy">We pull a few signals from your CV to make every search more relevant.</p>
          <div class="drop-zone" id="drop-zone"><input type="file" id="cv-file" accept=".pdf,.docx,.txt" hidden /><div class="upload-icon">↑</div><strong id="file-label">Drop your CV here</strong><span>PDF, DOCX or TXT · max 5 MB</span><button class="outline-button" id="choose-file">Choose file</button></div>
          <div class="or-line"><span>or paste text</span></div>
          <textarea id="cv-text" placeholder="Paste the text of your CV here (at least 20 characters)..." rows="4"></textarea>
          <label class="field-label" for="preferred-locations">Preferred locations <span>optional</span></label>
          <input id="preferred-locations" placeholder="Berlin, Munich" />
          <button class="primary-button" id="upload-profile">Save profile <span>→</span></button>
          <div class="profile-status" id="profile-status" aria-live="polite"></div>
        </div>

        <div class="panel search-panel">
          <div class="panel-heading"><div><span class="section-number">02</span><h3>Shape the search</h3></div><span class="panel-caption">FILTERS</span></div>
          <p class="panel-copy">Tell the agent what a good next role looks like.</p>
          <div class="field-grid"><div class="field full"><label for="role">Role</label><input id="role" placeholder="e.g. Backend Engineer" /></div><div class="field"><label for="location">Location</label><input id="location" placeholder="e.g. Berlin" /></div><div class="field"><label for="keywords">Keywords</label><input id="keywords" placeholder="python, APIs" /></div></div>
          <div class="toggle-row"><div><strong>Remote only</strong><small>Only show roles that can be worked remotely</small></div><label class="switch"><input type="checkbox" id="remote-only" /><span></span></label></div>
          <div class="field"><label for="employment">Employment type</label><select id="employment"><option value="">Any employment type</option><option value="full_time">Full time</option><option value="part_time">Part time</option><option value="contract">Contract</option><option value="intern">Internship</option></select></div>
          <div class="limit-row"><label for="limit">Results <span>1–200</span></label><input type="number" id="limit" min="1" max="200" value="25" /></div>
          <button class="primary-button search-button" id="run-search" disabled>Run search <span>↗</span></button>
          <div class="profile-hint" id="profile-hint">Save a profile above to unlock search.</div>
        </div>
      </section>

      <section class="results-section" id="results-section"><div class="results-header"><div><span class="section-number">03</span><h3>Recommended for you</h3></div><span class="result-count" id="result-count">Waiting for your first search</span></div><div class="results-list" id="results-list"><div class="empty-results"><span class="empty-mark">✦</span><strong>Your shortlist will appear here.</strong><span>Upload a profile and run a search to see ranked roles.</span></div></div></section>
      <footer>JOBHUNTER <span>·</span> A considered way to look for work</footer>
    </main>
  </div>
`

const $ = (id) => document.getElementById(id)
const setStatus = (message, type = '') => { $('profile-status').textContent = message; $('profile-status').className = `profile-status ${type}` }
const apiError = async (response) => { try { const body = await response.json(); return body.detail || 'Something went wrong.' } catch { return 'Could not reach the API.' } }

async function saveProfile() {
  const file = $('cv-file').files[0]
  const text = $('cv-text').value.trim()
  const locations = $('preferred-locations').value.split(',').map((item) => item.trim()).filter(Boolean)
  if (!file && text.length < 20) { setStatus('Add a CV file or paste at least 20 characters.', 'error'); return }
  setStatus('Saving profile...')
  try {
    const options = file ? { method: 'POST', body: (() => { const form = new FormData(); form.append('cv_file', file); locations.forEach((location) => form.append('preferred_locations', location)); return form })() } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cv_text: text, preferred_locations: locations }) }
    const response = await fetch(`${API_URL}/api/profiles/${file ? 'upload-file' : 'upload'}`, options)
    if (!response.ok) throw new Error(await apiError(response))
    state.profile = await response.json()
    $('run-search').disabled = false
    $('profile-hint').textContent = `Profile ready · ${state.profile.skills.join(', ')}`
    setStatus(`Profile saved · ${state.profile.skills.length} skill${state.profile.skills.length === 1 ? '' : 's'} found`, 'success')
  } catch (error) { setStatus(error.message, 'error') }
}

function renderResults(response) {
  state.results = response.results
  state.runId = response.run_id
  $('result-count').textContent = `${state.results.length} match${state.results.length === 1 ? '' : 'es'} · run saved`
  $('run-id').value = state.runId
  const list = $('results-list')
  if (!state.results.length) { list.innerHTML = '<div class="empty-results"><span class="empty-mark">—</span><strong>No matching roles yet.</strong><span>Try broadening the role, location, or keyword filters.</span></div>'; return }
  list.innerHTML = state.results.map((result, index) => `<article class="job-card"><div class="rank">${String(index + 1).padStart(2, '0')}</div><div class="job-main"><div class="job-topline"><span class="source">${result.job.source}</span><span class="match-score">${Math.round(result.score * 100)}% match</span></div><h4>${result.job.title}</h4><p class="company">${result.job.company} <span>·</span> ${result.job.location}</p><div class="job-tags"><span>${result.job.is_remote ? 'Remote' : result.job.location}</span><span>${result.job.employment_type.replace('_', ' ')}</span>${result.reasons.slice(0, 2).map((reason) => `<span>${reason}</span>`).join('')}</div></div><a class="open-job" href="${result.job.url}" target="_blank" rel="noreferrer" title="Open job posting" aria-label="Open ${result.job.title}">↗</a></article>`).join('')
}

async function runSearch() {
  if (!state.profile) return
  state.busy = true; $('run-search').disabled = true; $('run-search').innerHTML = 'Searching... <span>·</span>'
  const employment = $('employment').value
  const criteria = { role: $('role').value.trim() || null, location: $('location').value.trim() || null, keywords: $('keywords').value.split(',').map((item) => item.trim()).filter(Boolean), remote_only: $('remote-only').checked, employment_types: employment ? [employment] : [], limit: Number($('limit').value) || 25 }
  try { const response = await fetch(`${API_URL}/api/searches`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile_id: state.profile.profile_id, criteria }) }); if (!response.ok) throw new Error(await apiError(response)); renderResults(await response.json()); $('results-section').scrollIntoView({ behavior: 'smooth', block: 'start' }) } catch (error) { $('result-count').textContent = error.message; } finally { state.busy = false; $('run-search').disabled = false; $('run-search').innerHTML = 'Run search <span>↗</span>' }
}

async function loadRun() { const runId = $('run-id').value.trim(); if (!runId) return; $('result-count').textContent = 'Loading saved run...'; try { const response = await fetch(`${API_URL}/api/searches/${encodeURIComponent(runId)}`); if (!response.ok) throw new Error(await apiError(response)); renderResults(await response.json()) } catch (error) { $('result-count').textContent = error.message } }

$('choose-file').addEventListener('click', () => $('cv-file').click())
$('cv-file').addEventListener('change', () => { if ($('cv-file').files[0]) $('file-label').textContent = $('cv-file').files[0].name })
$('drop-zone').addEventListener('dragover', (event) => { event.preventDefault(); $('drop-zone').classList.add('dragging') })
$('drop-zone').addEventListener('dragleave', () => $('drop-zone').classList.remove('dragging'))
$('drop-zone').addEventListener('drop', (event) => { event.preventDefault(); $('drop-zone').classList.remove('dragging'); if (event.dataTransfer.files[0]) { $('cv-file').files = event.dataTransfer.files; $('file-label').textContent = event.dataTransfer.files[0].name } })
$('upload-profile').addEventListener('click', saveProfile)
$('run-search').addEventListener('click', runSearch)
$('load-run').addEventListener('click', loadRun)
$('health-button').addEventListener('click', async () => { try { const response = await fetch(`${API_URL}/health`); $('health-button').innerHTML = `<span class="pulse good"></span>${response.ok ? 'API connected' : 'API issue'}` } catch { $('health-button').innerHTML = '<span class="pulse bad"></span>API offline' } })
