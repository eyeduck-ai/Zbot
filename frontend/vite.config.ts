import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5487',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // 將大型依賴分割成獨立 chunk
          'vendor-react': ['react', 'react-dom'],
          'vendor-codemirror': [
            '@codemirror/state',
            '@codemirror/view',
            '@codemirror/commands',
            '@codemirror/language',
            '@codemirror/lang-json',
            '@codemirror/lint',
            '@codemirror/autocomplete',
          ],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
  },
})
