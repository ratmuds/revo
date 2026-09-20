<script lang="ts">
	import './layout.css';
	import '../app.css';

	let { children } = $props();
</script>

<div
	class="app-root min-h-screen bg-[#0c0c0c] text-white antialiased flex flex-col font-sans"
>{@render children()}</div>

<style>
	:global(body) {
		margin: 0;
		padding: 0;
		background-color: #0c0c0c;
		color: #ffffff;
		font-family: 'GeneralSans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
		overflow-x: hidden;
	}

	:global(*) {
		box-sizing: border-box;
	}
</style>
