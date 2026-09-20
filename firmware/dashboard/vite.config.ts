import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-auto';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				runes: ({ filename }) => filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter()
		})
	],
	ssr: {
		noExternal: ['bits-ui']
	},
	server: {
		port: 5173,
		proxy: {
			'/stream': { target: 'http://localhost:8080', changeOrigin: true },
			'/events': { target: 'http://localhost:8000', changeOrigin: true },
			'/cmd': { target: 'http://localhost:8000', changeOrigin: true },
			'/ik': { target: 'http://localhost:8000', changeOrigin: true },
			'/fk': { target: 'http://localhost:8000', changeOrigin: true },
			'/api': { target: 'http://localhost:8000', changeOrigin: true }
		}
	}
});
