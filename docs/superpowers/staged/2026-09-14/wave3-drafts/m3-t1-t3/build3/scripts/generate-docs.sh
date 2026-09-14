#!/bin/sh
#
# Generate Documentation (OpenAPI + TypeDoc)
#
# This script generates both API documentation from the backend OpenAPI spec
# and TypeScript documentation from the frontend source code.
#
# Usage:
#   ./scripts/generate-docs.sh              # Generate all docs
#   ./scripts/generate-docs.sh --api-only   # Generate only OpenAPI/Redoc
#   ./scripts/generate-docs.sh --ts-only    # Generate only TypeDoc
#   ./scripts/generate-docs.sh --serve      # Generate and serve locally
#   ./scripts/generate-docs.sh --help       # Show help
#
# Requirements:
#   - Python 3.14+ with backend dependencies installed
#   - Node.js 20.19+ with frontend dependencies installed
#   - npm packages: typedoc, typedoc-plugin-markdown, @redocly/cli
#

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCS_OUTPUT_DIR="$PROJECT_ROOT/docs-output"

# Flags
API_ONLY=false
TS_ONLY=false
SERVE=false

# Colors (portable - works in sh)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    GREEN=''
    RED=''
    YELLOW=''
    CYAN=''
    NC=''
fi

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

print_step() {
    printf "${CYAN}> %s${NC}\n" "$1"
}

print_success() {
    printf "${GREEN}[OK] %s${NC}\n" "$1"
}

print_error() {
    printf "${RED}[ERROR] %s${NC}\n" "$1" >&2
}

print_warning() {
    printf "${YELLOW}[WARN] %s${NC}\n" "$1"
}

show_help() {
    cat << 'EOF'
Generate Documentation (OpenAPI + TypeDoc)

Usage:
    ./scripts/generate-docs.sh [OPTIONS]

Options:
    -h, --help       Show this help message
    --api-only       Generate only OpenAPI spec and Redoc HTML
    --ts-only        Generate only TypeDoc documentation
    --serve          Generate docs and start a local server

Output:
    docs-output/
    ├── api/
    │   └── openapi.json       # OpenAPI specification
    ├── api-html/
    │   └── index.html         # Redoc HTML documentation
    └── typescript/
        └── README.md          # TypeDoc markdown output

Examples:
    ./scripts/generate-docs.sh           # Generate all documentation
    ./scripts/generate-docs.sh --serve   # Generate and serve at localhost:8080

Requirements:
    Backend:  Python 3.14+, .venv with backend dependencies
    Frontend: Node.js 20.19+/22.12+, npm with typedoc installed
              Optional: @redocly/cli for HTML generation

EOF
    exit 0
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

# ─────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ─────────────────────────────────────────────────────────────────────────────

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            show_help
            ;;
        --api-only)
            API_ONLY=true
            shift
            ;;
        --ts-only)
            TS_ONLY=true
            shift
            ;;
        --serve)
            SERVE=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Main Script
# ─────────────────────────────────────────────────────────────────────────────

cd "$PROJECT_ROOT"

# Create output directory
mkdir -p "$DOCS_OUTPUT_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# Generate OpenAPI Documentation
# ─────────────────────────────────────────────────────────────────────────────

