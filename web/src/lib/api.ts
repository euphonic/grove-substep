import { PUBLIC_API_URL } from '$app/env/public';

export type Health = {
	status: string;
	env: string;
	adapters: Record<string, string>;
};

export type Me = { user_id: string };

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

/** Typed client for the FastAPI backend. SSE streaming arrives in M2. */
export function createApi(
	accessToken: string | null,
	fetchFn: typeof fetch = fetch,
	baseUrl: string = PUBLIC_API_URL
) {
	async function get<T>(path: string): Promise<T> {
		const headers: Record<string, string> = { Accept: 'application/json' };
		if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
		const res = await fetchFn(`${baseUrl}${path}`, { headers });
		if (!res.ok) throw new ApiError(res.status, `${path} failed: ${res.status}`);
		return (await res.json()) as T;
	}
	return {
		health: () => get<Health>('/health'),
		me: () => get<Me>('/me')
	};
}
