/**
 * lightbox.js - Full-screen image zoom
 */

// DOM elements
let lightbox = null
let lightboxImage = null
let lightboxClose = null
let diaryImage = null

/**
 * Initialize lightbox
 */
export function initLightbox() {
  lightbox = document.getElementById('lightbox')
  lightboxImage = document.getElementById('lightbox-image')
  lightboxClose = document.getElementById('lightbox-close')
  diaryImage = document.getElementById('diary-image')
  
  // Open lightbox on image click
  diaryImage.addEventListener('click', () => {
    openLightbox()
  })
  
  // Close on close button click
  lightboxClose.addEventListener('click', (e) => {
    e.stopPropagation()
    closeLightbox()
  })
  
  // Close on lightbox background click
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) {
      closeLightbox()
    }
  })
  
  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && lightbox.classList.contains('active')) {
      closeLightbox()
    }
  })
}

/**
 * Open the lightbox
 */
function openLightbox() {
  lightboxImage.src = diaryImage.src
  lightboxImage.alt = diaryImage.alt
  lightbox.classList.add('active')
  document.body.style.overflow = 'hidden'
  lightboxClose.focus()
}

/**
 * Close the lightbox
 */
function closeLightbox() {
  lightbox.classList.remove('active')
  document.body.style.overflow = ''
  diaryImage.focus()
}
