# AURA Auto-Commit Script
# Automatically commits and pushes changes to GitHub

param(
    [string]$Message = "Auto-commit: Update project files",
    [switch]$Push = $true
)

Write-Host "`n🔄 AURA Auto-Commit Script`n" -ForegroundColor Cyan

# Check if git is initialized
if (-not (Test-Path ".git")) {
    Write-Host "❌ Git repository not found. Run 'git init' first." -ForegroundColor Red
    exit 1
}

# Check for changes
$changes = git status --porcelain
if ([string]::IsNullOrWhiteSpace($changes)) {
    Write-Host "✅ No changes to commit." -ForegroundColor Green
    exit 0
}

Write-Host "📝 Changes detected:" -ForegroundColor Yellow
git status --short

# Add all changes
Write-Host "`n➕ Staging changes..." -ForegroundColor Cyan
git add .

# Create commit message with timestamp
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$commitMessage = "$Message [$timestamp]"

# Commit changes
Write-Host "💾 Committing changes..." -ForegroundColor Cyan
git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Commit failed!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Changes committed successfully!" -ForegroundColor Green

# Push to GitHub
if ($Push) {
    Write-Host "`n🚀 Pushing to GitHub..." -ForegroundColor Cyan
    
    # Get current branch
    $branch = git branch --show-current
    
    if ([string]::IsNullOrWhiteSpace($branch)) {
        Write-Host "⚠️  No branch detected. Creating 'main' branch..." -ForegroundColor Yellow
        git branch -M main
        $branch = "main"
    }
    
    git push origin $branch
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Successfully pushed to GitHub!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Push failed. You may need to set up remote:" -ForegroundColor Yellow
        Write-Host "   git remote add origin <your-github-repo-url>" -ForegroundColor Gray
        Write-Host "   git push -u origin $branch" -ForegroundColor Gray
    }
}

Write-Host "`n✨ Done!`n" -ForegroundColor Green

