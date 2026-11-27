import { error } from '@sveltejs/kit';
import { createApi } from '#lib/api.js';
import type { RequestHandler } from './$types';

/** Proxies a chat turn to the API so the access token stays server-side. */
export const POST: RequestHandler = async ({ request, locals, fetch }) => {
	if (!locals.session) error(401, 'Not signed in');
	const body = (await request.json()) as { threadId?: unknown; text?: unknown };
	if (typeof body.threadId !== 'string' || typeof body.text !== 'string' || !body.text.trim()) {
		error(400, 'threadId and text are required');
	}
	const upstream = await createApi(locals.session.access_token, fetch).postMessage(
		body.threadId,
		body.text
	);
	if (!upstream.ok || !upstream.body) error(upstream.status === 404 ? 404 : 502, 'Chat failed');
	return new Response(upstream.body, {
		headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' }
	});
};
