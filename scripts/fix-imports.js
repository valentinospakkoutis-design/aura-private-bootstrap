const fs = require('fs');
const path = require('path');

const directories = ['app', 'components', 'hooks', 'services', 'store', 'utils', 'constants', 'contexts'];

function getRelativePath(fromDir, toDir) {
  const relative = path.relative(fromDir, toDir);
  return relative.startsWith('.') ? relative : `./${relative}`;
}

function replaceInFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;
  const fileDir = path.dirname(filePath);

  // Find all @/ imports
  const importRegex = /from\s+['"]@\/([^'"]+)['"]/g;
  
  content = content.replace(importRegex, (match, importPath) => {
    // Calculate relative path from current file to target
    const targetPath = path.join(process.cwd(), 'mobile/src', importPath);
    const relativePath = getRelativePath(fileDir, path.dirname(targetPath));
    const fileName = path.basename(targetPath);
    const newImport = path.join(relativePath, fileName).replace(/\\/g, '/');
    
    changed = true;
    return `from '${newImport}'`;
  });

  if (changed) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`✅ Fixed: ${filePath}`);
    return true;
  }
  return false;
}

function walkDirectory(dir) {
  const files = fs.readdirSync(dir);
  let fixedCount = 0;
  
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory() && !file.startsWith('.') && file !== 'node_modules') {
      fixedCount += walkDirectory(filePath);
    } else if (file.endsWith('.tsx') || file.endsWith('.ts') || file.endsWith('.js') || file.endsWith('.jsx')) {
      if (replaceInFile(filePath)) {
        fixedCount++;
      }
    }
  });
  
  return fixedCount;
}

console.log('🔧 Fixing @ imports...\n');

let totalFixed = 0;
directories.forEach(dir => {
  const dirPath = path.join(process.cwd(), dir);
  if (fs.existsSync(dirPath)) {
    console.log(`📁 Processing ${dir}/...`);
    totalFixed += walkDirectory(dirPath);
  }
});

// Also process mobile/src directory
const mobileSrcPath = path.join(process.cwd(), 'mobile/src');
if (fs.existsSync(mobileSrcPath)) {
  console.log(`📁 Processing mobile/src/...`);
  totalFixed += walkDirectory(mobileSrcPath);
}

console.log(`\n✅ Fixed ${totalFixed} files!`);
console.log('🚀 Ready to rebuild!');

