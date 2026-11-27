import { describe, expect, it } from 'vitest';
import { isPublicPath, isValidEmail } from './routes';

describe('isPublicPath', () => {
	it('allows login and callback only', () => {
		expect(isPublicPath('/login')).toBe(true);
		expect(isPublicPath('/auth/callback')).toBe(true);
		expect(isPublicPath('/')).toBe(false);
		expect(isPublicPath('/hold')).toBe(false);
		expect(isPublicPath('/loginx')).toBe(false);
	});
});

describe('isValidEmail', () => {
	it('accepts plain addresses and rejects junk', () => {
		expect(isValidEmail('a@b.co')).toBe(true);
		expect(isValidEmail(' a@b.co ')).toBe(true);
		expect(isValidEmail('nope')).toBe(false);
		expect(isValidEmail('a@b')).toBe(false);
	});
});
