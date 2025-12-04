#!/bin/bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Ensure your_application is importable
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python -c "import your_application; print('your_application imported successfully')"