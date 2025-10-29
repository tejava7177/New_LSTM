/// <reference types="node" />
// Dev proxy: route frontend `/api` calls to the backend.
// - Default: remote backend on HTTPS (EC2 + Nginx)
// - Override locally: VITE_PROXY_TARGET=http://localhost:8000 npm run dev
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Default to deployed backend; allow local override via env.
const target = process.env.VITE_PROXY_TARGET ?? 'https://cbbunivproject.store'
const useSecure = target.startsWith('https://') // verify TLS only for https targets

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target,
        changeOrigin: true,
        secure: useSecure,
      },
      // Swagger UI / OpenAPI (useful during dev)
      '/docs': {
        target,
        changeOrigin: true,
        secure: useSecure,
      },
      '/openapi.json': {
        target,
        changeOrigin: true,
        secure: useSecure,
      },
    },
  },
})