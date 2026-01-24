import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: {
      // alle API-kald går til backend
      '/account': 'http://127.0.0.1:8000',
      '/sessions': 'http://127.0.0.1:8000',
      '/share': 'http://127.0.0.1:8000',
      '/v1': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/settings': 'http://127.0.0.1:8000',
      '/status': 'http://127.0.0.1:8000',
      '/models': 'http://127.0.0.1:8000',
      '/config': 'http://127.0.0.1:8000',
      '/notifications': 'http://127.0.0.1:8000',
      '/notes': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/login': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: '../ui_dist',
    assetsDir: 'assets',
  },
})
