import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // All /api/* requests in dev are forwarded to the FastAPI backend
      '/api': {
        // Node gateway (8090) proxies RAG to FastAPI (8000) and serves /api/nav/*
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8090',
        changeOrigin: true,
      },
    },
  },
})
