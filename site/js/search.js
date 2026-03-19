/**
 * search.js - Pagefind-powered search page
 *
 * initSearchForm() — attaches submit handler to the header form; navigates
 *                    to /search?q=... on submit.
 * runSearch(query) — called by main.js when the /search route is active;
 *                    loads Pagefind, runs the query, renders result cards.
 */

import { navigate } from './main.js'

// Build the Pagefind URL from parts so Vite's static import analysis never
// sees a resolvable string literal. The middleware in vite.config.js strips
// the ?import query param Vite appends and serves from dist/pagefind/.
const PAGEFIND_URL = ['', 'pagefind', 'pagefind.js'].join('/')

let pagefind = null

async function getPagefind() {
  if (!pagefind) {
    try {
      pagefind = await import(PAGEFIND_URL)
      await pagefind.init()
    } catch (err) {
      console.error('Failed to load Pagefind:', err)
      return null
    }
  }
  return pagefind
}

/**
 * Attach the submit handler to the header search form.
 * Called once during app init.
 */
export function initSearchForm() {
  const form = document.getElementById('search-form')
  if (!form) return

  form.addEventListener('submit', (e) => {
    e.preventDefault()
    const q = document.getElementById('search-input').value.trim()
    if (!q) return
    navigate(`search?q=${encodeURIComponent(q)}`)
  })
}

/**
 * Run a search and render results into #search-results.
 * Called by main.js whenever the /search route is active.
 */
export async function runSearch(query) {
  const queryDisplay = document.getElementById('search-query-display')
  const resultsContainer = document.getElementById('search-results')

  // Echo the query
  if (queryDisplay) queryDisplay.textContent = `"${query}"`

  // Sync the search input so it reflects the current query
  const input = document.getElementById('search-input')
  if (input && input.value !== query) input.value = query

  // Show loading state
  resultsContainer.innerHTML = `
    <div class="search-loading">
      <span class="spinner"></span>
    </div>`

  const pf = await getPagefind()
  if (!pf) {
    resultsContainer.innerHTML = `
      <p class="search-message">Search is unavailable. Please try again later.</p>`
    return
  }

  const { results } = await pf.search(query)

  if (results.length === 0) {
    resultsContainer.innerHTML = `
      <p class="search-message">No results found for <strong>"${escapeHtml(query)}"</strong>.</p>`
    return
  }

  // Fetch result data (limit to 40)
  const data = await Promise.all(results.slice(0, 40).map(r => r.data()))

  resultsContainer.innerHTML = data.map(r => {
    // data-pagefind-meta="url:/1865/0003" ends up in r.meta.url.
    // r.url is the physical file path — not what we want.
    const url = r.meta?.url || r.url
    const title = r.meta?.title || url
    const excerpt = r.excerpt || ''
    // url from pagefind meta is "#YYYY/NNNN"; strip leading # or / to get bare id
    const id = url.replace(/^[#\/]+/, '')
    return `
      <a class="search-result-card" href="#${id}" data-id="${id}">
        <span class="search-result-title">${escapeHtml(title)}</span>
        <p class="search-result-excerpt">${excerpt}</p>
      </a>`
  }).join('')

  // SPA navigation on click — prevent full-page reload
  resultsContainer.querySelectorAll('.search-result-card').forEach(card => {
    card.addEventListener('click', (e) => {
      e.preventDefault()
      const id = card.dataset.id   // e.g. "1865/0003"
      navigate(id)
    })
  })
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
