#!/usr/bin/env node
/*
 * Verifies that TypeORM forwards `queryMode: 'extended'` to `pg` and that the
 * extended protocol rejects multi-command SQL.  Used by scripts/smoke-test.sh
 * against a real PostgreSQL instance; exits non-zero when the payload is
 * accepted.
 *
 * Environment: PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE,
 *              SMOKE_PAYLOAD (optional).
 */
const { DataSource } = require('typeorm');

if (!process.env.PG_HOST) {
    console.error('PG_HOST is required');
    process.exit(2);
}

const payload = process.env.SMOKE_PAYLOAD
    || "SELECT 'x\\'; COMMIT; DELETE FROM smoke_probe WHERE 1=0; --'";

(async () => {
    const dataSource = new DataSource({
        type: 'postgres',
        host: process.env.PG_HOST,
        port: Number(process.env.PG_PORT || 5432),
        username: process.env.PG_USER || 'postgres',
        password: process.env.PG_PASSWORD || '',
        database: process.env.PG_DATABASE || 'postgres',
        entities: [],
        synchronize: false,
    });

    await dataSource.initialize();
    const runner = dataSource.createQueryRunner();
    try {
        await runner.startTransaction();
        await runner.query('SET TRANSACTION READ ONLY');
        try {
            await runner.query({ text: payload, queryMode: 'extended' });
            console.log('EXTENDED_ACCEPTED');
            process.exitCode = 1;
        } catch (err) {
            console.log(String(err.message).split('\n')[0]);
        }
        await runner.rollbackTransaction();
    } finally {
        await runner.release();
        await dataSource.destroy();
    }
})().catch((err) => {
    console.error(err);
    process.exit(1);
});