#!/usr/bin/env bash

set -e

echo "======================================="
echo "Zygotrip Backend Cleanup + Freeze Tool"
echo "======================================="

ROOT_DIR=$(pwd)

echo ""
echo "Scanning repository..."

# Show large files
echo ""
echo "Top large files:"
find . -type f -exec du -h {} + | sort -rh | head -20


echo ""
echo "Scanning junk directories..."

JUNK_DIRS=(
"venv"
"node_modules"
"__pycache__"
".pytest_cache"
".mypy_cache"
"logs"
"media"
".idea"
".vscode"
".DS_Store"
)

for dir in "${JUNK_DIRS[@]}"; do
    FOUND=$(find . -type d -name "$dir")
    if [ ! -z "$FOUND" ]; then
        echo "Found junk dir: $FOUND"
    fi
done


echo ""
echo "Scanning junk files..."

JUNK_FILES=(
"*.pyc"
"*.pyo"
"*.log"
"*.sqlite3"
"*.DS_Store"
)

for pattern in "${JUNK_FILES[@]}"; do
    FOUND=$(find . -type f -name "$pattern")
    if [ ! -z "$FOUND" ]; then
        echo "Found junk files matching $pattern"
    fi
done


echo ""
echo "Cleaning junk directories..."

for dir in "${JUNK_DIRS[@]}"; do
    find . -type d -name "$dir" -exec rm -rf {} +
done


echo ""
echo "Cleaning junk files..."

for pattern in "${JUNK_FILES[@]}"; do
    find . -type f -name "$pattern" -delete
done


echo ""
echo "Generating .gitignore..."

cat <<EOF > .gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Virtual environments
venv/
.env
.env.*

# Logs
logs/
*.log

# Django
media/
staticfiles/
db.sqlite3

# Node
node_modules/
npm-debug.log

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
EOF


echo ""
echo "Initializing Git repository..."

if [ ! -d ".git" ]; then
    git init
fi


echo ""
echo "Adding files..."

git add .


echo ""
echo "Creating backend freeze commit..."

git commit -m "Backend Freeze v1 - OTA core architecture stable"


echo ""
echo "Creating tag..."

git tag backend-freeze-v1


echo ""
echo "Repository status:"
git status


echo ""
echo "======================================="
echo "Backend freeze complete"
echo "======================================="