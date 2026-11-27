import { describe, expect, it, vi } from 'vitest';
import { ApiError, createApi } from './api';

vi.mock('$app/env/public', () => ({ PUBLIC_API_URL: 'http://localhost:8000' }));

type Call = { url: string; headers: Record<string, string> };

function fakeFetch(status: number, body: unknown) {
	const calls: Call[] = [];
	const fn = (input: string, init?: { headers?: Record<string, string> }) => {
		calls.push({ url: input, headers: init?.headers ?? {} });
		return Promise.resolve(new Response(JSON.stringify(body), { status }));
	};
	return { fetch: fn as unknown as typeof fetch, calls };
}

describe('createApi', () => {
	it('sends the bearer token to /me', async () => {
		const f = fakeFetch(200, { user_id: 'u1' });
		await expect(createApi('tok', f.fetch, 'http://api').me()).resolves.toEqual({ user_id: 'u1' });
		expect(f.calls[0].url).toBe('http://api/me');
		expect(f.calls[0].headers.Authorization).toBe('Bearer tok');
	});

	it('omits the header without a token', async () => {
		const f = fakeFetch(200, { status: 'ok', env: 'local', adapters: {} });
		await createApi(null, f.fetch, 'http://api').health();
		expect(f.calls[0].headers.Authorization).toBeUndefined();
	});

	it('throws ApiError on failure', async () => {
		const f = fakeFetch(401, { detail: 'invalid token' });
		await expect(createApi('bad', f.fetch, 'http://api').me()).rejects.toBeInstanceOf(ApiError);
	});
});
