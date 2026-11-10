declare module 'jsrealb' {
	export interface Realisable {
		realize(): string;
	}

	export interface JsRealB {
		fromJSON(
			value: Record<string, unknown>,
			language?: 'en' | 'fr'
		): Realisable | undefined;
		loadEn(trace?: boolean): void;
		loadFr(trace?: boolean): void;
		setExceptionOnWarning(value: boolean): void;
		jsRealB_version: string;
	}

	const jsRealB: JsRealB;
	export default jsRealB;
}
