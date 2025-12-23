#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting full project validation...${NC}"

# 1. Backend Validation
echo -e "\n${GREEN}=== Backend: Linting & Type Checking ===${NC}"
cd backend
echo "Running Ruff (Linting)..."
ruff check .
echo "Running Ruff (Formatting)..."
ruff format --check .
echo "Running MyPy (Type Checking)..."
mypy .
cd ..

# 2. Frontend Validation
echo -e "\n${GREEN}=== Frontend: Linting & Type Checking ===${NC}"
cd frontend
echo "Running ESLint..."
npm run lint
echo "Running Type Check..."
npx tsc --noEmit
# Check Prettier without writing
echo "Running Prettier Check..."
npx prettier --check "src/**/*.{ts,tsx}"
cd ..

# 3. Tests & Coverage
echo -e "\n${GREEN}=== Backend: Testing & Coverage (Threshold: 95%) ===${NC}"
# Run pytest with coverage report
cd backend
pytest --cov=. --cov-report=term-missing --cov-fail-under=95
cd ..

echo -e "\n${GREEN}=== Frontend: Testing ===${NC}"
cd frontend
npm run test -- --run
cd ..

echo -e "\n${GREEN}✅ VALIDATION SUCCESSFUL: codebase is healthy!${NC}"
