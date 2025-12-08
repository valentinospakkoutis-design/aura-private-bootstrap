#!/bin/bash
# AURA Auto-Commit Script
# Automatically commits and pushes changes to GitHub

MESSAGE="${1:-Auto-commit: Update project files}"
PUSH="${2:-true}"

echo ""
echo "🔄 AURA Auto-Commit Script"
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "❌ Git repository not found. Run 'git init' first."
    exit 1
fi

# Check for changes
if [ -z "$(git status --porcelain)" ]; then
    echo "✅ No changes to commit."
    exit 0
fi

echo "📝 Changes detected:"
git status --short

# Add all changes
echo ""
echo "➕ Staging changes..."
git add .

# Create commit message with timestamp
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
COMMIT_MESSAGE="$MESSAGE [$TIMESTAMP]"

# Commit changes
echo "💾 Committing changes..."
git commit -m "$COMMIT_MESSAGE"

if [ $? -ne 0 ]; then
    echo "❌ Commit failed!"
    exit 1
fi

echo "✅ Changes committed successfully!"

# Push to GitHub
if [ "$PUSH" = "true" ]; then
    echo ""
    echo "🚀 Pushing to GitHub..."
    
    # Get current branch
    BRANCH=$(git branch --show-current)
    
    if [ -z "$BRANCH" ]; then
        echo "⚠️  No branch detected. Creating 'main' branch..."
        git branch -M main
        BRANCH="main"
    fi
    
    git push origin "$BRANCH"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully pushed to GitHub!"
    else
        echo "⚠️  Push failed. You may need to set up remote:"
        echo "   git remote add origin <your-github-repo-url>"
        echo "   git push -u origin $BRANCH"
    fi
fi

echo ""
echo "✨ Done!"
echo ""

