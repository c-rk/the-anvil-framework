# Putting Anvil on GitHub

## 1. Create the repo on GitHub

1. Go to github.com → **New repository**
2. Name it `anvil-framework` (or whatever)
3. Set to **Private** (recommended while in dev)
4. **Do NOT** initialize with README, .gitignore, or license — you'll push existing files

---

## 2. Initialize git locally

Open a terminal in `The_Anvil_Framework/anvil-03-1/`:

```bash
cd "O:\ClaudeWorks\The_Anvil_Framework\anvil-03-1"
git init
git branch -M main
```

---

## 3. Create .gitignore

Create `O:\ClaudeWorks\The_Anvil_Framework\anvil-03-1\.gitignore`:

```
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.eggs/

# Registry database (user-specific, auto-regenerated)
*.db

# Generated outputs from examples
*.png
*.csv
*.json
nozzle_result.*
sweep_*.csv

# Jupyter
.ipynb_checkpoints/

# Editors
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

---

## 4. First commit

```bash
git add .
git commit -m "Initial commit: Anvil framework v1.1.0"
```

---

## 5. Connect to GitHub and push

```bash
git remote add origin https://github.com/YOUR_USERNAME/anvil-framework.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

---

## 6. Verify

Go to `github.com/YOUR_USERNAME/anvil-framework` — all files should be there.

---

## Day-to-day workflow

### Making changes (with Claude or on your own)

```bash
# Check what changed
git status
git diff

# Stage and commit
git add src/anvil/units.py          # specific file
git add src/anvil/                  # whole folder
git add .                           # everything

git commit -m "fix: compound unit parser handles cm/s and g/s"

# Push to GitHub
git push
```

### Commit message conventions (recommended)

```
fix: short description       — bug fix
feat: short description      — new feature
refactor: short description  — code cleanup, no behavior change
docs: short description      — documentation only
test: short description      — adding/fixing tests
```

### Pulling changes (if editing on another machine)

```bash
git pull
```

---

## Working with Claude on future sessions

Tell Claude:

> "The Anvil framework is at `O:\ClaudeWorks\The_Anvil_Framework\anvil-03-1`. It's a git repo. Make changes, then I'll commit."

Claude edits files directly. You review with `git diff`, then commit yourself:

```bash
git diff                         # review all changes
git diff src/anvil/units.py      # review one file
git add .
git commit -m "feat: your description"
git push
```

---

## Optional: tag releases

When a stable version is ready:

```bash
git tag -a v1.1.0 -m "Stable: compound units, project registry, 55 RSQs"
git push origin v1.1.0
```

---

## If you ever need to undo

```bash
git diff HEAD          # see uncommitted changes
git restore file.py    # discard changes to one file (IRREVERSIBLE)
git restore .          # discard ALL uncommitted changes (IRREVERSIBLE)
git revert HEAD        # undo last commit (safe — creates new commit)
```
