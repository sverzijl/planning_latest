# GitHub Actions CI/CD Deployment Checklist

Use this checklist to deploy the CI/CD pipeline to your GitHub repository.

## Pre-Deployment Validation

### Local Environment Checks

- [ ] **Python version verified**
  ```bash
  python --version  # Should be 3.11 or higher
  ```

- [ ] **Dependencies installed**
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **All tests passing locally**
  ```bash
  pytest
  # Expected: 266+ tests passed
  ```

- [ ] **Coverage acceptable**
  ```bash
  pytest --cov=src tests/
  # Expected: Coverage > 80%
  ```

- [ ] **Code quality checks passing**
  ```bash
  black --check src/ tests/ ui/
  flake8 src/ tests/ ui/
  ```

### CI/CD Files Validation

- [ ] **Run validation script**
  ```bash
  python .github/workflows/validate_setup.py
  # Expected: "✓ All validation checks passed!"
  ```

- [ ] **Workflow files exist**
  ```bash
  ls -la .github/workflows/
  # Should show: tests.yml, coverage.yml
  ```

- [ ] **YAML syntax valid**
  ```bash
  # Validation script checks this automatically
  # Or manually: python -c "import yaml; yaml.safe_load(open('.github/workflows/tests.yml'))"
  ```

- [ ] **Documentation files present**
  ```bash
  ls -la .github/workflows/*.md
  # Should show: CI_CD_SETUP.md, QUICK_START.md, README.md, DEPLOYMENT_CHECKLIST.md
  ```

- [ ] **Pre-commit config exists**
  ```bash
  ls -la .pre-commit-config.yaml
  ```

---

## Repository Configuration

### Step 1: Update Badge URLs

- [ ] **Open README.md**
- [ ] **Find badge section** (lines 3-5)
- [ ] **Replace `USER/REPO` with your repository**

  Example:
  ```markdown
  # Before
  ![Tests](https://github.com/USER/REPO/workflows/Tests/badge.svg)

  # After (replace with your username and repo name)
  ![Tests](https://github.com/sverzijl/planning_latest/workflows/Tests/badge.svg)
  ```

- [ ] **Save README.md**

### Step 2: Initial Commit

- [ ] **Stage all new files**
  ```bash
  git status
  # Should show all .github/workflows files as new
  ```

- [ ] **Commit CI/CD files**
  ```bash
  git add .github/
  git add .pre-commit-config.yaml
  git add CI_CD_IMPLEMENTATION_SUMMARY.md
  git add README.md
  git commit -m "Add GitHub Actions CI/CD pipeline

  - Main test workflow with Python 3.11 and 3.12
  - Coverage reporting workflow
  - Pre-commit hooks configuration
  - Comprehensive documentation
  - Validation tooling
  "
  ```

- [ ] **Verify commit**
  ```bash
  git log -1
  git show --stat
  ```

### Step 3: Push to GitHub

- [ ] **Push to remote repository**
  ```bash
  git push origin master
  # Or: git push origin main
  ```

- [ ] **Wait for push to complete**

---

## GitHub Repository Setup

### Step 4: Enable GitHub Actions

- [ ] **Navigate to repository on GitHub**
- [ ] **Click "Actions" tab**
- [ ] **If prompted, click "I understand my workflows, go ahead and enable them"**
- [ ] **Verify workflows appear in list:**
  - [ ] Tests
  - [ ] Coverage

### Step 5: Monitor First Workflow Run

- [ ] **Click on first workflow run** (triggered by your push)
- [ ] **Wait for completion** (~10 minutes)
- [ ] **Verify all jobs succeed:**
  - [ ] test (3.11) - Green checkmark
  - [ ] test (3.12) - Green checkmark
  - [ ] coverage - Green checkmark (if on master/main)

### Step 6: Verify Badges

- [ ] **Go to repository main page**
- [ ] **Scroll to README**
- [ ] **Verify badges display:**
  - [ ] Tests badge shows "passing"
  - [ ] Coverage badge shows percentage (if configured)
  - [ ] Python version badge shows "3.11+"

