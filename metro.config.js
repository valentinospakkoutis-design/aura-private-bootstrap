// Learn more https://docs.expo.dev/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Add path alias support for @/ imports
const projectRoot = __dirname;
const mobileSrcPath = path.resolve(projectRoot, 'mobile/src');

config.resolver = {
  ...config.resolver,
  alias: {
    '@': mobileSrcPath,
  },
  extraNodeModules: {
    '@': mobileSrcPath,
  },
};

// Add watch folders
config.watchFolders = [
  projectRoot,
  mobileSrcPath,
];

module.exports = config;

