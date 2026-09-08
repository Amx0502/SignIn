import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

function blockSensitiveFileRequests() {
  return {
    name: 'block-sensitive-file-requests',
    enforce: 'pre',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        let pathname = ''
        try {
          pathname = decodeURIComponent(
            new URL(request.url || '/', 'http://localhost').pathname,
          ).replaceAll('\\', '/')
        } catch {
          response.statusCode = 400
          response.end('Bad Request')
          return
        }

        const normalizedPath = pathname.toLowerCase()
        const isBlocked = normalizedPath.startsWith('/@fs/')
          || normalizedPath.includes('/.ssh/')
          || normalizedPath.startsWith('/etc/')
          || /\/(?:\.env(?:\.[^/]*)?|[^/]*\.(?:pem|key|crt))$/.test(normalizedPath)

        if (isBlocked) {
          response.statusCode = 403
          response.setHeader('Content-Type', 'text/plain; charset=utf-8')
          response.end('Forbidden')
          return
        }
        next()
      })
    },
  }
}

export default defineConfig({
  plugins: [
    blockSensitiveFileRequests(),
    vue(),
    Components({
      dts: false,
      dirs: [],
      directives: true,
      resolvers: [ElementPlusResolver({ importStyle: 'css' })],
    }),
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    fs: {
      strict: true,
      deny: [
        '.env',
        '.env.*',
        '*.{crt,key,pem}',
        '**/.ssh/**',
        '**/id_rsa',
        '**/id_ed25519',
      ],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist'
  }
})
