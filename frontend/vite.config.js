import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['astrolabe-icon.svg'],
      manifest: {
        name: 'Astrolabe Research Feed',
        short_name: 'Astrolabe',
        description: 'Doom-scroll battery research paper summaries',
        theme_color: '#2563eb',
        background_color: '#0f172a',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/app',
        scope: '/',
        icons: [
          {
            src: '/astrolabe-icon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any maskable',
          },
        ],
      },
      workbox: {
        // Cache API responses for offline reading
        runtimeCaching: [
          {
            urlPattern: /^\/api\/papers/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'paper-api-cache',
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 60 * 24, // 24 hours
              },
            },
          },
          {
            urlPattern: /^\/api\/papers\/filters/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'filters-cache',
              expiration: {
                maxAgeSeconds: 60 * 60 * 24,
              },
            },
          },
        ],
      },
    }),
  ],
  server: {
    host: '0.0.0.0',   // expose to local network (phone access)
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8003',
        changeOrigin: true,
      },
    },
  },
})
