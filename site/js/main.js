/**
 * main.js - Entry point for the Smillie Diaries viewer
 * 
 * Loads data, initializes modules, handles routing.
 */

import { initViewer, renderEntry } from './viewer.js'
import { initNav, updateNavButtons } from './nav.js'
import { initScrubber, syncScrubber } from './scrubber.js'
import { initDatePicker } from './datepicker.js'
import { initSearch } from './search.js'
import { initLightbox } from './lightbox.js'

// Global state
let manifest = null
let yearIndex = null
let dateIndex = null
let ids = []
let idToIndex = null

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
  
  // Build ordered ID array and reverse lookup map
  ids = Object.keys(manifest)
  idToIndex = new Map(ids.map((id, i) => [id, i]))
}

/**
 * Parse URL path to extract image ID
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
 * Navigate to an image by ID
 */
export function navigate(id, replace = false) {
  if (!id || !manifest[id]) {
    // Invalid ID - redirect to first image
    id = ids[0]
    history.replaceState({ id }, '', `/${id}`)
  } else if (replace) {
    history.replaceState({ id }, '', `/${id}`)
  } else {
    history.pushState({ id }, '', `/${id}`)
  }
  
  const index = idToIndex.get(id)
  renderEntry(id, manifest, yearIndex)
  syncScrubber(index)
  updateNavButtons(index, ids.length)
}

/**
 * Navigate by delta (for prev/next)
 */
export function navigateByDelta(delta) {
  const currentId = urlToId(location.pathname) || ids[0]
  const currentIndex = idToIndex.get(currentId)
  const newIndex = Math.max(0, Math.min(ids.length - 1, currentIndex + delta))
  
  if (newIndex !== currentIndex) {
    navigate(ids[newIndex])
  }
}

/**
 * Navigate by index (for scrubber)
 */
export function navigateByIndex(index) {
  const clampedIndex = Math.max(0, Math.min(ids.length - 1, index))
  navigate(ids[clampedIndex])
}

/**
 * Get ID by index
 */
export function getIdByIndex(index) {
  return ids[index]
}

/**
 * Get year info for an index
 */
export function getYearInfoForIndex(index) {
  const id = ids[index]
  if (!id) return null
  const [year] = id.split('/')
  return { year, info: yearIndex[year] }
}

/**
 * Navigate by date
 */
export function navigateByDate(date) {
  const id = dateIndex[date]
  if (id) {
    navigate(id)
    return true
  }
  return false
}

/**
 * Get sorted dates array for date picker
 */
export function getSortedDates() {
  return Object.keys(dateIndex).sort()
}

/**
 * Get date index for nearest date lookup
 */
export function getDateIndex() {
  return dateIndex
}

/**
 * Get total count of images
 */
export function getTotalCount() {
  return ids.length
}

/**
 * Get year index data
 */
export function getYearIndex() {
  return yearIndex
}

/**
 * Initialize the application
 */
async function init() {
  try {
    await loadData()
    
    // Initialize all modules
    initViewer()
    initNav()
    initScrubber(ids.length)
    initDatePicker()
    initSearch()
    initLightbox()
    
    // Handle browser back/forward
    window.addEventListener('popstate', (e) => {
      const id = e.state?.id || urlToId(location.pathname) || ids[0]
      navigate(id, true)
    })
    
    // Initial navigation based on URL
    const initialId = urlToId(location.pathname)
    navigate(initialId || ids[0], true)
    
  } catch (error) {
    console.error('Failed to initialize:', error)
    document.querySelector('.main').innerHTML = `
      <div class="tx-placeholder">
        <p>Failed to load diary data. Please try refreshing the page.</p>
      </div>
    `
  }
}

// Start the app
init()
