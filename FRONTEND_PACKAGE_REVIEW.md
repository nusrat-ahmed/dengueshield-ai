# Frontend package.json — Verification Notes

The existing `frontend/package.json` should be preserved. Its exact dependency versions must remain aligned with `frontend/package-lock.json`; do not replace it with a newly guessed manifest.

Run these commands from the repository root in PowerShell:

```powershell
Get-Content .\frontend\package.json
```

To print the scripts and dependencies as formatted JSON:

```powershell
node -e "const p=require('./frontend/package.json'); console.log(JSON.stringify({name:p.name,version:p.version,scripts:p.scripts,dependencies:p.dependencies,devDependencies:p.devDependencies},null,2))"
```

To verify the lockfile is present:

```powershell
Test-Path .\frontend\package-lock.json
```

To list the npm scripts:

```powershell
cd frontend
npm run
```

The project has already demonstrated that this script exists and completes successfully:

```powershell
npm run typecheck
```

The Next.js production build command is:

```powershell
npm run build
```

A previous build attempt failed with a Node.js out-of-memory error on a machine reporting approximately 3.7 GB of physical RAM. This is a resource limitation observed during that attempt; it does not prove that the package manifest is invalid.

Before changing `package.json`:
1. Inspect the current file.
2. Check that `package-lock.json` corresponds to it.
3. Preserve the existing Next.js, React, and TypeScript versions.
4. Change only a script or dependency that is demonstrably missing.
5. Run `npm install` only when dependencies actually change.
6. Commit `package.json` and `package-lock.json` together when either is intentionally updated.
