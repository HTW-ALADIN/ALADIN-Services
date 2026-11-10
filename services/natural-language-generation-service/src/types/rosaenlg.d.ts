declare module 'rosaenlg' {
	interface RosaeNlgRenderOptions extends Record<string, unknown> {
		language: 'en_US' | 'fr_FR' | 'de_DE' | 'it_IT' | 'es_ES';
		forceRandomSeed: number;
		compileDebug: false;
		cache: false;
	}

	interface RosaeNlg {
		render(template: string, options: RosaeNlgRenderOptions): string;
		getRosaeNlgVersion(): string;
	}

	const rosaeNlg: RosaeNlg;
	export default rosaeNlg;
}
