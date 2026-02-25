import { describe, it, expect, beforeEach } from 'vitest';
import { SurfaceRealizationService } from '../../../src/generation/description/surface-realization-service';

describe('SurfaceRealizationService', () => {
    let service: SurfaceRealizationService;

    beforeEach(() => {
        service = new SurfaceRealizationService();
    });

    // -------------------------------------------------------------------------
    // separateWords
    // -------------------------------------------------------------------------

    describe('separateWords', () => {

        describe('English (lang="en")', () => {

            it('lowercases a plain lowercase string', () => {
                expect(service.separateWords('hello world', 'en')).toBe('hello world');
            });

            it('inserts a space at CamelCase boundaries and lowercases', () => {
                expect(service.separateWords('firstName', 'en')).toBe('first name');
            });

            it('replaces underscores with spaces and lowercases', () => {
                expect(service.separateWords('unit_price', 'en')).toBe('unit price');
            });

            it('replaces hyphens with spaces and lowercases', () => {
                expect(service.separateWords('order-date', 'en')).toBe('order date');
            });

            it('defaults to English when no lang is provided', () => {
                expect(service.separateWords('UnitPrice')).toBe('unit price');
            });

        });

        describe('German (lang="de")', () => {

            it('preserves original casing for a German alias', () => {
                expect(service.separateWords('Mitarbeiter', 'de')).toBe('Mitarbeiter');
            });

            it('inserts a space at CamelCase boundaries but preserves casing', () => {
                expect(service.separateWords('ErsterName', 'de')).toBe('Erster Name');
            });

            it('replaces underscores with spaces but preserves casing', () => {
                expect(service.separateWords('Einstellungs_datum', 'de')).toBe('Einstellungs datum');
            });

            it('does not lowercase German-aliased display names', () => {
                // A German alias like "Stückpreis" should come through unchanged.
                expect(service.separateWords('Stückpreis', 'de')).toBe('Stückpreis');
            });

        });

    });

    // -------------------------------------------------------------------------
    // pluralize
    // -------------------------------------------------------------------------

    describe('pluralize', () => {

        describe('English (lang="en")', () => {

            it('appends "s" to a word not ending in "s"', () => {
                expect(service.pluralize('employee', 'en')).toBe('employees');
            });

            it('leaves a word that already ends in "s" unchanged', () => {
                expect(service.pluralize('orders', 'en')).toBe('orders');
            });

            it('defaults to English when no lang is provided', () => {
                expect(service.pluralize('product')).toBe('products');
            });

        });

        describe('German (lang="de")', () => {

            it('returns the word unchanged (German pluralisation is irregular)', () => {
                expect(service.pluralize('Mitarbeiter', 'de')).toBe('Mitarbeiter');
            });

            it('does not append "s" even for words that would take it in English', () => {
                expect(service.pluralize('Produkt', 'de')).toBe('Produkt');
            });

        });

    });

    // -------------------------------------------------------------------------
    // formatName
    // -------------------------------------------------------------------------

    describe('formatName', () => {

        describe('English (lang="en")', () => {

            it('formats a snake_case column name to lower-case words', () => {
                expect(service.formatName('unit_price', 'en')).toBe('unit price');
            });

            it('formats a CamelCase name to lower-case words', () => {
                expect(service.formatName('firstName', 'en')).toBe('first name');
            });

            it('separates a trailing "id" suffix with a space', () => {
                expect(service.formatName('employee_id', 'en')).toBe('employee id');
            });

            it('pluralises when aggregation is COUNT', () => {
                expect(service.formatName('employee_id', 'en', 'COUNT')).toBe('employee ids');
            });

            it('pluralises when aggregation is SUM', () => {
                expect(service.formatName('unit_price', 'en', 'SUM')).toBe('unit prices');
            });

            it('pluralises when aggregation is AVG', () => {
                expect(service.formatName('unit_price', 'en', 'AVG')).toBe('unit prices');
            });

            it('does NOT pluralise when aggregation is MAX', () => {
                expect(service.formatName('unit_price', 'en', 'MAX')).toBe('unit price');
            });

            it('does NOT pluralise when aggregation is MIN', () => {
                expect(service.formatName('unit_price', 'en', 'MIN')).toBe('unit price');
            });

            it('defaults to English when no lang is provided', () => {
                expect(service.formatName('order_date')).toBe('order date');
            });

        });

        describe('German (lang="de")', () => {

            it('converts underscores to spaces but preserves casing', () => {
                // Raw DB name — no alias, so SurfaceRealizationService processes it.
                expect(service.formatName('unit_price', 'de')).toBe('unit price');
            });

            it('preserves casing of a German alias', () => {
                // When the alias map returns "Stückpreis", formatName should not lowercase it.
                expect(service.formatName('Stückpreis', 'de')).toBe('Stückpreis');
            });

            it('does NOT pluralise for COUNT in German', () => {
                // German pluralisation is skipped entirely.
                expect(service.formatName('Mitarbeiter', 'de', 'COUNT')).toBe('Mitarbeiter');
            });

            it('does NOT pluralise for SUM in German', () => {
                expect(service.formatName('Stückpreis', 'de', 'SUM')).toBe('Stückpreis');
            });

        });

    });

});
