// eslint.config.js — Aura mobile (Expo / React Native)
// Uses the official Expo ESLint config which covers React, React Native,
// hooks rules and TypeScript out of the box.
const { defineConfig } = require("eslint/config");

module.exports = defineConfig([
  {
    ignores: [
      "node_modules/**",
      ".expo/**",
      "dist/**",
      "android/**",
      "ios/**",
      "coverage/**",
      "android-webview/**",
      "backend/**",        // Python — linted separately
      "scripts/**",
    ],
  },
  {
    extends: ["expo"],
    rules: {
      // Treat console.warn/error as warnings in CI (console.log is noise)
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },
]);
