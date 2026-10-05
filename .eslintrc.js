module.exports = {
  extends: ["expo"],
  ignorePatterns: [
    "node_modules/",
    ".expo/",
    "dist/",
    "android/",
    "ios/",
    "coverage/",
    "android-webview/",
    "backend/",
    "scripts/",
  ],
  env: {
    node: true,
  },
  rules: {
    "no-console": ["warn", { allow: ["warn", "error"] }],
  },
  overrides: [
    {
      files: ["**/__tests__/**/*.[jt]s?(x)", "**/*.test.[jt]s?(x)", "**/*.spec.[jt]s?(x)"],
      env: {
        jest: true,
        node: true,
      },
    },
  ],
};
