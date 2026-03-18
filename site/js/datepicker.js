/**
 * datepicker.js - Date input (in the nav row) with nearest-image lookup
 */

import { navigateByDate, getSortedDates, getDateIndex, getIndexForId, navigate } from './main.js'

let datePicker = null
let sortedDates = null

/**
 * Sync the date picker display to the first date of the current page.
 * Only updates when dates are non-empty — non-diary pages (covers, blanks)
 * keep showing the last known date.
 */
export function syncDatePicker(dates) {
  if (datePicker && dates && dates.length > 0) {
    datePicker.value = dates[0]
  }
}

/**
 * For pages with no dates (covers, blanks, almanac-only), scan forward
 * through the sorted date list to find the first date whose image comes
 * at or after the current image's position in the manifest sequence.
 */
export function syncDatePickerForward(currentId) {
  if (!datePicker || !sortedDates) return
  const dateIndex = getDateIndex()
  const currentIndex = getIndexForId(currentId)
  if (currentIndex == null) return

  for (const date of sortedDates) {
    const targetIndex = getIndexForId(dateIndex[date])
    if (targetIndex != null && targetIndex >= currentIndex) {
      datePicker.value = date
      return
    }
  }
}

/**
 * Initialize the date picker
 */
export function initDatePicker() {
  datePicker = document.getElementById('date-picker')
  if (!datePicker) return

  sortedDates = getSortedDates()

  if (sortedDates.length > 0) {
    datePicker.min = sortedDates[0]
    datePicker.max = sortedDates[sortedDates.length - 1]
  }

  datePicker.addEventListener('change', (e) => {
    const date = e.target.value
    if (!date) return

    // Exact match in date index
    if (navigateByDate(date)) return

    // Nearest date via binary search
    const id = findNearestDate(date)
    if (id) navigate(id)
  })
}

/**
 * Binary search for the nearest diary date to a given ISO date string.
 */
function findNearestDate(target) {
  const dateIndex = getDateIndex()
  if (!sortedDates || sortedDates.length === 0) return null

  let lo = 0
  let hi = sortedDates.length - 1

  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (sortedDates[mid] < target) lo = mid + 1
    else hi = mid
  }

  const after  = sortedDates[lo]
  const before = sortedDates[lo - 1]

  if (!before) return dateIndex[after]
  if (!after)  return dateIndex[before]

  const targetTime = new Date(target).getTime()
  const beforeTime = new Date(before).getTime()
  const afterTime  = new Date(after).getTime()

  return (targetTime - beforeTime) <= (afterTime - targetTime)
    ? dateIndex[before]
    : dateIndex[after]
}
