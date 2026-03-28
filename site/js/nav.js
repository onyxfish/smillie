/**
 * nav.js - Previous/next navigation and keyboard shortcuts
 */

import { navigateByDelta } from './main.js'

// DOM elements
let prevBtn = null
let nextBtn = null
let prevBtnBottom = null
let nextBtnBottom = null

// Swipe detection state
const SWIPE_THRESHOLD = 50   // minimum horizontal distance in px
const SWIPE_MAX_ANGLE = 0.5  // max ratio of vertical/horizontal to count as horizontal swipe

/**
 * Initialize navigation buttons and keyboard shortcuts
 */
export function initNav() {
  prevBtn = document.getElementById('prev-btn')
  nextBtn = document.getElementById('next-btn')
  prevBtnBottom = document.getElementById('prev-btn-bottom')
  nextBtnBottom = document.getElementById('next-btn-bottom')
  
  // Button click handlers
  prevBtn.addEventListener('click', () => navigateByDelta(-1))
  nextBtn.addEventListener('click', () => navigateByDelta(1))
  prevBtnBottom.addEventListener('click', () => navigateByDelta(-1))
  nextBtnBottom.addEventListener('click', () => navigateByDelta(1))
  
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Don't handle if user is typing in an input
    if (isInputFocused()) return
    
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      navigateByDelta(-1)
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      navigateByDelta(1)
    }
  })

  // Touch swipe for mobile navigation
  initSwipe()
}

/**
 * Attach touch swipe listeners to the viewer page
 */
function initSwipe() {
  const viewer = document.getElementById('viewer-page')
  const lightbox = document.getElementById('lightbox')

  let touchStartX = null
  let touchStartY = null

  viewer.addEventListener('touchstart', (e) => {
    // Don't initiate swipe if touch started inside the nav controls
    // (e.g. the scrubber or date picker) so those controls remain usable.
    if (e.target.closest('.nav-controls')) return
    touchStartX = e.touches[0].clientX
    touchStartY = e.touches[0].clientY
  }, { passive: true })

  viewer.addEventListener('touchend', (e) => {
    // Skip if no valid touchstart was recorded or the lightbox is open
    if (touchStartX === null || lightbox.classList.contains('active')) return

    const dx = e.changedTouches[0].clientX - touchStartX
    const dy = e.changedTouches[0].clientY - touchStartY

    touchStartX = null
    touchStartY = null

    // Only treat as a horizontal swipe when the horizontal distance is
    // large enough and the gesture isn't too diagonal (avoids division by zero).
    if (Math.abs(dx) >= SWIPE_THRESHOLD && Math.abs(dy) <= Math.abs(dx) * SWIPE_MAX_ANGLE) {
      if (dx < 0) {
        navigateByDelta(1)   // swipe left → next page
      } else {
        navigateByDelta(-1)  // swipe right → previous page
      }
    }
  }, { passive: true })
}

/**
 * Check if an input element is focused
 */
function isInputFocused() {
  const tag = document.activeElement?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA'
}

/**
 * Update button disabled states based on current position
 */
export function updateNavButtons(index, totalCount) {
  const atStart = index === 0
  const atEnd = index === totalCount - 1
  
  prevBtn.disabled = atStart
  nextBtn.disabled = atEnd
  prevBtnBottom.disabled = atStart
  nextBtnBottom.disabled = atEnd
}
