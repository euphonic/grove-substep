import { PUBLIC_API_URL } from '$app/env/public';

export type Health = {
	status: string;
	env: string;
	adapters: Record<string, string>;
};

export type Me = { user_id: string };

export type ThreadSummary = { id: string; created_at: string; last_message_at: string };

export type ChatMessage = { role: 'user' | 'assistant'; content: string };

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

/** Typed client for the FastAPI backend. Used server-side so tokens never reach the browser. */
export function createApi(
	accessToken: string | null,
	fetchFn: typeof fetch = fetch,
	baseUrl: string = PUBLIC_API_URL
) {
	function headers(extra: Record<string, string> = {}): Record<string, string> {
		const h: Record<string, string> = { Accept: 'application/json', ...extra };
		if (accessToken) h.Authorization = `Bearer ${accessToken}`;
		return h;
	}

	async function request<T>(method: 'GET' | 'POST', path: string): Promise<T> {
		const res = await fetchFn(`${baseUrl}${path}`, { method, headers: headers() });
		if (!res.ok) throw new ApiError(res.status, `${path} failed: ${res.status}`);
		return (await res.json()) as T;
	}

	return {
		health: () => request<Health>('GET', '/health'),
		me: () => request<Me>('GET', '/me'),
		listThreads: () => request<ThreadSummary[]>('GET', '/threads'),
		createThread: () => request<ThreadSummary>('POST', '/threads'),
		getMessages: (threadId: string) =>
			request<{ messages: ChatMessage[] }>(
				'GET',
				`/threads/${encodeURIComponent(threadId)}/messages`
			),
		/** Returns the raw SSE response so callers can pipe it. */
		postMessage: (threadId: string, text: string) =>
			fetchFn(`${baseUrl}/threads/${encodeURIComponent(threadId)}/messages`, {
				method: 'POST',
				headers: headers({ 'Content-Type': 'application/json', Accept: 'text/event-stream' }),
				body: JSON.stringify({ text })
			})
	};
}
