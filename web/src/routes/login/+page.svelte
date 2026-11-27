<script lang="ts">
	import type { PageProps } from './$types';

	let { form }: PageProps = $props();
</script>

<section class="space-y-6 py-12">
	<h1 class="text-2xl font-light">Sign in</h1>
	{#if form?.sent}
		<p>Check your email. We sent a sign-in link to <strong>{form.email}</strong>.</p>
	{:else}
		<form method="POST" class="space-y-4">
			<label class="block">
				<span class="text-sm">Email</span>
				<input
					name="email"
					type="email"
					required
					autocomplete="email"
					value={form?.email ?? ''}
					class="mt-1 block w-full rounded-lg border border-grove-100 bg-white px-3 py-2"
				/>
			</label>
			{#if form?.error}<p class="text-sm text-red-700">{form.error}</p>{/if}
			<button class="w-full rounded-lg bg-grove-700 px-4 py-2 text-white">
				Send me a magic link
			</button>
		</form>
	{/if}
</section>
