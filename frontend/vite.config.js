import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, API calls go to the FastAPI server on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': { target: 'http://127.0.0.1:8000', ws: true } },
  },
})
