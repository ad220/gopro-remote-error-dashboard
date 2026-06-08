import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      '/admin': 'http://localhost:8083',
    },
  },
  build: {
    // Output into the backend's static folder so FastAPI can serve it
    outDir: '../backend/static',
    emptyOutDir: true,
  },
})
