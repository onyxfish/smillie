/**
 * search.js - Pagefind integration for full-text search
 */

import { navigate } from './main.js'

// DOM elements
let searchInput = null
let searchResults = null

// Pagefind instance (lazy loaded)
let pagefind = null

/**
 * Initialize search functionality
 */
export function initSearch() {
  searchInput = document.getElementById('search-input')
  searchResults = document.getElementById('search-results')
  
  // Debounced search on input
  let debounceTimer = null
  searchInput.addEventListener('input', (e) => {
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => handleSearch(e.target.value), 200)
  })
  
  // Close results on outside click
  document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
      hideResults()
    }
  })
  
  // Close results on Escape
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideResults()
      searchInput.blur()
    }
  })
}

/**
 * Lazy load Pagefind
 */
// Build the URL from parts so Vite's static import analysis never sees a
// resolvable string literal. The middleware in vite.config.js strips the
// ?import query param Vite appends and serves the file from dist/pagefind/.
const PAGEFIND_URL = ['', 'pagefind', 'pagefind.js'].join('/')

async function getPagefind() {
  if (!pagefind) {
    try {
      pagefind = await import(PAGEFIND_URL)
      await pagefind.init()
    } catch (error) {
      console.error('Failed to load Pagefind:', error)
      return null
    }
  }
  return pagefind
}

/**
 * Handle search input
 */
async function handleSearch(query) {
  query = query.trim()
  
  if (query.length < 2) {
    hideResults()
    return
  }
  
  const pf = await getPagefind()
  if (!pf) {
    searchResults.innerHTML = '<div class="search-result"><span class="result-excerpt">Search unavailable</span></div>'
    searchResults.hidden = false
    return
  }
  
  const { results } = await pf.search(query)
  const data = await Promise.all(results.slice(0, 20).map(r => r.data()))
  
  renderResults(data)
}

/**
 * Render search results
 */
function renderResults(data) {
  if (data.length === 0) {
    searchResults.innerHTML = '<div class="search-result"><span class="result-excerpt">No results found</span></div>'
    searchResults.hidden = false
    return
  }
  
  searchResults.innerHTML = data.map(r => `
    <a class="search-result" href="${r.url}" data-id="${r.url.replace(/^\//, '')}">
      <span class="result-meta">${r.meta?.title || ''}</span>
      <span class="result-excerpt">${r.excerpt || ''}</span>
    </a>
  `).join('')
  
  searchResults.hidden = false
  
  // Handle result clicks
  searchResults.querySelectorAll('.search-result').forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault()
      const id = a.dataset.id
      if (id) {
        navigate(id)
        hideResults()
        searchInput.value = ''
      }
    })
  })
}

/**
 * Hide search results
 */
function hideResults() {
  searchResults.hidden = true
  searchResults.innerHTML = ''
}
