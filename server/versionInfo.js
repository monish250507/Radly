import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { config } from './config.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function loadPackageInfo() {
  try {
    const raw = readFileSync(path.join(__dirname, '../package.json'), 'utf8');
    const pkg = JSON.parse(raw);
    return { name: pkg.name, version: pkg.version };
  } catch {
    return { name: config.service.name, version: '0.0.0-unknown' };
  }
}

const pkg = loadPackageInfo();

export function getVersionInfo() {
  return {
    name: pkg.name,
    version: pkg.version,
    env: config.env,
    runtimeMode: config.runtimeMode,
    commitSha: process.env.VERCEL_GIT_COMMIT_SHA || null,
    nodeVersion: process.version
  };
}
