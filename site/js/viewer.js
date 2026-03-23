/**
 * viewer.js - Image and transcription display
 */

import { marked } from 'marked'

marked.use({ breaks: true })
import { syncDatePicker, syncDatePickerForward } from './datepicker.js'

// DOM elements
let img = null
let imageLoading = null
let transcriptionArea = null

// Navigation counter to prevent stale responses from overwriting current view
let currentNavId = 0

/**
 * Initialize viewer DOM references
 */
export function initViewer() {
  img = document.getElementById('diary-image')
  imageLoading = document.getElementById('image-loading')
  transcriptionArea = document.getElementById('transcription-area')

  img.addEventListener('load', () => {
    img.classList.remove('loading')
    imageLoading.classList.remove('active')
  })

  img.addEventListener('error', () => {
    img.classList.remove('loading')
    imageLoading.classList.remove('active')
  })
}

/**
 * Format a date range for display, e.g. "January 1-2, 1865"
 */
function formatDateRange(dates) {
  if (!dates || dates.length === 0) return ''

  const months = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ]

  if (dates.length === 1) {
    const [y, m, d] = dates[0].split('-')
    return `${months[parseInt(m)]} ${parseInt(d)}, ${y}`
  }

  const [y1, m1, d1] = dates[0].split('-')
  const [y2, m2, d2] = dates[dates.length - 1].split('-')

  if (y1 === y2 && m1 === m2) {
    return `${months[parseInt(m1)]} ${parseInt(d1)}-${parseInt(d2)}, ${y1}`
  } else if (y1 === y2) {
    return `${months[parseInt(m1)]} ${parseInt(d1)} - ${months[parseInt(m2)]} ${parseInt(d2)}, ${y1}`
  } else {
    return `${months[parseInt(m1)]} ${parseInt(d1)}, ${y1} - ${months[parseInt(m2)]} ${parseInt(d2)}, ${y2}`
  }
}

/**
 * Prefetch adjacent images for snappier navigation
 */
function prefetchAdjacentImages(id, manifest) {
  const ids = Object.keys(manifest)
  const index = ids.indexOf(id)

  const prefetch = (i) => {
    if (i >= 0 && i < ids.length) {
      const adjId = ids[i]
      const [year] = adjId.split('/')
      const link = document.createElement('link')
      link.rel = 'prefetch'
      link.href = `/images/${year}/${manifest[adjId]}.jpg`
      link.as = 'image'
      document.head.appendChild(link)
    }
  }

  prefetch(index - 1)
  prefetch(index + 1)
}

/**
 * Render a diary entry: load image immediately, fetch transcription async.
 */
export async function renderEntry(id, manifest, yearIndex) {
  const thisNavId = ++currentNavId
  const fileUri = manifest[id]
  const [year] = id.split('/')
  const seq = parseInt(id.split('/')[1])

  // Basic page title (refined with date once transcription loads)
  document.title = `${year} · ${seq} — The Diaries of James David Smillie`

  // Image loads immediately
  img.classList.add('loading')
  imageLoading.classList.add('active')
  img.src = `/images/${year}/${fileUri}.jpg`
  img.alt = `Diary photograph, ${year}, image ${seq}`

  // Spinner while transcription loads
  transcriptionArea.innerHTML = `
    <div class="tx-loading" aria-label="Loading transcription" aria-live="polite">
      <span class="spinner"></span>
    </div>`

  try {
    const response = await fetch(`/data/transcriptions/${year}/${fileUri}.json`)
    if (!response.ok) throw response.status
    const tx = await response.json()

    if (thisNavId !== currentNavId) return  // user navigated away

    const hasDiary = tx.sections.left.includes('diary') ||
                     tx.sections.right.includes('diary')

    // Sync date picker: use this page's first date if available,
    // otherwise find the next dated image forward in sequence.
    if (tx.dates.length) {
      syncDatePicker(tx.dates)
    } else {
      syncDatePickerForward(id)
    }

    if (hasDiary && tx.dates.length) {
      document.title = `${formatDateRange(tx.dates)} — The Diaries of James David Smillie`
    }

    transcriptionArea.innerHTML = `
      <div class="date-label ${hasDiary && tx.dates.length ? '' : 'hidden'}">
        ${hasDiary ? formatDateRange(tx.dates) : ''}
      </div>
      <div class="transcription-columns">
        <div class="transcription-col">
          <div class="transcription-col-label">Left page</div>
          <div class="transcription-text">${marked.parse(tx.left || '')}</div>
        </div>
        <div class="transcription-col">
          <div class="transcription-col-label">Right page</div>
          <div class="transcription-text">${marked.parse(tx.right || '')}</div>
        </div>
      </div>`

  } catch (status) {
    if (thisNavId !== currentNavId) return
    const msg = status === 404
      ? 'Transcription not yet available.'
      : 'Could not load transcription.'
    transcriptionArea.innerHTML = `<p class="tx-placeholder">${msg}</p>`
  }

  prefetchAdjacentImages(id, manifest)
}
