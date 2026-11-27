<script lang="ts">
	import type { Profile, Tradition } from '#lib/api.js';

	let {
		traditions,
		profile,
		submitLabel,
		error = null
	}: {
		traditions: Tradition[];
		profile: Profile;
		submitLabel: string;
		error?: string | null;
	} = $props();

	const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
</script>

<form method="POST" class="space-y-6">
	<fieldset class="space-y-3">
		<legend class="mb-2 text-sm">Your default tradition (you can switch any session)</legend>
		{#each traditions as t (t.id)}
			<label
				class="flex cursor-pointer gap-3 rounded-lg border border-grove-100 bg-white p-3 has-[:checked]:border-grove-700"
			>
				<input
					type="radio"
					name="default_tradition"
					value={t.id}
					checked={profile.default_tradition === t.id}
					required
					class="mt-1"
				/>
				<span>
					<span class="block font-bold">{t.display_name}</span>
					<span class="block text-sm text-grove-700">{t.description}</span>
				</span>
			</label>
		{/each}
	</fieldset>

	<label class="block">
		<span class="text-sm">What should we call you? (optional)</span>
		<input
			name="display_name"
			maxlength="60"
			value={profile.display_name ?? ''}
			class="mt-1 block w-full rounded-lg border border-grove-100 bg-white px-3 py-2"
		/>
	</label>
	<input type="hidden" name="timezone" value={timezone} />

	{#if error}<p class="text-sm text-red-700" role="alert">{error}</p>{/if}
	<button class="w-full rounded-lg bg-grove-700 px-4 py-2 text-white">{submitLabel}</button>
</form>
