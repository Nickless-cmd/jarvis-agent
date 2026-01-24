import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Paths that should be proxied to the backend during development.
const proxyPaths = [
  '/status',
  '/v1',
  '/account',
  '/auth',
  '/sessions',
  '/admin',
  '/settings',
  '/notes',
  '/notifications',
  '/models',
  '/config',
  '/events',
  '/share'
]

const devProxy = proxyPaths.reduce((acc, path) => {
  acc[path] = {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    secure: false,
  }
  return acc
}, {} as Record<string, unknown>)

export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    // Restrict dev server to loopback only and avoid exposing to network
    host: '127.0.0.1',
    strictPort: true,
    // Proxy backend paths to local backend
    proxy: devProxy,
  },
  build: {
    outDir: '../ui_dist',
    assetsDir: 'assets',
    sourcemap: false,
  }
})
