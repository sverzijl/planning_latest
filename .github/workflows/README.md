# GitHub Actions Workflows

This directory contains GitHub Actions CI/CD workflows for automated testing and quality assurance.

## Workflow Files

### `tests.yml` - Main Test Workflow

**Purpose:** Run comprehensive test suite on every push and pull request

**Triggers:**
- Push to `master` or `main` branches
- Pull requests targeting `master` or `main`

**Matrix:** Python 3.11 and 3.12

**Steps:**
1. Checkout code
2. Setup Python environment
3. Cache pip dependencies
4. Install requirements
5. Run all tests with pytest
6. Run labor validation tests
7. Run labor calendar validation tests

**Expected Runtime:** 5-10 minutes per Python version

**Badge:** `![Tests](https://github.com/USER/REPO/workflows/Tests/badge.svg)`

---

### `coverage.yml` - Coverage Workflow

**Purpose:** Generate and upload test coverage reports

**Triggers:**
- Push to `master` or `main` branches only

**Steps:**
1. Checkout code
2. Setup Python 3.11
3. Install dependencies + pytest-cov
4. Run tests with coverage
5. Upload to Codecov (optional)

**Output:** Coverage XML and terminal report

**Badge:** `![Coverage](https://github.com/USER/REPO/workflows/Coverage/badge.svg)`

---

## Documentation

### Quick Start
- **`QUICK_START.md`** - Fast onboarding guide for developers
  - 5-minute setup
  - Daily workflow
  - Common commands
  - Troubleshooting tips

### Detailed Setup
- **`CI_CD_SETUP.md`** - Comprehensive CI/CD documentation
  - Complete workflow configuration
  - GitHub setup instructions
  - Customization options
  - Advanced features
  - Best practices

---

## Validation

### Validate Your Setup

Before pushing to GitHub, validate the CI/CD configuration:

```bash
# Run validation script
python .github/workflows/validate_setup.py
```

**Checks performed:**
- ✓ Workflow file syntax
- ✓ Required project structure
- ✓ Python environment compatibility
- ✓ Test suite execution
- ✓ Pre-commit configuration
- ✓ Documentation completeness

**Expected output:**
```
GitHub Actions CI/CD Setup Validator
================================================================================
                          Validating Workflow Files
================================================================================

✓ Workflow directory exists: .github/workflows
ℹ Found: tests.yml - Main test workflow
✓   Valid YAML with 1 job(s)
ℹ Found: coverage.yml - Coverage reporting workflow
✓   Valid YAML with 1 job(s)

...

================================================================================
                            Validation Summary
================================================================================

Total checks: 6
Passed: 6
Failed: 0

✓ All validation checks passed!
Your CI/CD setup is ready to use.
```

---

## Pre-commit Hooks

### Setup

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Test hooks
pre-commit run --all-files
```

### Configuration

See `.pre-commit-config.yaml` in project root:

**Hooks:**
- `pytest` - Run all tests
- `pytest-labor-validation` - Run integration tests
- `black` - Format Python code
- `flake8` - Lint code

### Usage

```bash
# Hooks run automatically on commit
git commit -m "Your message"

# Run manually
pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

---

## Workflow Status

### Monitoring

1. **Push changes** to GitHub
2. **Navigate to** repository Actions tab
3. **Monitor** workflow execution in real-time
4. **Review** results and logs

### Status Icons

- ⏳ **Yellow circle** - Workflow running
- ✅ **Green checkmark** - All checks passed
- ❌ **Red X** - Tests failed
- ⚠️ **Yellow warning** - Some checks skipped

### Viewing Results

Click on workflow run → Expand job → View step details

---

## Local Testing

Before pushing, test locally to catch issues early:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific tests
pytest tests/test_labor_validation_integration.py -v

# Format code
black src/ tests/ ui/

# Lint code
flake8 src/ tests/ ui/

# Type check
mypy src/
```

---

## Troubleshooting

### Common Issues

**1. Tests pass locally but fail in CI**
- Different Python versions (test with 3.11 and 3.12 locally)
- Missing dependencies in requirements.txt
- File path issues (absolute vs relative)

**2. Workflow not triggering**
- Check workflow YAML syntax
- Verify branch names match triggers
- Ensure GitHub Actions is enabled

**3. Slow execution**
- Use dependency caching (already configured)
- Reduce test scope on PRs
- Run expensive tests only on main branch

### Getting Help

1. Review workflow logs in GitHub Actions tab
2. Check documentation files in this directory
3. Run local validation: `python .github/workflows/validate_setup.py`
4. Open an issue with workflow logs

---

## Configuration Updates

### Update Badge URLs

In `README.md`, replace placeholders:

```markdown
<!-- Before -->
![Tests](https://github.com/USER/REPO/workflows/Tests/badge.svg)

<!-- After (example) -->
![Tests](https://github.com/sverzijl/planning_latest/workflows/Tests/badge.svg)
```

### Modify Test Execution

Edit `.github/workflows/tests.yml`:

```yaml
# Stop on first failure
pytest tests/ --maxfail=1

# Run in parallel
pip install pytest-xdist
pytest tests/ -n auto

# Verbose output
pytest tests/ -vv
```

### Add Code Quality Checks

```yaml
- name: Run black
  run: black --check src/ tests/ ui/

- name: Run flake8
  run: flake8 src/ tests/ ui/
```

---

## Test Coverage

### Current Coverage

**266+ tests** covering:
- Core models and data structures
- Excel parsers (multi-file, SAP IBP)
- Production and labor calculations
- Network routing and optimization
- Integrated end-to-end scenarios
- Labor calendar validation

**Target:** 80%+ code coverage

### Viewing Coverage

```bash
# Generate HTML report
pytest --cov=src --cov-report=html

# Open in browser
open htmlcov/index.html  # Mac
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## Best Practices

1. **Write tests first** - Test-driven development
2. **Keep tests fast** - Use mocking for slow operations
3. **Test locally** - Catch issues before CI
4. **Monitor status** - Fix failures immediately
5. **Meaningful commits** - Clear, descriptive messages
6. **Small PRs** - Easier to review and test

---

## Quick Commands Reference

```bash
# Validate setup
python .github/workflows/validate_setup.py

# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Format code
black src/ tests/ ui/

# Lint code
flake8 src/ tests/ ui/

# Install pre-commit
pip install pre-commit && pre-commit install

# Run pre-commit hooks
pre-commit run --all-files
```

---

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Codecov Documentation](https://docs.codecov.com/)
- [pre-commit Documentation](https://pre-commit.com/)

---

## Maintenance

### Regular Tasks

- **Weekly:** Review workflow execution times
- **Monthly:** Update dependencies and workflow versions
- **Quarterly:** Review and update test coverage goals

### Updating Workflows

1. Edit workflow YAML files
2. Validate syntax: `python .github/workflows/validate_setup.py`
3. Test in feature branch first
4. Monitor first execution
5. Merge to main if successful

---

## Support

For issues or questions:
1. Check documentation in this directory
2. Review GitHub Actions logs
3. Run validation script
4. Open repository issue with details

---

**Last Updated:** 2025-10-09
**Maintained By:** Development Team
