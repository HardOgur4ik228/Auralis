# =============================================================================
# Publishes the Auralis frontend (public/) to the gh-pages branch used by
# GitHub Pages. Run from the repo root:
#
#     powershell -ExecutionPolicy Bypass -File scripts/deploy-gh-pages.ps1
#
# Requires a git identity configured in the repo (it already is for this repo).
#
# How it works (zero risk to your working tree):
#   1. Copies public/ to a scratch folder outside the repo.
#   2. Builds a fresh tree from that folder via a private temporary index
#      (git read-tree --empty + git add + git write-tree).
#   3. Creates a commit from that tree with git commit-tree -- the gh-pages
#      branch keeps ONLY the static site files at its root (+ .nojekyll).
#   4. Force-pushes that commit to origin/gh-pages and updates the local ref.
# Never checks out another branch, so any open edits in your working tree
# are left untouched.
# Works on Windows PowerShell 5.1 and 7.x: git errors are handled via
# $LASTEXITCODE, never via $ErrorActionPreference.
# =============================================================================

$PSNativeCommandUseErrorActionPreference = $false
$ErrorActionPreference = "Continue"

$repo = Join-Path $PSScriptRoot ".."
Set-Location $repo

function Invoke-Git {
    $output = & git $args 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        $detail = ($output | Out-String).Trim()
        throw "git $($args -join ' ') exited with code $code$([Environment]::NewLine)$detail"
    }
    return $output
}

$scratch = Join-Path $env:TEMP "ghpages_site_$PID"
$gitDir = (Invoke-Git "rev-parse" "--absolute-git-dir").Trim()
$altIndex = Join-Path $gitDir "ghpages-index-$PID"

try {
    # 1. Copy site files out of the repo so git never sees partial state.
    Remove-Item -Recurse -Force $scratch -ErrorAction SilentlyContinue
    Copy-Item -Recurse public $scratch

    # 2. Fresh tree from the scratch folder using a private index.
    $env:GIT_INDEX_FILE = $altIndex
    try {
        Invoke-Git "read-tree" "--empty" | Out-Null
        Invoke-Git "--git-dir=$gitDir" "--work-tree=$scratch" "add" "-A" | Out-Null
        $tree = (Invoke-Git "write-tree").Trim()
    }
    finally {
        Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue
    }

    # 3. Commit the tree (gh-pages gets only the site, no history needed).
    $message = "Site update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $commit = (Invoke-Git "commit-tree" $tree "-m" $message).Trim()

    # 4. Publish (force: gh-pages is a mirror of public/ only).
    Invoke-Git "push" "-f" "origin" "$commit`:refs/heads/gh-pages" | Out-Null
    Invoke-Git "update-ref" "refs/heads/gh-pages" $commit | Out-Null

    $remoteUrl = Invoke-Git "remote" "get-url" "origin"
    if ($remoteUrl -match "github\.com[:/]([^/]+)/([^/]+?)(\.git)?$") {
        $pagesUrl = "https://$($Matches[1]).github.io/$($Matches[2])/"
    } else {
        $pagesUrl = "https://<your-username>.github.io/Auralis/"
    }
    Write-Host ""
    Write-Host "  Deployed OK -> $pagesUrl" -ForegroundColor Green
    Write-Host "  Settings -> Pages -> Build and deployment -> Source:" -ForegroundColor Yellow
    Write-Host "    Deploy from a branch -> gh-pages -> / (root) -> Save" -ForegroundColor Yellow
    Write-Host ""
}
catch {
    Write-Host "Deploy failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Remove-Item -Recurse -Force $scratch -ErrorAction SilentlyContinue
    Remove-Item -Force $altIndex -ErrorAction SilentlyContinue
}