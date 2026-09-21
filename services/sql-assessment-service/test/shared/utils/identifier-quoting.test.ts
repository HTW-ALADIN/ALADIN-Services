import { describe, it, expect } from 'vitest';
import { quoteIdentifier } from '../../../src/shared/utils/identifier-quoting';

describe('quoteIdentifier', () => {
	it('wraps a plain identifier in double quotes', () => {
		expect(quoteIdentifier('orders')).toBe('"orders"');
	});

	it('preserves the declared case of mixed/uppercase identifiers', () => {
		expect(quoteIdentifier('ANGNR')).toBe('"ANGNR"');
		expect(quoteIdentifier('Mitarbeiter')).toBe('"Mitarbeiter"');
		expect(quoteIdentifier('unitPrice')).toBe('"unitPrice"');
	});

	it('doubles embedded double quotes', () => {
		expect(quoteIdentifier('weird"name')).toBe('"weird""name"');
		expect(quoteIdentifier('a"b"c')).toBe('"a""b""c"');
	});

	it('quotes identifiers with spaces and special characters', () => {
		expect(quoteIdentifier('order details')).toBe('"order details"');
		expect(quoteIdentifier('order-details')).toBe('"order-details"');
	});

	it('is transparent for lowercase identifiers in PostgreSQL semantics', () => {
		// "orders" resolves to the same object as the unquoted orders
		expect(quoteIdentifier('orders')).toBe('"orders"');
	});

	it('handles an identifier that is only quotes', () => {
		expect(quoteIdentifier('"')).toBe('""""');
	});
});
