import { execFileSync } from 'node:child_process';
import path from 'node:path';

export default async function globalSetup() {
  const frontendDir = __dirname.includes('tests\\e2e') ? path.resolve(__dirname, '..', '..') : path.resolve(process.cwd());
  const repoRoot = path.resolve(frontendDir, '..');
  const pythonExecutable = path.join(repoRoot, 'venv', 'Scripts', 'python.exe');
  const managePy = path.join(repoRoot, 'manage.py');

  execFileSync(pythonExecutable, [managePy, 'seed_playwright_live'], {
    cwd: repoRoot,
    stdio: 'inherit',
  });
}