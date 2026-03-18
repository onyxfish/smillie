/**
 * main.js - Entry point for the Smillie Diaries viewer
 *
 * Handles data loading, client-side routing, and module coordination.
 *
 * Routes:
 *   /YYYY/NNNN        → diary viewer
 *   /search?q=...     → search results page
 *   / or unknown      → diary viewer at first image
 */

import { initViewer, renderEntry } from './viewer.js'
import { initNav, updateNavButtons } from './nav.js'
import { initScrubber, syncScrubber } from './scrubber.js'
import { initDatePicker } from './datepicker.js'
import { initSearchForm, runSearch } from './search.js'
import { initLightbox } from './lightbox.js'

// Global state
let manifest = null
let yearIndex = null
let dateIndex = null
let ids = []
let idToIndex = null

// Page elements
let viewerPage = null
let searchPage = null

/**
 * Load all data files in parallel
 */
async function loadData() {
  const [manifestData, yearData, dateData] = await Promise.all([
    fetch('/data/manifest.json').then(r => r.json()),
    fetch('/data/year-index.json').then(r => r.json()),
    fetch('/data/date-index.json').then(r => r.json()),
  ])

  manifest = manifestData
  yearIndex = yearData
  dateIndex = dateData

  ids = Object.keys(manifest)
  idToIndex = new Map(ids.map((id, i) => [id, i]))
}

/**
 * Show the diary viewer, hide the search page
 */
function showViewer() {
  viewerPage.hidden = false
  searchPage.hidden = true
  document.title = 'The Diaries of James David Smillie'
}

/**
 * Show the search page, hide the diary viewer
 */
function showSearch() {
  viewerPage.hidden = true
  searchPage.hidden = false
}

/**
 * Parse a diary image ID from a URL pathname (/YYYY/NNNN)
 */
function urlToId(pathname) {
  const m = pathname.match(/^\/(\d{4})\/(\d{4})$/)
  if (m) {
    const id = `${m[1]}/${m[2]}`
    if (manifest[id]) return id
  }
  return null
}

/**
 * Route a URL — either diary viewer or search page.
 * `replace` controls whether to use replaceState vs pushState.
 */
export function navigate(urlOrId, replace = false) {
  // Detect /search?q=... (passed as a full path string)
  if (typeof urlOrId === 'string' && urlOrId.startsWith('/search')) {
    const url = new URL(urlOrId, location.origin)
    if (replace) {
      history.replaceState({ type: 'search', q: url.searchParams.get('q') }, '', urlOrId)
    } else {
      history.pushState({ type: 'search', q: url.searchParams.get('q') }, '', urlOrId)
    }
    showSearch()
    runSearch(url.searchParams.get('q') || '')
    document.title = `Search — The Diaries of James David Smillie`
    return
  }

  // Diary viewer — urlOrId is either a full path (/YYYY/NNNN) or bare id (YYYY/NNNN)
  let id = urlOrId
  if (typeof id === 'string' && id.startsWith('/')) {
    id = urlToId(id) // parse from path, returns null if invalid
  }

  if (!id || !manifest[id]) {
    id = ids[0]
    history.replaceState({ type: 'diary', id }, '', `/${id}`)
  } else if (replace) {
    history.replaceState({ type: 'diary', id }, '', `/${id}`)
  } else {
    history.pushState({ type: 'diary', id }, '', `/${id}`)
  }

  showViewer()
  const index = idToIndex.get(id)
  renderEntry(id, manifest, yearIndex)
  syncScrubber(index)
  updateNavButtons(index, ids.length)
}

/**
 * Navigate by ±1 (prev/next buttons, keyboard)
 */
export function navigateByDelta(delta) {
  const currentId = urlToId(location.pathname) || ids[0]
  const currentIndex = idToIndex.get(currentId) ?? 0
  const newIndex = Math.max(0, Math.min(ids.length - 1, currentIndex + delta))
  if (newIndex !== currentIndex) navigate(ids[newIndex])
}

/**
 * Navigate to an index position (scrubber)
 */
export function navigateByIndex(index) {
  navigate(ids[Math.max(0, Math.min(ids.length - 1, index))])
}

/** Get the ID at a given index */
export function getIdByIndex(index) { return ids[index] }

/** Get the manifest index for a given ID */
export function getIndexForId(id) { return idToIndex.get(id) }

/** Get year + yearIndex info for a given manifest index */
export function getYearInfoForIndex(index) {
  const id = ids[index]
  if (!id) return null
  const [year] = id.split('/')
  return { year, info: yearIndex[year] }
}

/** Navigate to the image that matches a date string */
export function navigateByDate(date) {
  const id = dateIndex[date]
  if (id) { navigate(id); return true }
  return false
}

/** Sorted date strings for the date picker */
export function getSortedDates() { return Object.keys(dateIndex).sort() }

/** Raw date→id index */
export function getDateIndex() { return dateIndex }

/** Total image count */
export function getTotalCount() { return ids.length }

/** Full year index */
export function getYearIndex() { return yearIndex }

/**
 * Bootstrap
 */
async function init() {
  viewerPage = document.getElementById('viewer-page')
  searchPage = document.getElementById('search-page')

  try {
    await loadData()

    initViewer()
    initNav()
    initScrubber(ids.length)
    initDatePicker()
    initSearchForm()
    initLightbox()

    // Browser back / forward
    window.addEventListener('popstate', (e) => {
      const state = e.state
      if (state?.type === 'search') {
        showSearch()
        runSearch(state.q || '')
        document.title = `Search — The Diaries of James David Smillie`
      } else {
        const id = state?.id || urlToId(location.pathname) || ids[0]
        showViewer()
        const index = idToIndex.get(id) ?? 0
        renderEntry(id, manifest, yearIndex)
        syncScrubber(index)
        updateNavButtons(index, ids.length)
      }
    })

    // Initial route
    if (location.pathname === '/search') {
      const q = new URLSearchParams(location.search).get('q') || ''
      history.replaceState({ type: 'search', q }, '', location.href)
      showSearch()
      runSearch(q)
      document.title = `Search — The Diaries of James David Smillie`
    } else {
      const initialId = urlToId(location.pathname)
      navigate(initialId || ids[0], true)
    }

  } catch (err) {
    console.error('Failed to initialize:', err)
    document.querySelector('.main').innerHTML = `
      <div class="tx-placeholder">
        <p>Failed to load diary data. Please try refreshing the page.</p>
      </div>`
  }
}

init()
