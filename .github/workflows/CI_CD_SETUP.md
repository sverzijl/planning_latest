# CI/CD Setup Documentation

## Overview

This project uses GitHub Actions for continuous integration and deployment. The CI/CD pipeline automatically runs tests, generates coverage reports, and ensures code quality on every push and pull request.

## Workflow Files

### 1. Tests Workflow (`.github/workflows/tests.yml`)

**Triggers:**
- Push to `master` or `main` branches
- Pull requests to `master` or `main` branches

**Matrix Strategy:**
- Python 3.11
- Python 3.12

**Steps:**
1. Checkout code
2. Set up Python environment
3. Cache pip dependencies for faster builds
4. Install project dependencies from `requirements.txt`
5. Run all tests with pytest
6. Run labor validation integration tests
7. Run labor calendar validation tests

**Expected Runtime:** 5-10 minutes

**Success Criteria:**
- All 266+ tests must pass
- No test failures or errors
- Exit code 0

### 2. Coverage Workflow (`.github/workflows/coverage.yml`)

**Triggers:**
- Push to `master` or `main` branches (not on PRs to reduce overhead)

**Steps:**
1. Checkout code
2. Set up Python 3.11
3. Cache pip dependencies
4. Install dependencies including `pytest-cov`
5. Run tests with coverage tracking
6. Upload coverage report to Codecov

**Coverage Reports:**
- XML format for Codecov upload
- Terminal output for immediate feedback

**Expected Coverage:** 80%+ (current coverage exceeds this)

## GitHub Repository Setup

### Step 1: Update Badge URLs

In `README.md`, replace the placeholder URLs with your repository information:

```markdown
![Tests](https://github.com/YOUR_USERNAME/YOUR_REPO/workflows/Tests/badge.svg)
![Coverage](https://github.com/YOUR_USERNAME/YOUR_REPO/workflows/Coverage/badge.svg)
```

Example for repository `sverzijl/planning_latest`:
```markdown
![Tests](https://github.com/sverzijl/planning_latest/workflows/Tests/badge.svg)
![Coverage](https://github.com/sverzijl/planning_latest/workflows/Coverage/badge.svg)
```

### Step 2: Enable GitHub Actions

1. Navigate to your GitHub repository
2. Click on the "Actions" tab
3. GitHub will automatically detect the workflow files in `.github/workflows/`
4. Click "I understand my workflows, go ahead and enable them"

### Step 3: Configure Codecov (Optional)

For coverage reporting:

