import { Type, Static, TSchema } from '@sinclair/typebox';

/**
 * Recursive schema for a serializable MappingElement.
 *
 * The library's MappingElement<S> can be:
 *   - A JSONPath string
 *   - An array of JSONPath strings (try-first-match)
 *   - A MapperFunctions object ({ $path, $default? })
 *   - A plain nested object whose values are MappingElements
 *   - An array of MappingElements (template array → produces array output)
 *
 * Note: WireFunction ($formatting, $return, $disable) cannot be serialised
 * over HTTP and are therefore excluded from this schema.
 */

/**
 * The serializable subset of MapperFunctions<S>.
 * $formatting, $return and $disable are excluded because they require
 * JavaScript functions which cannot be passed via JSON.
 */
export const MapperFunctionsSchema = Type.Object(
	{
		$path: Type.Union([Type.String(), Type.Array(Type.String())], {
			description:
				'JSONPath expression(s) to extract a value from the input. ' +
				'When an array is provided, each path is tried in order and the ' +
				'first non-null result is returned.',
		}),
		$default: Type.Optional(
			Type.Union([Type.String(), Type.Number()], {
				description:
					'Fallback value used when the resolved value is null or undefined.',
			})
		),
	},
	{
		$id: 'MapperFunctions',
		title: 'MapperFunctions',
		description:
			'Advanced mapping directive. ' +
			'Note: $formatting, $return, and $disable require JavaScript functions ' +
			'and cannot be expressed in a JSON request body — use the npm library ' +
			'directly for those use-cases.',
		additionalProperties: false,
	}
);

export type MapperFunctionsType = Static<typeof MapperFunctionsSchema>;

/**
 * A single mapping value within a template.
 * Recursive union: string | MapperFunctions | object | array
 *
 * TypeBox's Type.Recursive allows us to create a self-referential schema
 * that generates a valid JSON Schema $ref cycle.
 */
export const MappingElementSchema = Type.Recursive(
	(Self) =>
		Type.Union(
			[
				// Plain JSONPath string
				Type.String({
					description:
						'A JSONPath expression evaluated against the input data.',
					examples: ['$.store.book[0].title', '$.user.name'],
				}),
				// Advanced MapperFunctions directive
				MapperFunctionsSchema,
				// Nested template object (recurse)
				Type.Record(Type.String(), Self, {
					description: 'A nested mapping template object.',
				}),
				// Array of MappingElements — maps each template over the input
				Type.Array(Self, {
					description:
						'An array of mapping elements. ' +
						'When all items are strings, tries each path in order (first-match). ' +
						'Otherwise maps each template over the input to produce an array result.',
				}),
			],
			{
				description:
					'A single mapping value: path string, advanced directive, nested object, or array.',
			}
		),
	{ $id: 'MappingElement' }
);

export type MappingElementType = Static<typeof MappingElementSchema>;

/**
 * A full mapping template: a plain object whose values are MappingElements.
 */
export const MappingTemplateSchema = Type.Record(
	Type.String(),
	MappingElementSchema,
	{
		$id: 'MappingTemplate',
		title: 'MappingTemplate',
		description:
			'A declarative JSON-to-JSON mapping template. Each key in the output ' +
			'object corresponds to a key in this template, whose value describes ' +
			'how to derive the output value from the input data.',
		examples: [
			{
				title: '$.book.title',
				author: '$.book.author.name',
				price: { $path: '$.book.price', $default: 0 },
				meta: { isbn: '$.book.isbn' },
			},
		],
	}
);

export type MappingTemplateType = Static<typeof MappingTemplateSchema>;

/**
 * Request body for POST /map and POST /map/async
 */
export const MapRequestSchema = Type.Object(
	{
		data: Type.Unknown({
			description:
				'The input JSON object to transform. Can be any valid JSON value ' +
				'(object, array, string, number, boolean, or null).',
			examples: [{ store: { book: [{ title: 'Moby Dick', price: 8.99 }] } }],
		}),
		template: MappingTemplateSchema,
	},
	{
		$id: 'MapRequest',
		title: 'MapRequest',
		description: 'Request body for a JSON mapping operation.',
		additionalProperties: false,
	}
);

export type MapRequestType = Static<typeof MapRequestSchema>;

/**
 * Success response body
 */
export const MapResponseSchema = Type.Object(
	{
		result: Type.Unknown({
			description:
				'The transformed JSON output produced by applying the template to the input data.',
		}),
	},
	{
		$id: 'MapResponse',
		title: 'MapResponse',
		description: 'Successful mapping result.',
	}
);

export type MapResponseType = Static<typeof MapResponseSchema>;

/**
 * Error response body (matches Fastify's default error shape)
 */
export const ErrorResponseSchema = Type.Object(
	{
		statusCode: Type.Number({ description: 'HTTP status code.' }),
		error: Type.String({ description: 'HTTP error name.' }),
		message: Type.String({ description: 'Human-readable error message.' }),
	},
	{
		$id: 'ErrorResponse',
		title: 'ErrorResponse',
		description: 'Error response returned when validation or mapping fails.',
	}
);

export type ErrorResponseType = Static<typeof ErrorResponseSchema>;