if [ "$TS_ONLY" = false ]; then
    print_step "Generating OpenAPI specification..."

    # Check Python environment
    VENV_DIR="$PROJECT_ROOT/.venv"
    if check_command uv; then
        PYTHON_CMD="uv run python"
    elif [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1091
        . "$VENV_DIR/bin/activate"
        PYTHON_CMD="python"
    else
        print_error "Python environment not found. Run 'uv sync' or './scripts/setup.sh' first."
        exit 1
    fi

    # Generate OpenAPI spec
    mkdir -p "$DOCS_OUTPUT_DIR/api"
    export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://user:password@localhost:5432/security}"  # pragma: allowlist secret
    export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

    $PYTHON_CMD -c "
from backend.main import app
import json

spec = app.openapi()
with open('$DOCS_OUTPUT_DIR/api/openapi.json', 'w') as f:
    json.dump(spec, f, indent=2)
print(f'OpenAPI spec: {len(spec.get(\"paths\", {}))} paths')
"
    print_success "OpenAPI specification generated: $DOCS_OUTPUT_DIR/api/openapi.json"

    # Generate Redoc HTML (if redocly-cli is available)
    if check_command npx && npm list -g @redocly/cli >/dev/null 2>&1 || [ -d "$PROJECT_ROOT/frontend/node_modules/@redocly/cli" ]; then
        print_step "Generating Redoc HTML documentation..."
        mkdir -p "$DOCS_OUTPUT_DIR/api-html"

        if npx --prefix "$PROJECT_ROOT/frontend" @redocly/cli build-docs \
            "$DOCS_OUTPUT_DIR/api/openapi.json" \
            --output "$DOCS_OUTPUT_DIR/api-html/index.html" \
            --title "Home Security Intelligence API" 2>/dev/null; then
            print_success "Redoc HTML generated: $DOCS_OUTPUT_DIR/api-html/index.html"
        else
            print_warning "Redoc generation failed. Install @redocly/cli for HTML docs."
        fi
    else
        print_warning "Skipping Redoc HTML (install @redocly/cli globally or locally)"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Generate TypeDoc Documentation
# ─────────────────────────────────────────────────────────────────────────────

if [ "$API_ONLY" = false ]; then
    print_step "Generating TypeDoc documentation..."

    if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
        print_error "Frontend dependencies not installed. Run: cd frontend && npm install"
        exit 1
    fi

    cd "$PROJECT_ROOT/frontend"

    # Check if typedoc is installed
    if [ ! -d "node_modules/typedoc" ]; then
        print_warning "TypeDoc not installed. Installing..."
        npm install --save-dev typedoc typedoc-plugin-markdown
    fi

    # Generate TypeDoc
    npx typedoc

    print_success "TypeDoc generated: $DOCS_OUTPUT_DIR/typescript/"
    cd "$PROJECT_ROOT"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Serve Documentation (if requested)
# ─────────────────────────────────────────────────────────────────────────────

if [ "$SERVE" = true ]; then
    print_step "Starting documentation server..."

    # Create a simple index.html if it doesn't exist
    if [ ! -f "$DOCS_OUTPUT_DIR/index.html" ]; then
        cat > "$DOCS_OUTPUT_DIR/index.html" << 'INDEXEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Documentation Index</title>
    <style>
        body { font-family: system-ui; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        h1 { color: #333; }
        ul { list-style: none; padding: 0; }
        li { margin: 1rem 0; }
        a { color: #0066cc; text-decoration: none; font-size: 1.2rem; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Documentation</h1>
    <ul>
        <li><a href="api-html/index.html">API Documentation (Redoc)</a></li>
        <li><a href="api/openapi.json">OpenAPI Specification (JSON)</a></li>
        <li><a href="typescript/README.md">TypeScript Documentation</a></li>
    </ul>
</body>
</html>
INDEXEOF
    fi

    # Use Python's built-in HTTP server
    print_success "Documentation available at: http://localhost:8080"
    print_success "Press Ctrl+C to stop"
    cd "$DOCS_OUTPUT_DIR"
    python3 -m http.server 8080
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

echo ""
printf "${GREEN}============================================${NC}\n"
printf "${GREEN}  Documentation generated successfully!${NC}\n"
printf "${GREEN}============================================${NC}\n"
echo ""
echo "Output directory: $DOCS_OUTPUT_DIR"
echo ""
if [ "$TS_ONLY" = false ]; then
    echo "  - OpenAPI spec:  $DOCS_OUTPUT_DIR/api/openapi.json"
    if [ -f "$DOCS_OUTPUT_DIR/api-html/index.html" ]; then
        echo "  - API docs HTML: $DOCS_OUTPUT_DIR/api-html/index.html"
    fi
fi
if [ "$API_ONLY" = false ]; then
    echo "  - TypeScript:    $DOCS_OUTPUT_DIR/typescript/"
fi
echo ""
echo "To view locally: ./scripts/generate-docs.sh --serve"
