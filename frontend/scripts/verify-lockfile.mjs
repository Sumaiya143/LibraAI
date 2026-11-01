import fs from 'node:fs';
const pkg = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const path = new URL('../package-lock.json', import.meta.url);
if (!fs.existsSync(path)) {
  console.error('frontend/package-lock.json is missing. Run npm install once and commit the generated lockfile.');
  process.exit(1);
}
const lock = JSON.parse(fs.readFileSync(path, 'utf8'));
if (lock.lockfileVersion !== 3) throw new Error('Use npm lockfileVersion 3 for Node 20/npm 10 builds.');
const root = lock.packages?.[''];
if (!root) throw new Error('package-lock.json has no root package entry.');
for (const group of ['dependencies', 'devDependencies']) {
  for (const [name, version] of Object.entries(pkg[group] || {})) {
    const locked = root[group]?.[name];
    if (locked !== version) throw new Error(`${name} lock mismatch: package.json=${version}, lock=${locked ?? 'missing'}`);
  }
}
console.log('Frontend lockfile root dependencies match package.json.');
