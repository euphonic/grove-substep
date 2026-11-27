<script lang="ts">
	import Chat from '#lib/components/Chat.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<section class="space-y-4 py-6">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-light">Check in</h1>
		<form method="POST" action="?/new">
			<button class="text-sm underline">New conversation</button>
		</form>
	</div>
	{#key data.threadId}
		<Chat threadId={data.threadId} initial={data.messages} />
	{/key}
</section>
