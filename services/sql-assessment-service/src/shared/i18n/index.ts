/**
 * i18n public API.
 *
 * Usage:
 *
 *   import { t, resolveLanguageCode } from '../shared/i18n';
 *
 *   const lang = resolveLanguageCode(req.body.languageCode);
 *
 *   // simple message
 *   return res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
 *
 *   // legacy positional interpolation (replaces {{value}})
 *   return res.status(400).json({ message: t('QUERY_NON_SELECT', lang, statementType) });
 *
 *   // named-placeholder interpolation (replaces {{expected}}, {{received}}, …)
 *   entry.message = t('FEEDBACK_GROUP_KEY', lang, { expected: refKey, received: stuKey });
 */

import { MESSAGES, MessageKey, SupportedLanguage } from './messages';

export { MessageKey, SupportedLanguage };
export { MESSAGES } from './messages';

/** The default language used when no (valid) language code is supplied. */
export const DEFAULT_LANGUAGE: SupportedLanguage = 'en';

/**
 * Normalises a raw language-code string into a supported language, falling
 * back to English for anything unrecognised or absent.
 *
 * Accepts full BCP 47 tags with region subtag (e.g. "de-AT" → "de") as well
 * as bare codes ("de", "en").
 */
export function resolveLanguageCode(raw: string | undefined | null): SupportedLanguage {
    if (!raw || typeof raw !== 'string') return DEFAULT_LANGUAGE;
    // Take only the primary language subtag, lower-cased.
    const primary = raw.split('-')[0].toLowerCase();
    if (primary in MESSAGES) return primary as SupportedLanguage;
    return DEFAULT_LANGUAGE;
}

/**
 * Looks up the translated message for the given key and language.
 *
 * Supports two interpolation styles:
 *
 * 1. Legacy positional: pass a single `string` as the third argument.
 *    It replaces the first `{{value}}` placeholder in the template.
 *
 * 2. Named placeholders: pass a `Record<string, string>` as the third argument.
 *    Every `{{key}}` occurrence in the template is replaced by the matching
 *    value from the record.  For example:
 *
 *    ```ts
 *    t('FEEDBACK_GROUP_KEY', lang, { expected: 'id', received: 'name' })
 *    // → "Expected id, got name."
 *    ```
 *
 * @param key     - The MessageKey identifying the message.
 * @param lang    - The target language (use resolveLanguageCode to obtain this).
 * @param params  - Optional interpolation: a positional string or a named-placeholder record.
 */
export function t(
    key: MessageKey,
    lang: SupportedLanguage,
    params?: string | Record<string, string>
): string {
    const catalogue = MESSAGES[lang] ?? MESSAGES[DEFAULT_LANGUAGE];
    const template = catalogue[key] ?? MESSAGES[DEFAULT_LANGUAGE][key];
    if (params === undefined) return template;
    if (typeof params === 'string') {
        return template.replace('{{value}}', params);
    }
    // Named-placeholder substitution
    return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) => params[name] ?? `{{${name}}}`);
}
