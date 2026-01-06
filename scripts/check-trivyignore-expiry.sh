#!/usr/bin/env bash
# Check for expired CVE review dates in .trivyignore
#
# This script parses the .trivyignore file for REVIEW BY dates and reports
# any CVEs whose review dates have passed.
#
# Usage:
#   ./scripts/check-trivyignore-expiry.sh [--warn-days N] [--file PATH]
#
# Options:
#   --warn-days N    Warn about CVEs expiring within N days (default: 14)
#   --file PATH      Path to .trivyignore file (default: .trivyignore)
#
# Exit codes:
#   0 - No expired CVEs
#   1 - Expired CVEs found
#   2 - CVEs expiring soon (warning only, if --warn-days used)

set -euo pipefail

# Defaults
WARN_DAYS=${WARN_DAYS:-14}
TRIVYIGNORE_FILE=".trivyignore"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --warn-days)
            WARN_DAYS="$2"
            shift 2
            ;;
        --file)
            TRIVYIGNORE_FILE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--warn-days N] [--file PATH]"
            echo ""
            echo "Check for expired CVE review dates in .trivyignore"
            echo ""
            echo "Options:"
            echo "  --warn-days N    Warn about CVEs expiring within N days (default: 14)"
            echo "  --file PATH      Path to .trivyignore file (default: .trivyignore)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if file exists
if [[ ! -f "$TRIVYIGNORE_FILE" ]]; then
    echo "Error: .trivyignore file not found at: $TRIVYIGNORE_FILE"
    exit 1
fi

# Get current date in seconds since epoch
CURRENT_DATE=$(date +%Y-%m-%d)
CURRENT_EPOCH=$(date -d "$CURRENT_DATE" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$CURRENT_DATE" +%s 2>/dev/null)
WARN_EPOCH=$((CURRENT_EPOCH + WARN_DAYS * 86400))

# Track results
EXPIRED_CVES=()
EXPIRING_SOON_CVES=()
MISSING_DATE_CVES=()
TOTAL_CVES=0

# Parse the file
# Look for patterns like:
#   # CVE-XXXX-YYYY - Description (REVIEW BY: YYYY-MM-DD)
# followed by the CVE entry line

current_cve=""
current_review_date=""

while IFS= read -r line; do
    # Check for CVE comment with review date
    if [[ "$line" =~ ^#[[:space:]]*(CVE-[0-9]+-[0-9]+)[[:space:]]*-.*\(REVIEW\ BY:[[:space:]]*([0-9]{4}-[0-9]{2}-[0-9]{2})\) ]]; then
        current_cve="${BASH_REMATCH[1]}"
        current_review_date="${BASH_REMATCH[2]}"
    # Check for CVE entry line (not a comment)
    elif [[ "$line" =~ ^(CVE-[0-9]+-[0-9]+)[[:space:]]*$ ]]; then
        cve_id="${BASH_REMATCH[1]}"
        TOTAL_CVES=$((TOTAL_CVES + 1))

        if [[ -n "$current_review_date" && "$current_cve" == "$cve_id" ]]; then
            # Parse the review date
            review_epoch=$(date -d "$current_review_date" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$current_review_date" +%s 2>/dev/null)

            if [[ $review_epoch -lt $CURRENT_EPOCH ]]; then
                EXPIRED_CVES+=("$cve_id (expired: $current_review_date)")
            elif [[ $review_epoch -lt $WARN_EPOCH ]]; then
                days_until=$((($review_epoch - $CURRENT_EPOCH) / 86400))
                EXPIRING_SOON_CVES+=("$cve_id (expires in ${days_until} days: $current_review_date)")
            fi
        else
            # CVE without a review date in the expected format
            MISSING_DATE_CVES+=("$cve_id")
        fi

        # Reset tracking
        current_cve=""
        current_review_date=""
    fi
done < "$TRIVYIGNORE_FILE"

# Report results
echo "========================================"
echo "Trivyignore CVE Expiration Check"
echo "========================================"
echo "File: $TRIVYIGNORE_FILE"
echo "Current date: $CURRENT_DATE"
echo "Warning threshold: $WARN_DAYS days"
echo "Total CVEs tracked: $TOTAL_CVES"
echo ""

exit_code=0

if [[ ${#EXPIRED_CVES[@]} -gt 0 ]]; then
    echo "EXPIRED CVEs (${#EXPIRED_CVES[@]}):"
    echo "-----------------------------------"
    for cve in "${EXPIRED_CVES[@]}"; do
        echo "  [EXPIRED] $cve"
    done
    echo ""
    exit_code=1
fi

if [[ ${#EXPIRING_SOON_CVES[@]} -gt 0 ]]; then
    echo "EXPIRING SOON (${#EXPIRING_SOON_CVES[@]}):"
    echo "-----------------------------------"
    for cve in "${EXPIRING_SOON_CVES[@]}"; do
        echo "  [WARNING] $cve"
    done
    echo ""
    if [[ $exit_code -eq 0 ]]; then
        exit_code=2
    fi
fi

if [[ ${#MISSING_DATE_CVES[@]} -gt 0 ]]; then
    echo "MISSING REVIEW DATE (${#MISSING_DATE_CVES[@]}):"
    echo "-----------------------------------"
    for cve in "${MISSING_DATE_CVES[@]}"; do
        echo "  [MISSING] $cve"
    done
    echo ""
    # Missing dates are treated as errors - require all CVEs to have dates
    exit_code=1
fi

if [[ $exit_code -eq 0 ]]; then
    echo "All CVE review dates are valid and not expired."
elif [[ $exit_code -eq 1 ]]; then
    echo "ACTION REQUIRED: Review and update expired CVEs or extend their dates."
elif [[ $exit_code -eq 2 ]]; then
    echo "WARNING: Some CVEs are expiring soon. Plan to review them."
fi

exit $exit_code
