import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: {
      // proxy alle API-kald til backend, same-origin fra /ui/dev server
      '/account': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/sessions': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/share': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/admin': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/settings': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/models': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/config': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/status': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/notes': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
      '/notifications': { target: 'http://127.0.0.1:8000', changeOrigin: true, secure: false },
    },
  },
  build: {
    outDir: '../ui_dist',
    assetsDir: 'assets',
  },
})
