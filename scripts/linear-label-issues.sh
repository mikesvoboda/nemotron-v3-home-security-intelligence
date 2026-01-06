#!/bin/bash
#
# linear-label-issues.sh - Add Linear labels to issues based on worktree name
#
# Usage:
#   ./scripts/linear-label-issues.sh NEM-1234 NEM-1235 NEM-1236
#   ./scripts/linear-label-issues.sh --label custom-label NEM-1234
#   ./scripts/linear-label-issues.sh --list-only NEM-1234  # Just show what would be done
#
# The label name is auto-discovered from the git worktree directory name.
# For example, if running from /path/to/skill4_abc123, the label will be "skill4".
#
# Requirements:
#   - LINEAR_API_KEY environment variable must be set
#   - jq must be installed
#   - curl must be installed

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Linear team ID for NEM
TEAM_ID="998946a2-aa75-491b-a39d-189660131392"

# Default label color (gray)
LABEL_COLOR="#6B7280"

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] ISSUE_ID [ISSUE_ID...]

Add a Linear label to one or more issues. The label name is auto-discovered
from the current git worktree directory name.

Options:
    -l, --label NAME    Override the auto-discovered label name
    -c, --color HEX     Label color in hex format (default: #6B7280)
    -n, --list-only     Dry run - show what would be done without making changes
    -h, --help          Show this help message

Examples:
    # Auto-discover label from worktree name and add to issues
    $(basename "$0") NEM-1234 NEM-1235

    # Use a custom label name
    $(basename "$0") --label my-feature NEM-1234

    # Dry run to see what would happen
    $(basename "$0") --list-only NEM-1234 NEM-1235
EOF
    exit 0
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Discover label name from worktree directory
discover_label_name() {
    local current_dir
    current_dir=$(pwd)

    # Check if we're in a claude-squad worktree
    if [[ "$current_dir" == *"/.claude-squad/worktrees/"* ]]; then
        # Extract the worktree directory name (e.g., skill4_188825c79e903ad3)
        local worktree_name
        worktree_name=$(basename "$current_dir")

        # Extract the label part (everything before the underscore and hash)
        # Pattern: name_hash or just name
        if [[ "$worktree_name" =~ ^([a-zA-Z0-9_-]+)_[a-f0-9]+$ ]]; then
            echo "${BASH_REMATCH[1]}"
        else
            echo "$worktree_name"
        fi
    else
        # Try to get from git worktree
        local worktree_path
        worktree_path=$(git rev-parse --show-toplevel 2>/dev/null || echo "")

        if [[ -n "$worktree_path" ]]; then
            local worktree_name
            worktree_name=$(basename "$worktree_path")

            if [[ "$worktree_name" =~ ^([a-zA-Z0-9_-]+)_[a-f0-9]+$ ]]; then
                echo "${BASH_REMATCH[1]}"
            else
                echo "$worktree_name"
            fi
        else
            log_error "Could not discover label name from directory"
            exit 1
        fi
    fi
}

# Make a GraphQL request to Linear
linear_graphql() {
    local query="$1"
    curl -s -X POST https://api.linear.app/graphql \
        -H "Content-Type: application/json" \
        -H "Authorization: $LINEAR_API_KEY" \
        --data-raw "$query"
}

# Check if label exists and get its ID
get_label_id() {
    local label_name="$1"
    local response
    response=$(linear_graphql "{\"query\": \"{ issueLabels(filter: { name: { eq: \\\"$label_name\\\" }, team: { id: { eq: \\\"$TEAM_ID\\\" } } }) { nodes { id name } } }\"}")

    echo "$response" | jq -r '.data.issueLabels.nodes[0].id // empty'
}

# Create a new label
create_label() {
    local label_name="$1"
    local label_color="$2"

    local response
    response=$(linear_graphql "{
        \"query\": \"mutation CreateLabel(\$input: IssueLabelCreateInput!) { issueLabelCreate(input: \$input) { success issueLabel { id name } } }\",
        \"variables\": {
            \"input\": {
                \"name\": \"$label_name\",
                \"teamId\": \"$TEAM_ID\",
                \"color\": \"$label_color\"
            }
        }
    }")

    local success
    success=$(echo "$response" | jq -r '.data.issueLabelCreate.success // false')

    if [[ "$success" == "true" ]]; then
        echo "$response" | jq -r '.data.issueLabelCreate.issueLabel.id'
    else
        log_error "Failed to create label: $(echo "$response" | jq -r '.errors[0].message // "Unknown error"')"
        exit 1
    fi
}

# Get issue UUID from identifier (e.g., NEM-1234)
get_issue_id() {
    local identifier="$1"
    local response
    response=$(linear_graphql "{\"query\": \"{ issue(id: \\\"$identifier\\\") { id identifier } }\"}")

    echo "$response" | jq -r '.data.issue.id // empty'
}

# Add label to issue
add_label_to_issue() {
    local issue_id="$1"
    local label_id="$2"

    local response
    response=$(linear_graphql "{\"query\": \"mutation { issueAddLabel(id: \\\"$issue_id\\\", labelId: \\\"$label_id\\\") { success } }\"}")

    echo "$response" | jq -r '.data.issueAddLabel.success // false'
}

# Main
main() {
    local label_name=""
    local label_color="$LABEL_COLOR"
    local list_only=false
    local issues=()

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -l|--label)
                label_name="$2"
                shift 2
                ;;
            -c|--color)
                label_color="$2"
                shift 2
                ;;
            -n|--list-only)
                list_only=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            -*)
                log_error "Unknown option: $1"
                usage
                ;;
            *)
                issues+=("$1")
                shift
                ;;
        esac
    done

    # Check requirements
    if [[ -z "${LINEAR_API_KEY:-}" ]]; then
        log_error "LINEAR_API_KEY environment variable is not set"
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed"
        exit 1
    fi

    if [[ ${#issues[@]} -eq 0 ]]; then
        log_error "No issue IDs provided"
        usage
    fi

    # Auto-discover label name if not provided
    if [[ -z "$label_name" ]]; then
        label_name=$(discover_label_name)
        log_info "Auto-discovered label name: ${YELLOW}$label_name${NC}"
    fi

    if $list_only; then
        echo ""
        log_info "Dry run - would perform the following:"
        echo "  Label: $label_name"
        echo "  Color: $label_color"
        echo "  Issues: ${issues[*]}"
        exit 0
    fi

    # Get or create label
    log_info "Checking for existing label '$label_name'..."
    local label_id
    label_id=$(get_label_id "$label_name")

    if [[ -z "$label_id" ]]; then
        log_info "Label not found, creating '$label_name' with color $label_color..."
        label_id=$(create_label "$label_name" "$label_color")
        log_success "Created label with ID: $label_id"
    else
        log_success "Found existing label with ID: $label_id"
    fi

    # Add label to each issue
    echo ""
    log_info "Adding label to ${#issues[@]} issue(s)..."
    echo ""

    local success_count=0
    local fail_count=0

    for identifier in "${issues[@]}"; do
        local issue_id
        issue_id=$(get_issue_id "$identifier")

        if [[ -z "$issue_id" ]]; then
            log_error "$identifier: Issue not found"
            ((fail_count++))
            continue
        fi

        local result
        result=$(add_label_to_issue "$issue_id" "$label_id")

        if [[ "$result" == "true" ]]; then
            log_success "$identifier: Label added"
            ((success_count++))
        else
            log_error "$identifier: Failed to add label"
            ((fail_count++))
        fi
    done

    echo ""
    log_info "Summary: ${GREEN}$success_count succeeded${NC}, ${RED}$fail_count failed${NC}"
}

main "$@"
