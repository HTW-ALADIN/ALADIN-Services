import { Type, Static } from '@sinclair/typebox';

export const RegisterProviderRequestSchema = Type.Object(
	{
		name: Type.String({
			description:
				'Lowercase provider name, matching /^[a-z]+(-[a-z]+)*$/ (e.g. "mycompany", "eu-west").',
			pattern: '^[a-z]+(-[a-z]+)*$',
		}),
		baseUrl: Type.String({
			minLength: 1,
			description: 'OpenAI-compatible base URL for the provider.',
		}),
		apiKey: Type.String({
			minLength: 1,
			description: "The provider's API token.",
		}),
	},
	{
		$id: 'RegisterProviderRequest',
		title: 'RegisterProviderRequest',
		additionalProperties: false,
	}
);

export type RegisterProviderRequestType = Static<
	typeof RegisterProviderRequestSchema
>;

export const RegisterProviderResponseSchema = Type.Object(
	{
		registered: Type.Boolean(),
		mode: Type.Union([
			Type.Literal('gateway-admin-api'),
			Type.Literal('skipped'),
		]),
		message: Type.String(),
	},
	{ $id: 'RegisterProviderResponse', title: 'RegisterProviderResponse' }
);
