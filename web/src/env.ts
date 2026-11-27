import { defineEnvVars } from '@sveltejs/kit/env';

const withDefault = (fallback: string) => (value: string | undefined) => value || fallback;

export const variables = defineEnvVars({
	PUBLIC_API_URL: {
		public: true,
		schema: withDefault('http://localhost:8000'),
		description: 'Base URL of the FastAPI backend'
	},
	PUBLIC_SUPABASE_URL: {
		public: true,
		schema: withDefault('http://127.0.0.1:54321'),
		description: 'Supabase API URL (local: printed by `supabase start`)'
	},
	PUBLIC_SUPABASE_ANON_KEY: {
		public: true,
		schema: withDefault(''),
		description: 'Supabase anon/publishable key (local: printed by `supabase start`)'
	}
});
