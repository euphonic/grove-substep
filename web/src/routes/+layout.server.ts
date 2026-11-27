import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = ({ locals }) => {
	return { session: locals.session, email: locals.user?.email ?? null };
};
