import { fail } from '@sveltejs/kit';
import type { createApi, Tradition } from './api';

type Api = ReturnType<typeof createApi>;

/** Shared by onboarding and settings: validate the form and save the profile. */
export async function saveProfileForm(api: Api, request: Request, traditions: Tradition[]) {
	const form = await request.formData();
	const tradition = form.get('default_tradition');
	const name = form.get('display_name');
	const timezone = form.get('timezone');
	if (typeof tradition !== 'string' || !traditions.some((t) => t.id === tradition)) {
		return { error: fail(400, { error: 'Please choose a tradition.' }) };
	}
	await api.putProfile({
		default_tradition: tradition,
		display_name: typeof name === 'string' ? name.trim() || null : null,
		timezone: typeof timezone === 'string' && timezone ? timezone : 'UTC'
	});
	return { error: null };
}
