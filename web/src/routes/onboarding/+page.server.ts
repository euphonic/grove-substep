import { redirect } from '@sveltejs/kit';
import { createApi } from '#lib/api.js';
import { saveProfileForm } from '#lib/profileForm.js';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
	const api = createApi(locals.session?.access_token ?? null, fetch);
	const [traditions, profile] = await Promise.all([api.listTraditions(), api.getProfile()]);
	return { traditions, profile };
};

export const actions: Actions = {
	default: async ({ locals, fetch, request }) => {
		const api = createApi(locals.session?.access_token ?? null, fetch);
		const { error } = await saveProfileForm(api, request, await api.listTraditions());
		if (error) return error;
		redirect(303, '/session');
	}
};
