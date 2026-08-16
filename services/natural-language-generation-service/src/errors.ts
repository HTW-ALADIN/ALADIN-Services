export class ServiceError extends Error {
	constructor(
		public readonly code: string,
		public readonly status: number,
		public readonly title: string,
		detail: string
	) {
		super(detail);
		this.name = 'ServiceError';
	}
}

export interface Problem {
	type: string;
	title: string;
	status: number;
	detail: string;
	code: string;
	instance?: string;
}

export function toProblem(error: ServiceError, instance?: string): Problem {
	return {
		type: `https://github.com/HTW-ALADIN/ALADIN-Services/blob/master/services/natural-language-generation-service/README.md#${error.code}`,
		title: error.title,
		status: error.status,
		detail: error.message,
		code: error.code,
		...(instance === undefined ? {} : { instance }),
	};
}
