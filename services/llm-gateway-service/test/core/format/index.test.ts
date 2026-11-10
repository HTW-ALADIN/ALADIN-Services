import { expect } from 'chai';
import { getFormatAdapter } from '../../../src/core/format/index.js';
import { vercelFormatAdapter } from '../../../src/core/format/vercel.js';
import { openaiChatFormatAdapter } from '../../../src/core/format/openai-chat.js';
import { openaiResponsesFormatAdapter } from '../../../src/core/format/openai-responses.js';

describe('getFormatAdapter', () => {
	it('defaults to the Vercel adapter when format is omitted', () => {
		expect(getFormatAdapter(undefined)).to.equal(vercelFormatAdapter);
	});

	it('resolves the Vercel adapter explicitly', () => {
		expect(getFormatAdapter('vercel')).to.equal(vercelFormatAdapter);
	});

	it('resolves the OpenAI Chat Completions adapter', () => {
		expect(getFormatAdapter('openai-chat')).to.equal(openaiChatFormatAdapter);
	});

	it('resolves the OpenAI Responses adapter', () => {
		expect(getFormatAdapter('openai-responses')).to.equal(
			openaiResponsesFormatAdapter
		);
	});

	it('throws a clear error for an unknown format', () => {
		expect(() => getFormatAdapter('not-a-real-format')).to.throw(
			'Unknown "format"'
		);
	});
});
