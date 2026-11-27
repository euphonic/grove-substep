import { fail } from '@sveltejs/kit';
import { isValidEmail } from '#lib/routes.js';
import type { Actions } from './$types';

export const actions: Actions = {
	default: async ({ request, locals, url }) => {
		const raw = (await request.formData()).get('email');
		const email = typeof raw === 'string' ? raw.trim() : '';
		if (!isValidEmail(email)) {
			return fail(400, { email, error: 'Please enter a valid email address.' });
		}
		const { error } = await locals.supabase.auth.signInWithOtp({
			email,
			options: { emailRedirectTo: `${url.origin}/auth/callback` }
		});
		if (error) {
			return fail(500, { email, error: 'Could not send the link. Please try again.' });
		}
		return { sent: true, email };
	}
};