- [ ] **If badges not showing:**
  - Wait 2-3 minutes for GitHub to update
  - Clear browser cache
  - Verify badge URL matches repository exactly

---

## Optional Configuration

### Step 7: Branch Protection Rules (Recommended)

- [ ] **Go to Settings → Branches**
- [ ] **Click "Add rule"**
- [ ] **Branch name pattern:** `master` (or `main`)
- [ ] **Enable: "Require status checks to pass before merging"**
- [ ] **Select required checks:**
  - [ ] test (3.11)
  - [ ] test (3.12)
- [ ] **Enable: "Require branches to be up to date before merging"**
- [ ] **Enable: "Do not allow bypassing the above settings"** (optional)
- [ ] **Click "Create"**

### Step 8: Codecov Integration (Optional)

For public repositories (automatic):
- [ ] **No setup needed** - Coverage uploads automatically
- [ ] **Visit codecov.io** to view reports (after first run)

For private repositories:
- [ ] **Visit [codecov.io](https://codecov.io)**
- [ ] **Sign in with GitHub**
- [ ] **Add your repository**
- [ ] **Copy Codecov token**
- [ ] **Go to repository Settings → Secrets → Actions**
- [ ] **Click "New repository secret"**
- [ ] **Name:** `CODECOV_TOKEN`
- [ ] **Value:** [paste token]
- [ ] **Click "Add secret"**
- [ ] **Re-run coverage workflow to verify**

### Step 9: Install Pre-commit Hooks Locally (Recommended)

- [ ] **Install pre-commit package**
  ```bash
  pip install pre-commit
  ```

- [ ] **Install git hooks**
  ```bash
  pre-commit install
  ```

- [ ] **Test hooks**
  ```bash
  pre-commit run --all-files
  # Should run: pytest, black, flake8
  ```

- [ ] **Verify hooks work on commit**
  ```bash
  # Make a trivial change
  echo "# test" >> README.md
  git add README.md
  git commit -m "Test pre-commit hooks"
  # Should see hooks running
  ```

- [ ] **Revert test change if needed**
  ```bash
  git reset HEAD~1
  ```

---

## Post-Deployment Verification

### Step 10: Test Pull Request Workflow

- [ ] **Create test branch**
  ```bash
  git checkout -b test/ci-cd-verification
  ```

- [ ] **Make trivial change**
  ```bash
  echo "# CI/CD Test" >> README.md
  git add README.md
  git commit -m "Test CI/CD workflow"
  ```

- [ ] **Push branch**
  ```bash
  git push origin test/ci-cd-verification
  ```

- [ ] **Create pull request on GitHub**
- [ ] **Verify workflows run automatically**
- [ ] **Check "Checks" tab shows:**
  - [ ] test (3.11) - running or passed
  - [ ] test (3.12) - running or passed
- [ ] **Wait for completion**
- [ ] **Verify all checks pass**
- [ ] **Close/delete test PR**
  ```bash
  git checkout master
  git branch -D test/ci-cd-verification
  git push origin --delete test/ci-cd-verification
  ```

### Step 11: Verify Badge Functionality

- [ ] **View README on GitHub**
- [ ] **Click on "Tests" badge**
  - Should link to workflow runs
- [ ] **Click on "Coverage" badge** (if configured)
  - Should link to Codecov report
- [ ] **Verify badges update after workflow runs**

---

## Team Onboarding

### Step 12: Share Documentation

- [ ] **Share with team:**
  - [ ] `.github/workflows/QUICK_START.md` - For new developers
  - [ ] `.github/workflows/CI_CD_SETUP.md` - For detailed reference
  - [ ] `README.md` - Updated with CI/CD info

- [ ] **Schedule team walkthrough** (optional)
  - Show GitHub Actions tab
  - Demonstrate workflow execution
  - Explain pre-commit hooks
  - Review PR process with CI checks

### Step 13: Update Contributing Guidelines

- [ ] **Add to CONTRIBUTING.md** (if exists):
  - [ ] Require passing tests before PR
  - [ ] Mention pre-commit hooks
  - [ ] Link to CI/CD documentation

---

## Troubleshooting Checklist

### If Workflows Don't Appear

- [ ] **Check GitHub Actions is enabled:**
  - Repository Settings → Actions → General
  - Ensure "Allow all actions and reusable workflows" is selected

- [ ] **Verify workflow files location:**
  ```bash
  ls -la .github/workflows/
  # Should show tests.yml, coverage.yml in correct location
  ```

- [ ] **Check YAML syntax:**
  ```bash
  python .github/workflows/validate_setup.py
  ```

### If Tests Fail in CI but Pass Locally

- [ ] **Check Python version:**
  ```bash
  python --version
  # Test with 3.11 and 3.12 if possible
  ```

- [ ] **Verify all dependencies in requirements.txt:**
  ```bash
  pip freeze | grep -v "^-e" > requirements-local.txt
  diff requirements.txt requirements-local.txt
  ```

- [ ] **Check for file path issues:**
  - Use `pathlib.Path` for cross-platform compatibility
  - Avoid hardcoded paths

- [ ] **Review workflow logs:**
  - Actions tab → Failed workflow → Expand failed step

### If Badges Don't Show

- [ ] **Verify badge URL syntax:**
  ```markdown
  ![Tests](https://github.com/USERNAME/REPO/workflows/Tests/badge.svg)
  ```

- [ ] **Check workflow name matches:**
  - URL: `/workflows/Tests/`
  - File: `name: Tests`

- [ ] **Wait and refresh:**
  - GitHub takes 2-3 minutes to generate badges
  - Clear browser cache

- [ ] **Try direct badge URL in browser:**
  - Paste badge URL directly
  - Should show SVG image

---

## Success Criteria

All items checked = Successful deployment ✅

### Minimum Required
- [x] Local tests passing
- [x] Validation script passes
- [x] Workflows committed and pushed
- [x] GitHub Actions enabled
- [x] First workflow run succeeds
- [x] Badges display correctly

### Recommended
- [x] Branch protection enabled
- [x] Pre-commit hooks installed
- [x] Test PR created and verified
- [x] Team documentation shared

### Optional
- [ ] Codecov configured
- [ ] Team training completed
- [ ] Contributing guidelines updated
- [ ] Monitoring dashboard setup

---

## Rollback Procedure

If issues arise and you need to disable CI/CD:

### Temporary Disable

- [ ] **Rename workflow files:**
  ```bash
  mv .github/workflows/tests.yml .github/workflows/tests.yml.disabled
  mv .github/workflows/coverage.yml .github/workflows/coverage.yml.disabled
  git add .github/workflows/
  git commit -m "Temporarily disable CI/CD workflows"
  git push
  ```

### Complete Removal

- [ ] **Delete workflow files:**
  ```bash
  rm .github/workflows/tests.yml
  rm .github/workflows/coverage.yml
  git add .github/workflows/
  git commit -m "Remove CI/CD workflows"
  git push
  ```

- [ ] **Disable Actions on GitHub:**
  - Settings → Actions → General
  - Select "Disable actions"

---

## Post-Deployment Tasks

### Week 1
- [ ] Monitor workflow execution times
- [ ] Review any test failures
- [ ] Collect team feedback
- [ ] Fix any issues discovered

### Month 1
- [ ] Review coverage trends
- [ ] Optimize slow tests
- [ ] Update documentation based on feedback
- [ ] Consider additional workflows (security scanning, etc.)

### Ongoing
- [ ] Update workflow actions quarterly
- [ ] Review and update dependencies
- [ ] Monitor and maintain test coverage
- [ ] Refine based on team needs

---

## Completion

Date deployed: ________________

Deployed by: ________________

Initial workflow status: ________________

Notes:
_____________________________________________
_____________________________________________
_____________________________________________

---

**Next Steps After Completion:**

1. Share success with team
2. Monitor for issues in first week
3. Iterate and improve based on feedback
4. Consider Phase 5 features (advanced automation)

**Congratulations! Your CI/CD pipeline is live!** 🚀

---
