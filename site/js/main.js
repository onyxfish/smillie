/**
 * main.js - Entry point for the Smillie Diaries viewer
 *
 * Handles data loading, client-side routing, and module coordination.
 *
 * Routes (hash-based, works on static S3 hosting):
 *   #YYYY/NNNN        → diary viewer
 *   #search?q=...     → search results page
 *   # or unknown      → diary viewer at default image
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

const DEFAULT_ENTRY_ID = '1865/0002'

function getDefaultId() {
  return manifest?.[DEFAULT_ENTRY_ID] ? DEFAULT_ENTRY_ID : ids[0]
}

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
 * Parse a diary image ID from a hash string (#YYYY/NNNN or YYYY/NNNN)
 */
function hashToId(hash) {
  const m = hash.replace(/^#/, '').match(/^(\d{4})\/(\d{4})$/)
  if (m) {
    const id = `${m[1]}/${m[2]}`
    if (manifest[id]) return id
  }
  return null
}

/**
 * Route based on the current location.hash — either diary viewer or search page.
 * `replace` controls whether to use replaceState vs pushState.
 */
export function navigate(urlOrId, replace = false) {
  // Detect search route: "search?q=..." or "#search?q=..."
  const normalized = (typeof urlOrId === 'string' ? urlOrId : '').replace(/^#/, '')
  if (normalized.startsWith('search')) {
    const q = new URLSearchParams(normalized.slice(normalized.indexOf('?') + 1)).get('q') || ''
    const newHash = `#search?q=${encodeURIComponent(q)}`
    if (replace) {
      history.replaceState(null, '', newHash)
    } else {
      history.pushState(null, '', newHash)
    }
    showSearch()
    runSearch(q)
    document.title = `Search — The Diaries of James David Smillie`
    return
  }

  // Diary viewer — urlOrId is either a hash (#YYYY/NNNN), bare id (YYYY/NNNN),
  // or legacy path (/YYYY/NNNN) for backwards compatibility
  let id = normalized.startsWith('/') ? normalized.slice(1) : normalized
  if (!id || !manifest[id]) {
    id = getDefaultId()
  }

  const newHash = `#${id}`
  if (replace) {
    history.replaceState(null, '', newHash)
  } else {
    history.pushState(null, '', newHash)
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
  const currentId = hashToId(location.hash) || getDefaultId()
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

    // Browser back / forward (hash changes)
    window.addEventListener('hashchange', () => {
      routeFromHash(location.hash)
    })

    // Initial route from hash
    routeFromHash(location.hash, true)

  } catch (err) {
    console.error('Failed to initialize:', err)
    document.querySelector('.main').innerHTML = `
      <div class="tx-placeholder">
        <p>Failed to load diary data. Please try refreshing the page.</p>
      </div>`
  }
}

/**
 * Parse and dispatch a route from a hash string.
 * Called on initial load and on hashchange events.
 */
function routeFromHash(hash, replace = false) {
  const fragment = hash.replace(/^#/, '')

  if (fragment.startsWith('search')) {
    const q = new URLSearchParams(fragment.slice(fragment.indexOf('?') + 1)).get('q') || ''
    showSearch()
    runSearch(q)
    document.title = `Search — The Diaries of James David Smillie`
    return
  }

  const id = hashToId(hash) || getDefaultId()
  if (!hashToId(hash)) {
    // Redirect to the canonical default-image hash without creating a new history entry
    history.replaceState(null, '', `#${id}`)
  }

  showViewer()
  const index = idToIndex.get(id)
  renderEntry(id, manifest, yearIndex)
  syncScrubber(index)
  updateNavButtons(index, ids.length)
}

init()
