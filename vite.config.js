import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  root: 'site',
  publicDir: 'public',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'site/index.html'),
        about: resolve(__dirname, 'site/about.html'),
      },
    },
  },
  server: {
    proxy: {
      // Proxy image requests to local file server during development
      '/images': {
        target: 'http://localhost:8001',
        rewrite: (path) => path.replace('/images', ''),
      },
    },
  },
})
