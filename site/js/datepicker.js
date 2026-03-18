/**
 * datepicker.js - Date input with nearest-image lookup
 */

import { navigateByDate, getSortedDates, getDateIndex } from './main.js'

// DOM elements
let datePicker = null

// Sorted dates array for binary search
let sortedDates = null

/**
 * Initialize the date picker
 */
export function initDatePicker() {
  datePicker = document.getElementById('date-picker')
  sortedDates = getSortedDates()
  
  // Set min/max dates
  if (sortedDates.length > 0) {
    datePicker.min = sortedDates[0]
    datePicker.max = sortedDates[sortedDates.length - 1]
  }
  
  // Handle date selection
  datePicker.addEventListener('change', (e) => {
    const date = e.target.value
    if (!date) return
    
    // Try exact match first
    if (navigateByDate(date)) {
      return
    }
    
    // Find nearest date
    const nearestId = findNearestDate(date)
    if (nearestId) {
      // Import navigate dynamically to avoid circular dependency
      import('./main.js').then(({ navigate }) => {
        navigate(nearestId)
      })
    }
  })
}

/**
 * Find the nearest date using binary search
 */
function findNearestDate(target) {
  const dateIndex = getDateIndex()
  
  if (sortedDates.length === 0) return null
  
  // Binary search to find insertion point
  let lo = 0
  let hi = sortedDates.length - 1
  
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (sortedDates[mid] < target) {
      lo = mid + 1
    } else {
      hi = mid
    }
  }
  
  const after = sortedDates[lo]
  const before = sortedDates[lo - 1]
  
  if (!before) return dateIndex[after]
  if (!after) return dateIndex[before]
  
  // Compare distances using Date timestamps (not string arithmetic)
  const targetTime = new Date(target).getTime()
  const beforeTime = new Date(before).getTime()
  const afterTime = new Date(after).getTime()
  
  return (targetTime - beforeTime) <= (afterTime - targetTime)
    ? dateIndex[before]
    : dateIndex[after]
}
