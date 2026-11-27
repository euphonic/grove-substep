<script lang="ts">
	import './layout.css';
	import { resolve } from '$app/paths';
	import favicon from '#lib/assets/favicon.svg';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>The Grove</title>
</svelte:head>

<div class="min-h-dvh bg-grove-50 text-grove-900">
	<header class="mx-auto flex max-w-xl items-center justify-between px-4 py-4">
		<a href={resolve('/')} class="text-lg font-bold tracking-wide">The Grove</a>
		{#if data.session}
			<nav class="flex gap-4 text-sm">
				<a href={resolve('/session')}>Session</a>
				<a href={resolve('/hold')}>The Hold</a>
				<a href={resolve('/settings')}>Settings</a>
			</nav>
		{/if}
	</header>
	<main class="mx-auto max-w-xl px-4 pb-16">
		{@render children()}
	</main>
</div>
