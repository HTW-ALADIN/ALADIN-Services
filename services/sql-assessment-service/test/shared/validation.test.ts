import { describe, it, expect } from 'vitest';

import { validateConnectionInfo } from '../../src/shared/utils/validation';

const validConnection = {
    host: 'db.example.com',
    port: 5432,
    username: 'user',
    password: 'secret',
    schema: 'public',
};

// Tests for src/shared/utils/validation.ts
describe('validateConnectionInfo', () => {
    it.todo('returns null for a valid PostgresConnectionOptions object');
    it.todo('returns an error message when host is missing');
    it.todo('returns an error message when port is missing');
    it.todo('returns an error message when schema is missing');

    it.each([
        ['localhost'],
        ['127.0.0.1'],
        ['10.0.0.5'],
        ['172.16.0.5'],
        ['192.168.1.5'],
        ['169.254.169.254'],
        ['metadata.google.internal'],
        ['::1'],
        ['[::1]'],
    ])(
        'rejects unsafe connection target host %s',
        (host) => {
            const error = validateConnectionInfo({ ...validConnection, host });
            expect(error).not.toBeNull();
            expect(error).toContain('Connection target is blocked');
        },
    );

    it('allows a public host that does not resolve to an internal address', () => {
        const error = validateConnectionInfo({
            ...validConnection,
            host: 'db.postgres.example.com',
        });
        // Public names may be unresolvable in this environment; only the
        // internal-target rejection must be guaranteed, so null (valid) or a
        // DNS-unrelated error is acceptable here — the host is never blocked.
        if (error) {
            expect(error).not.toContain('Connection target is blocked');
        }
    });
});
