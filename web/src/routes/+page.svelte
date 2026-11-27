<script lang="ts">
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<section class="space-y-4 py-8">
	<h1 class="text-2xl font-light">Welcome to the Grove</h1>
	<p>Signed in as <strong>{data.email}</strong>.</p>
	{#if data.me}
		<p class="text-sm text-grove-700">API sees you as <code>{data.me.user_id}</code>.</p>
	{:else}
		<p class="text-sm text-red-700">API check failed: {data.apiError}</p>
	{/if}
	<form method="POST" action="?/signout">
		<button class="text-sm underline">Sign out</button>
	</form>
</section>
