import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        // VITE_API_URL is set to http://api:8003 inside Docker Compose so the
        // frontend container can reach the API container by service name.
        // Falls back to localhost for bare-metal development.
        target: process.env.VITE_API_URL || 'http://localhost:8003',
        changeOrigin: true,
      },
    },
  },
})
