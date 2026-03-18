/**
 * scrubber.js - Timeline range input
 */

import { navigateByIndex, getIdByIndex, getYearInfoForIndex, getYearIndex, getTotalCount } from './main.js'

// DOM elements
let scrubber = null
let yearLabelsContainer = null
let navLabel = null

/**
 * Initialize the scrubber
 */
export function initScrubber(totalCount) {
  scrubber = document.getElementById('scrubber')
  yearLabelsContainer = document.getElementById('year-labels')
  navLabel = document.getElementById('nav-label')
  
  // Set scrubber max value
  scrubber.max = String(totalCount - 1)
  
  // Build year labels
  buildYearLabels()
  
  // Live preview while dragging (no image load)
  scrubber.addEventListener('input', (e) => {
    const index = parseInt(e.target.value)
    const info = getYearInfoForIndex(index)
    if (info) {
      const id = getIdByIndex(index)
      const seq = parseInt(id.split('/')[1])
      navLabel.textContent = `${info.year} - ${seq} of ${info.info.count}`
    }
  })
  
  // Navigate on release
  scrubber.addEventListener('change', (e) => {
    const index = parseInt(e.target.value)
    navigateByIndex(index)
  })
}

/**
 * Build year labels at proportional positions
 */
function buildYearLabels() {
  const yearIndex = getYearIndex()
  const totalCount = getTotalCount()
  
  // Show select years: 1865, 1870, 1875, 1880, 1885, 1890, 1895, 1900, 1905, 1909
  const yearsToShow = Object.keys(yearIndex)
    .filter(year => {
      const y = parseInt(year)
      return y === 1865 || y === 1909 || (y % 5 === 0 && y >= 1870 && y <= 1905)
    })
    .sort()
  
  yearLabelsContainer.innerHTML = yearsToShow.map(year => {
    const { start } = yearIndex[year]
    const pct = (start / (totalCount - 1)) * 100
    return `<span class="year-label" style="left: ${pct}%">${year}</span>`
  }).join('')
}

/**
 * Sync scrubber position with current index
 */
export function syncScrubber(index) {
  if (scrubber) {
    scrubber.value = String(index)
  }
}
