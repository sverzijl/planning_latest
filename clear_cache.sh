#!/bin/bash
# Clear Python and Streamlit caches
# Run this script if you encounter import errors after refactoring

echo "🧹 Clearing Python bytecode cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "🧹 Clearing Streamlit cache..."
rm -rf .streamlit/cache 2>/dev/null

echo "✅ Cache cleared successfully!"
echo ""
echo "To verify imports work:"
echo "  source venv/bin/activate"
echo "  python test_imports.py"
echo ""
echo "To start the application:"
echo "  streamlit run ui/app.py"
