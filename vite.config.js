import { defineConfig } from 'vite'
import { resolve } from 'path'
import fs from 'fs'
import path from 'path'

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
        rewrite: (p) => p.replace('/images', ''),
      },
    },
  },
  plugins: [
    {
      // Serve dist/pagefind/ at /pagefind/ during dev
      name: 'serve-pagefind',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          // Strip query string before matching/resolving (Vite appends ?import)
          const urlPath = req.url.split('?')[0]
          if (!urlPath.startsWith('/pagefind/')) return next()
          const filePath = path.join(__dirname, 'dist', urlPath)
          if (!fs.existsSync(filePath)) return next()
          const ext = path.extname(filePath)
          const types = {
            '.js':   'application/javascript',
            '.json': 'application/json',
            '.css':  'text/css',
          }
          res.setHeader('Content-Type', types[ext] ?? 'application/octet-stream')
          fs.createReadStream(filePath).pipe(res)
        })
      },
    },
  ],
})