1. Visit [codecov.io](https://codecov.io)
2. Sign in with GitHub
3. Add your repository
4. Copy the Codecov token (if private repository)
5. Add as GitHub secret:
   - Go to repository Settings → Secrets → Actions
   - Add new secret: `CODECOV_TOKEN` with the copied value

**Note:** For public repositories, Codecov token is not required.

### Step 4: Branch Protection Rules (Recommended)

To enforce passing tests before merging:

1. Go to Settings → Branches
2. Add branch protection rule for `master` (or `main`)
3. Enable "Require status checks to pass before merging"
4. Select required checks:
   - `test (3.11)`
   - `test (3.12)`
   - `coverage` (if desired)
5. Enable "Require branches to be up to date before merging"

## Local Pre-commit Hooks

### Installation

```bash
# Install pre-commit package
pip install pre-commit

# Install git hooks
pre-commit install
```

### Configuration

The `.pre-commit-config.yaml` file defines local hooks:

1. **pytest**: Runs all tests before commit
2. **pytest-labor-validation**: Runs labor validation tests
3. **black**: Auto-formats Python code
4. **flake8**: Lints code for style issues

### Usage

```bash
# Hooks run automatically on git commit
git commit -m "Your message"

# Manually run hooks on all files
pre-commit run --all-files

# Manually run specific hook
pre-commit run pytest --all-files

# Skip hooks (not recommended)
git commit --no-verify -m "Your message"
```

### Updating Hooks

```bash
# Update to latest versions
pre-commit autoupdate

# Clean and reinstall
pre-commit clean
pre-commit install
```

## Workflow Customization

### Adjusting Test Execution

To modify test behavior, edit `.github/workflows/tests.yml`:

**Run fewer tests for faster feedback:**
```yaml
- name: Run tests with pytest
  run: |
    pytest tests/ -v --tb=short --maxfail=1  # Stop after first failure
```

**Run specific test categories:**
```yaml
- name: Run unit tests only
  run: |
    pytest tests/test_models.py tests/test_parsers.py -v
```

**Add parallel execution (requires pytest-xdist):**
```yaml
- name: Run tests in parallel
  run: |
    pip install pytest-xdist
    pytest tests/ -v -n auto  # Auto-detect CPU count
```

### Adding Code Quality Checks

Add to `.github/workflows/tests.yml`:

```yaml
- name: Run black formatter check
  run: |
    pip install black
    black --check src/ tests/ ui/

- name: Run flake8 linter
  run: |
    pip install flake8
    flake8 src/ tests/ ui/ --max-line-length=100

- name: Run type checker
  run: |
    pip install mypy
    mypy src/ --ignore-missing-imports
```

### Adding Performance Tests

```yaml
- name: Run performance benchmarks
  run: |
    pytest tests/test_performance.py -v --benchmark-only
```

## Troubleshooting

### Issue: Workflow Not Triggering

**Symptoms:**
- No workflow runs appear in Actions tab
- Workflows don't run on push or PR

**Solutions:**
1. Verify workflow files are in `.github/workflows/` directory
2. Check YAML syntax: `yamllint .github/workflows/*.yml`
3. Ensure GitHub Actions is enabled for the repository
4. Check branch names match trigger conditions (`master` vs `main`)

### Issue: Tests Failing in CI but Pass Locally

**Common Causes:**
1. **Environment differences**: Different Python versions or OS
2. **Missing dependencies**: Check `requirements.txt` is complete
3. **File path issues**: Use absolute paths or path.join()
4. **Timezone differences**: Mock datetime or use UTC
5. **File system differences**: Case sensitivity on Linux vs Windows/Mac

**Debug Steps:**
```yaml
# Add debug step to workflow
- name: Debug environment
  run: |
    python --version
    pip list
    pwd
    ls -la
    echo $PYTHONPATH
```

### Issue: Slow Workflow Execution

**Optimization Strategies:**

1. **Use caching effectively:**
```yaml
- name: Cache pip dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
```

2. **Limit test scope on PRs:**
```yaml
on:
  pull_request:
    paths:
      - 'src/**'
      - 'tests/**'
      - 'requirements.txt'
```

3. **Use matrix strategy judiciously:**
```yaml
# Only test one Python version on PRs
strategy:
  matrix:
    python-version: ${{ github.event_name == 'pull_request' && ['3.11'] || ['3.11', '3.12'] }}
```

### Issue: Coverage Upload Failing

**Error:** "Error uploading coverage reports"

**Solutions:**
1. Verify Codecov token is set (for private repos)
2. Check coverage.xml is generated: Add debug step
```yaml
- name: Check coverage file
  run: ls -la coverage.xml
```
3. Set `fail_ci_if_error: false` to make upload optional

## Best Practices

### 1. Keep Tests Fast
- Target < 10 minutes total execution time
- Use fixtures and mocking to avoid slow I/O
- Run slow tests only on main branch

### 2. Use Meaningful Commit Messages
```bash
# Good
git commit -m "Add labor calendar validation tests (#42)"

# Bad
git commit -m "fix stuff"
```

### 3. Monitor Workflow Status
- Check Actions tab regularly
- Fix failing tests immediately
- Review coverage trends

### 4. Version Control Dependencies
```bash
# Pin versions for reproducibility
pandas==2.1.0
pytest==7.4.0

# Use >= for flexibility
pandas>=2.1.0
pytest>=7.4.0
```

### 5. Test Locally First
```bash
# Run full test suite before pushing
pytest tests/ -v

# Run coverage locally
pytest --cov=src --cov-report=term

# Run code quality checks
black src/ tests/ ui/
flake8 src/ tests/ ui/
```

## Workflow Status Examples

### All Tests Passing ✅
```
Tests / test (3.11) - Success
Tests / test (3.12) - Success
Coverage / coverage - Success
```

### Test Failure ❌
```
Tests / test (3.11) - Failed
  FAILED tests/test_labor_validation_integration.py::test_missing_dates
```

**Action:** Fix the failing test and push again

### Flaky Tests ⚠️
If tests pass locally but fail intermittently in CI:
1. Add retries for flaky tests:
```python
@pytest.mark.flaky(reruns=3)
def test_sometimes_fails():
    ...
```
2. Investigate timing issues, race conditions
3. Mock external dependencies

## Monitoring and Metrics

### Key Metrics to Track
1. **Pass Rate:** Should be 100%
2. **Execution Time:** Keep under 10 minutes
3. **Coverage:** Maintain 80%+ coverage
4. **Failure Rate:** Track frequency of failures

### GitHub Insights
- Go to repository Insights → Actions
- View workflow run history
- Analyze success rates and trends

## Advanced Configuration

### Conditional Workflows
```yaml
jobs:
  test:
    if: github.event_name == 'pull_request' || github.ref == 'refs/heads/master'
```

### Artifact Upload
```yaml
- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: test-results
    path: test-results/
```

### Notifications
```yaml
- name: Notify on failure
  if: failure()
  run: |
    curl -X POST ${{ secrets.SLACK_WEBHOOK }} \
      -d '{"text": "Tests failed on ${{ github.ref }}"}'
```

## Support

For issues with CI/CD setup:
1. Check workflow logs in GitHub Actions tab
2. Review this documentation
3. Consult GitHub Actions documentation
4. Open an issue in the repository

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Codecov Documentation](https://docs.codecov.com/)
- [pre-commit Documentation](https://pre-commit.com/)
