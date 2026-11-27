import { error, redirect } from '@sveltejs/kit';
import { ApiError, createApi } from '#lib/api.js';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
	const api = createApi(locals.session?.access_token ?? null, fetch);
	let threadId = url.searchParams.get('thread');
	if (!threadId) {
		const threads = await api.listThreads();
		threadId = threads[0]?.id ?? (await api.createThread()).id;
	}
	try {
		const { messages } = await api.getMessages(threadId);
		return { threadId, messages };
	} catch (err) {
		if (err instanceof ApiError && err.status === 404) error(404, 'Conversation not found');
		throw err;
	}
};

export const actions: Actions = {
	new: async ({ locals, fetch }) => {
		const thread = await createApi(locals.session?.access_token ?? null, fetch).createThread();
		redirect(303, `/session?thread=${thread.id}`);
	}
};
