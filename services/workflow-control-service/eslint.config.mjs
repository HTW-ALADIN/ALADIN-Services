import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["build/**", "node_modules/**", "coverage/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.ts"],
    languageOptions: { globals: { ...globals.node } },
  },
  {
    files: ["tests/**/*.mjs"],
    languageOptions: { globals: { ...globals.node } },
  },
);