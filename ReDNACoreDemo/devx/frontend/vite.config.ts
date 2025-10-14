import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  envPrefix: 'VITE_',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '127.0.0.1', // Bind to IPv4 explicitly
    port: 3100,
    proxy: {
      '/devx/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
})
