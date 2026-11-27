<script lang="ts">
	import ProfileForm from '#lib/components/ProfileForm.svelte';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
</script>

<section class="space-y-6 py-8">
	<h1 class="text-2xl font-light">Settings</h1>
	{#if form && 'saved' in form}<p class="text-sm text-grove-700" role="status">Saved.</p>{/if}
	<ProfileForm
		traditions={data.traditions}
		profile={data.profile}
		submitLabel="Save"
		error={form && 'error' in form ? form.error : null}
	/>
</section>
