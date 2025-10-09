# CI/CD Quick Start Guide

## New Developer Onboarding

### 1. Clone and Setup (5 minutes)

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/planning_latest.git
cd planning_latest

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install pre-commit black flake8 mypy
```

### 2. Verify Setup (2 minutes)

```bash
# Run all tests
pytest

# Expected output: 266+ tests passed

# Run with coverage
pytest --cov=src tests/

# Expected output: Coverage > 80%
```

### 3. Enable Pre-commit Hooks (Optional, 1 minute)

```bash
# Install hooks
pre-commit install

# Test hooks
pre-commit run --all-files
```

## Daily Development Workflow

### Before Starting Work

```bash
# Update from main branch
git checkout master
git pull origin master

# Create feature branch
git checkout -b feature/your-feature-name
```

### During Development

```bash
# Run tests frequently
pytest tests/test_your_module.py -v

# Run all tests before committing
pytest

# Format code
black src/ tests/ ui/

# Check code quality
flake8 src/ tests/ ui/
```

### Before Committing

```bash
# Ensure all tests pass
pytest tests/ -v

# Check coverage
pytest --cov=src --cov-report=term

# Format and lint
black src/ tests/ ui/
flake8 src/ tests/ ui/

# Commit (pre-commit hooks will run automatically)
git add .
git commit -m "Descriptive commit message"
```

### Pushing Changes

```bash
# Push to your feature branch
git push origin feature/your-feature-name

# Create pull request on GitHub
# GitHub Actions will automatically run tests
```

## Common Tasks

### Run Specific Tests

```bash
# Run single test file
pytest tests/test_models.py -v

# Run single test function
pytest tests/test_models.py::test_location_creation -v

# Run tests matching pattern
pytest -k "labor" -v

# Run only labor validation tests
pytest tests/test_labor_validation_integration.py -v
```

### Debug Test Failures

```bash
# Run with detailed output
pytest tests/test_models.py -vv

# Stop at first failure
pytest tests/ --maxfail=1

# Show local variables on failure
pytest tests/ -l

# Run with Python debugger
pytest tests/ --pdb
```

### Check Code Quality

```bash
# Auto-format code
black src/ tests/ ui/

# Check formatting without changing
black --check src/ tests/ ui/

# Lint code
flake8 src/ tests/ ui/ --max-line-length=100

# Type checking
mypy src/ --ignore-missing-imports
```

### Update Dependencies

```bash
# Install new package
pip install new-package

# Update requirements.txt
pip freeze > requirements.txt

# Or manually add to requirements.txt
echo "new-package>=1.0.0" >> requirements.txt
```

## Pull Request Checklist

Before creating a pull request:

- [ ] All tests pass locally (`pytest`)
- [ ] Code is formatted (`black src/ tests/ ui/`)
- [ ] No linting errors (`flake8 src/ tests/ ui/`)
- [ ] New tests added for new functionality
- [ ] Coverage maintained or improved
- [ ] Documentation updated (if needed)
- [ ] Commit messages are clear and descriptive
- [ ] Branch is up to date with master

## GitHub Actions Status

### Monitoring Your PR

1. Push your branch to GitHub
2. Create pull request
3. Go to "Checks" tab on PR
4. Monitor workflow execution

**Expected workflows:**
- Tests (Python 3.11) - ~5 minutes
- Tests (Python 3.12) - ~5 minutes

### Understanding Status Icons

- ⏳ Yellow circle: Workflow running
- ✅ Green checkmark: All tests passed
- ❌ Red X: Tests failed
- ⚠️ Yellow warning: Some checks skipped

### If Tests Fail

1. Click on failed check to see details
2. Expand failed test section
3. Read error message
4. Fix locally and push again

```bash
# Fix the issue
# Run tests locally
pytest

# Commit and push fix
git add .
git commit -m "Fix test failure in XYZ"
git push origin feature/your-feature-name

# GitHub Actions will run again automatically
```

## Troubleshooting

### "Tests pass locally but fail in CI"

**Common causes:**
- Different Python version (CI uses 3.11 and 3.12)
- Missing dependency in requirements.txt
- File path issues (absolute vs relative)
- Timezone or locale differences

**Solution:**
```bash
# Test with Python 3.11 locally
python3.11 -m pytest

# Check requirements.txt is complete
pip freeze > requirements-freeze.txt
diff requirements.txt requirements-freeze.txt
```

### "Pre-commit hooks are too slow"

**Solution:**
```bash
# Run only specific hooks
SKIP=pytest pre-commit run --all-files

# Or disable hooks temporarily
git commit --no-verify -m "WIP: work in progress"

# Re-enable and fix before pushing
pre-commit run --all-files
```

### "Coverage decreased"

**Solution:**
```bash
# Generate detailed coverage report
pytest --cov=src --cov-report=html

# Open htmlcov/index.html in browser
# Add tests for uncovered lines

# Verify coverage improved
pytest --cov=src --cov-report=term
```

## Tips and Best Practices

### 1. Write Tests First (TDD)
```python
# Write test for new feature
def test_new_feature():
    result = new_feature()
    assert result == expected

# Implement feature to make test pass
def new_feature():
    return expected
```

### 2. Keep Commits Small
```bash
# Good: Small, focused commits
git commit -m "Add labor calendar validation"
git commit -m "Fix edge case in date handling"

# Bad: Large, unfocused commits
git commit -m "Add feature and fix bugs and update docs"
```

### 3. Use Descriptive Branch Names
```bash
# Good
git checkout -b feature/labor-calendar-validation
git checkout -b bugfix/date-parsing-error
git checkout -b docs/update-readme

# Bad
git checkout -b fix
git checkout -b temp
```

### 4. Run Tests Before Pushing
```bash
# Create alias for convenience
alias test-all='pytest tests/ -v && black --check src/ tests/ ui/ && flake8 src/ tests/ ui/'

# Use before pushing
test-all && git push
```

### 5. Monitor CI/CD Status
- Enable GitHub notifications for CI/CD
- Fix failures immediately
- Don't merge failing PRs

## Quick Reference Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific tests
pytest tests/test_models.py -v

# Format code
black src/ tests/ ui/

# Lint code
flake8 src/ tests/ ui/

# Type check
mypy src/

# Pre-commit hooks
pre-commit run --all-files

# Update pre-commit
pre-commit autoupdate
```

## Getting Help

1. **Check documentation:**
   - README.md - Project overview
   - CLAUDE.md - Development guidelines
   - .github/workflows/CI_CD_SETUP.md - Detailed CI/CD docs

2. **Review workflow logs:**
   - GitHub Actions tab → Failed workflow → Expand sections

3. **Ask for help:**
   - Open an issue
   - Ask in pull request comments
   - Contact maintainers

## Next Steps

1. Read full documentation in `.github/workflows/CI_CD_SETUP.md`
2. Review project structure in `CLAUDE.md`
3. Explore example data in `data/examples/`
4. Start contributing!

---

**Happy coding!** 🚀
