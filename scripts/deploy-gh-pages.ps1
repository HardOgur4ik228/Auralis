# =============================================================================
# Publishes the Auralis frontend (public/) to the gh-pages branch used by
# GitHub Pages. Run from the repo root:
#
#     powershell -ExecutionPolicy Bypass -File scripts/deploy-gh-pages.ps1
#
# Requires a git identity configured in the repo (it already is for this repo).
# The gh-pages branch keeps ONLY the static site files at its root.
# =============================================================================

$ErrorActionPreference = "Stop"

$repo = Join-Path $PSScriptRoot ".."
Set-Location $repo

$current = git branch --show-current
$scratch = Join-Path $env:TEMP "ghpages_site_$PID"
$tmpBranch = "gh-pages-tmp-$PID"
$errorSeen = $false

try {
    # 1. Stage the site files in a scratch folder first, so `git rm` below
    #    cannot destroy the public/ directory we are about to copy from.
    Remove-Item -Recurse -Force $scratch -ErrorAction SilentlyContinue
    Copy-Item -Recurse public $scratch

    # 2. Orphan branch = fresh history containing only the site.
    git checkout --orphan $tmpBranch *> $null
    git rm -rf -q . 2>$null

    # 3. Site files land at the branch root (with .nojekyll from public/).
    Copy-Item -Recurse "$scratch\*" .
    Remove-Item -Recurse -Force $scratch, public -ErrorAction SilentlyContinue

    git add -A
    git commit -q -m "Site update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"

    # 4. Publish (force: gh-pages is a mirror of public/ only).
    git push -f origin "$tmpBranch`:gh-pages"
    Write-Host ""
    Write-Host "  Deployed to https://<your-username>.github.io/Auralis/" -ForegroundColor Green
    Write-Host "  Enable once: Settings -> Pages -> Deploy from a branch -> gh-pages -> / (root)" -ForegroundColor Yellow
    Write-Host ""
}
catch {
    Write-Host "Deploy failed: $($_.Exception.Message)" -ForegroundColor Red
    $errorSeen = $true
}
finally {
    # Always return home.
    if ($current) { git checkout -q $current 2>$null } else { git checkout -q main 2>$null }
    git branch -D $tmpBranch 2>$null
    Remove-Item -Recurse -Force $scratch -ErrorAction SilentlyContinue
    if ($errorSeen) { exit 1 }
}