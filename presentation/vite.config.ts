import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // геометрия перекрёстка берётся из frontend/ — тот же код, что рисует схему в приложении
  server: { port: 5180, fs: { allow: ['..'] } },
})
