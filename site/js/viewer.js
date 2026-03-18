/**
 * viewer.js - Image and transcription display
 */

import { marked } from 'marked'

// DOM elements
let img = null
let imageLoading = null
let navLabel = null
let transcriptionArea = null

// Navigation counter to prevent stale responses from overwriting current view
let currentNavId = 0

/**
 * Initialize viewer DOM references
 */
export function initViewer() {
  img = document.getElementById('diary-image')
  imageLoading = document.getElementById('image-loading')
  navLabel = document.getElementById('nav-label')
  transcriptionArea = document.getElementById('transcription-area')
  
  // Handle image load states
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
 * Format a date range for display
 */
function formatDateRange(dates) {
  if (!dates || dates.length === 0) return ''
  
  const months = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ]
  
  if (dates.length === 1) {
    const [y, m, d] = dates[0].split('-')
    return `${months[parseInt(m)]} ${parseInt(d)}, ${y}`
  }
  
  // Multiple dates - format as range
  const first = dates[0]
  const last = dates[dates.length - 1]
  const [y1, m1, d1] = first.split('-')
  const [y2, m2, d2] = last.split('-')
  
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
      const adjacentId = ids[i]
      const [year] = adjacentId.split('/')
      const fileUri = manifest[adjacentId]
      const link = document.createElement('link')
      link.rel = 'prefetch'
      link.href = `/images/${year}/${fileUri}.jpg`
      link.as = 'image'
      document.head.appendChild(link)
    }
  }
  
  prefetch(index - 1)
  prefetch(index + 1)
}

/**
 * Render a diary entry
 */
export async function renderEntry(id, manifest, yearIndex) {
  const thisNavId = ++currentNavId
  const fileUri = manifest[id]
  const [year] = id.split('/')
  const seq = parseInt(id.split('/')[1])
  
  // 1. Update page title (basic, will be refined with date if available)
  document.title = `${year} - ${seq} - The Diaries of James David Smillie`
  
  // 2. Image - loads immediately
  img.classList.add('loading')
  imageLoading.classList.add('active')
  img.src = `/images/${year}/${fileUri}.jpg`
  img.alt = `Diary photograph, ${year}, image ${seq}`
  
  // 3. Nav indicator
  const { count } = yearIndex[year]
  navLabel.textContent = `${year} - ${seq} of ${count}`
  
  // 4. Show spinner while transcription loads
  transcriptionArea.innerHTML = `
    <div class="tx-loading" aria-label="Loading transcription" aria-live="polite">
      <span class="spinner"></span>
    </div>`
  
  try {
    const response = await fetch(`/data/transcriptions/${year}/${fileUri}.json`)
    if (!response.ok) throw response.status
    const tx = await response.json()
    
    // Guard: discard if user navigated away
    if (thisNavId !== currentNavId) return
    
    const hasDiary = tx.sections.left.includes('diary') ||
                     tx.sections.right.includes('diary')
    
    // Update page title with date if available
    if (hasDiary && tx.dates.length) {
      document.title = `${formatDateRange(tx.dates)} - The Diaries of James David Smillie`
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
    // Guard: discard if user navigated away
    if (thisNavId !== currentNavId) return
    
    const msg = status === 404
      ? 'Transcription not yet available.'
      : 'Could not load transcription.'
    transcriptionArea.innerHTML = `<p class="tx-placeholder">${msg}</p>`
  }
  
  // 5. Prefetch adjacent images
  prefetchAdjacentImages(id, manifest)
}
