<script lang="ts">
	import ProfileForm from '#lib/components/ProfileForm.svelte';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
</script>

<section class="space-y-6 py-8">
	<h1 class="text-2xl font-light">Welcome to the Grove</h1>
	<p class="text-grove-700">
		A quiet place to check in. Choose the tradition you'd like your meditations to draw on.
	</p>
	<ProfileForm
		traditions={data.traditions}
		profile={data.profile}
		submitLabel="Begin"
		error={form?.error}
	/>
</section>
