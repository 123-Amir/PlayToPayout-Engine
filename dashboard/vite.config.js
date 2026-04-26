import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const isProd = process.env.NODE_ENV === 'production'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: isProd
          ? 'https://playtopayout-engine-2.onrender.com'
          : 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
