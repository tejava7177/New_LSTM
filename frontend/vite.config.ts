// Dev proxy: route frontend `/api` calls to the backend.
// - Default: remote backend on HTTPS (EC2 + Nginx)
// - Override locally: VITE_PROXY_TARGET=http://localhost:8000 npm run dev
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const target = process.env.VITE_PROXY_TARGET ?? 'https://cbbunivproject.store'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target,
        changeOrigin: true,
        secure: true, // LE cert 사용 중: true 권장 (이슈시 false로 시도)
      },
      // (선택) 스웨거 프록시
      '/docs': {
        target,
        changeOrigin: true,
        secure: true,
      },
      '/openapi.json': {
        target,
        changeOrigin: true,
        secure: true,
      },
    },
  },
})