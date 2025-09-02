import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({
			pages: '../ui_dist',
			assets: '../ui_dist',
			fallback: 'index.html', // Important for SPA mode
			precompress: false,
			strict: false // This helps avoid errors with routes not found
		})
	}
};

export default config;
