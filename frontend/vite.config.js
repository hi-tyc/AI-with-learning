import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 端口从环境变量读取（由 start.py 传入）
const backendPort = process.env.VITE_BACKEND_PORT || 6003
const frontendPort = parseInt(process.env.VITE_FRONTEND_PORT || '5173', 10)

export default defineConfig({
  plugins: [vue()],
  server: {
    port: frontendPort,
    host: true,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
      '/data': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist'
  }
})
