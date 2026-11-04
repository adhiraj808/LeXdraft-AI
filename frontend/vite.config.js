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
    // Vendor splitting is configured below via `advancedChunks` (the Rollup
    // `manualChunks` option is removed in Vite 8 / Rolldown).
    rollupOptions: {
      output: {
        advancedChunks: {
          minSize: 20 * 1024,
          groups: [
            {
              name: 'vendor-react',
              test: /node_modules\/(react|react-dom|react-router|react-router-dom|history|@remix-run)\//,
            },
            {
              name: 'vendor-ui',
              test: /node_modules\/(lucide-react|react-hot-toast)\//,
            },
            {
              name: 'vendor-utils',
              test: /node_modules\/(axios|follow-redirects|form-data|proxy-from-env)\//,
            },
            {
              name: 'vendor',
              test: /node_modules\//,
            },
            {
              name: 'page-dashboard',
              test: /src\/pages\/DashboardPage/,
            },
            {
              name: 'page-cases',
              test: /src\/pages\/(CaseListPage|CaseDetailPage|NewCasePage)/,
            },
            {
              name: 'page-legal-assistant',
              test: /src\/pages\/LegalAssistantPage/,
            },
            {
              name: 'page-admin',
              test: /src\/pages\/AdminPage/,
            },
            {
              name: 'chat-components',
              test: /src\/components\/chat\//,
            },
          ],
        },
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },
    // No minify option: Vite 8 (Rolldown) drops the esbuild-based minifier and
    // uses its built-in Oxc minifier by default. Setting minify: 'esbuild' here
    // made the production build fail, and the extra `npm install esbuild` in the
    // Dockerfile was only there to work around it.
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