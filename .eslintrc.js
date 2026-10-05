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
  rules: {
    "no-console": ["warn", { allow: ["warn", "error"] }],
  },
};
