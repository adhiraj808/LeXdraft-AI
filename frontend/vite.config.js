import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    // Enable code splitting
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Vendor chunks
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom') || id.includes('react-router')) {
              return 'vendor-react';
            }
            if (id.includes('lucide-react') || id.includes('react-hot-toast')) {
              return 'vendor-ui';
            }
            if (id.includes('axios')) {
              return 'vendor-utils';
            }
            return 'vendor';
          }
          // Feature-based chunks
          if (id.includes('pages/DashboardPage')) return 'page-dashboard';
          if (id.includes('pages/CaseListPage') || id.includes('pages/CaseDetailPage') || id.includes('pages/NewCasePage')) {
            return 'page-cases';
          }
          if (id.includes('pages/LegalAssistantPage')) return 'page-legal-assistant';
          if (id.includes('pages/AdminPage')) return 'page-admin';
          if (id.includes('components/chat')) return 'chat-components';
        },
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },
    // Use esbuild for minification (faster, no extra dependency)
    minify: 'esbuild',
    // Enable CSS code splitting
    cssCodeSplit: true,
    // Reduce chunk size warning limit
    chunkSizeWarningLimit: 500,
    // Disable source maps for production
    sourcemap: false,
  },
  // Optimize dependencies
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'axios',
      'lucide-react',
      'react-hot-toast',
    ],
  },
})