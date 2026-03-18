/**
 * nav.js - Previous/next navigation and keyboard shortcuts
 */

import { navigateByDelta } from './main.js'

// DOM elements
let prevBtn = null
let nextBtn = null
let prevBtnBottom = null
let nextBtnBottom = null

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
