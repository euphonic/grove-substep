import { redirect } from '@sveltejs/kit';
import { createApi, type Me } from '#lib/api.js';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
	const api = createApi(locals.session?.access_token ?? null, fetch);
	const profile = await api.getProfile().catch(() => null);
	if (profile && !profile.onboarded) redirect(303, '/onboarding');
	let me: Me | null = null;
	let apiError: string | null = null;
	try {
		me = await api.me();
	} catch (err) {
		apiError = err instanceof Error ? err.message : 'API unreachable';
	}
	return { me, apiError };
};

export const actions: Actions = {
	signout: async ({ locals }) => {
		await locals.supabase.auth.signOut();
		redirect(303, '/login');
	}
};
