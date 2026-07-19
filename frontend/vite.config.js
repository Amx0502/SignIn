import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://0.0.0.0:8765',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://0.0.0.0:8765',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist'
  }
})
