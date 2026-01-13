#!/usr/bin/env bash
#
# Generate Self-Signed TLS Certificates for Local Development
#
# This script generates self-signed TLS certificates for local development and
# LAN deployments. The certificates include proper Subject Alternative Names (SANs)
# for localhost, local IPs, and custom hostnames.
#
# Usage:
#   ./scripts/generate-certs.sh                    # Generate with defaults
#   ./scripts/generate-certs.sh --help             # Show help
#   ./scripts/generate-certs.sh --hostname myhost  # Custom hostname
#   ./scripts/generate-certs.sh --san 192.168.1.100 --san server.local
#
# Output:
#   certs/cert.pem  - TLS certificate
#   certs/key.pem   - Private key (600 permissions)
#
# Security Note:
#   Self-signed certificates are suitable for local development and internal LAN use.
#   For internet-facing deployments, use certificates from a trusted CA (Let's Encrypt).
#

set -euo pipefail

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default configuration
DEFAULT_OUTPUT_DIR="${PROJECT_ROOT}/certs"
DEFAULT_CERT_NAME="cert.pem"
DEFAULT_KEY_NAME="key.pem"
DEFAULT_HOSTNAME="localhost"
DEFAULT_VALIDITY_DAYS=365
DEFAULT_ORGANIZATION="Home Security Intelligence"
DEFAULT_KEY_SIZE=2048

# Parse arguments
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
CERT_NAME="$DEFAULT_CERT_NAME"
KEY_NAME="$DEFAULT_KEY_NAME"
HOSTNAME="$DEFAULT_HOSTNAME"
VALIDITY_DAYS="$DEFAULT_VALIDITY_DAYS"
ORGANIZATION="$DEFAULT_ORGANIZATION"
KEY_SIZE="$DEFAULT_KEY_SIZE"
FORCE=false
QUIET=false
SHOW_HELP=false
USE_PYTHON=false
SAN_HOSTS=()

print_help() {
    cat << 'EOF'
Generate Self-Signed TLS Certificates for Local Development

USAGE:
    ./scripts/generate-certs.sh [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -o, --output-dir DIR    Output directory (default: certs/)
    -n, --hostname NAME     Primary hostname/CN (default: localhost)
    -s, --san HOST          Add Subject Alternative Name (can be repeated)
    -d, --days DAYS         Validity period in days (default: 365)
    --org NAME              Organization name (default: Home Security Intelligence)
    --cert-name NAME        Certificate filename (default: cert.pem)
    --key-name NAME         Private key filename (default: key.pem)
    --key-size BITS         RSA key size (default: 2048)
    -f, --force             Overwrite existing certificates without prompting
    -q, --quiet             Suppress informational output
    --use-python            Use Python script instead of OpenSSL

EXAMPLES:
    # Development (localhost only)
    ./scripts/generate-certs.sh

    # LAN deployment with specific IP
    ./scripts/generate-certs.sh --hostname security.home --san 192.168.1.100

    # Multiple SANs
    ./scripts/generate-certs.sh --san 192.168.1.100 --san 192.168.1.101 --san lb.local

    # Custom output location
    ./scripts/generate-certs.sh --output-dir /etc/ssl/hsi --days 730

ENVIRONMENT VARIABLES:
    TLS_CERT_PATH    Override default certificate output path
    TLS_KEY_PATH     Override default private key output path

OUTPUT:
    After generation, enable HTTPS by adding to your .env file:

        TLS_MODE=provided
        TLS_CERT_PATH=certs/cert.pem
        TLS_KEY_PATH=certs/key.pem

    Or start uvicorn directly with SSL:

        uvicorn backend.main:app --ssl-certfile=certs/cert.pem --ssl-keyfile=certs/key.pem

SECURITY NOTES:
    - Self-signed certificates trigger browser warnings (expected for development)
    - Private keys are created with 600 permissions (owner read/write only)
    - For production internet-facing deployments, use Let's Encrypt or a trusted CA
    - Certificate files are excluded from git via .gitignore

SEE ALSO:
    scripts/generate_certs.py    Python alternative with additional options
    docs/admin-guide/security.md TLS configuration documentation
EOF
}

error() {
    echo -e "${RED}Error: $1${NC}" >&2
}

warn() {
    if [[ "$QUIET" != "true" ]]; then
        echo -e "${YELLOW}Warning: $1${NC}"
    fi
}

info() {
    if [[ "$QUIET" != "true" ]]; then
        echo -e "${CYAN}$1${NC}"
    fi
}

success() {
    if [[ "$QUIET" != "true" ]]; then
        echo -e "${GREEN}$1${NC}"
    fi
}

# Check for required tools
check_openssl() {
    if ! command -v openssl &> /dev/null; then
        error "OpenSSL is required but not found. Please install OpenSSL."
        error "  macOS:  brew install openssl"
        error "  Ubuntu: sudo apt-get install openssl"
        error "  Fedora: sudo dnf install openssl"
        exit 1
    fi
}

# Get local IP addresses for SANs
get_local_ips() {
    local ips=()

    # Always include localhost addresses
    ips+=("127.0.0.1")
    ips+=("::1")

    # Try to get primary IP from hostname
    local hostname_ip
    hostname_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
    if [[ -n "$hostname_ip" && "$hostname_ip" != "127.0.0.1" ]]; then
        ips+=("$hostname_ip")
    fi

    # macOS fallback
    if [[ -z "$hostname_ip" ]]; then
        hostname_ip=$(ipconfig getifaddr en0 2>/dev/null || true)
        if [[ -n "$hostname_ip" && "$hostname_ip" != "127.0.0.1" ]]; then
            ips+=("$hostname_ip")
        fi
    fi

    printf '%s\n' "${ips[@]}" | sort -u
}

# Build OpenSSL SAN extension configuration
build_san_extension() {
    local san_entries=()
    local index=1

    # Add DNS entries
    san_entries+=("DNS.$index = $HOSTNAME")
    ((index++))

    if [[ "$HOSTNAME" != "localhost" ]]; then
        san_entries+=("DNS.$index = localhost")
        ((index++))
    fi

    # Add custom SAN hosts (DNS or IP)
    for san in "${SAN_HOSTS[@]}"; do
        # Check if it's an IP address
        if [[ "$san" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [[ "$san" =~ ^[0-9a-fA-F:]+$ ]]; then
            san_entries+=("IP.$index = $san")
        else
            san_entries+=("DNS.$index = $san")
        fi
        ((index++))
    done

    # Add local IPs
    local ip_index=1
    while IFS= read -r ip; do
        # Skip if already in SAN_HOSTS
        local skip=false
        for existing in "${SAN_HOSTS[@]}"; do
            if [[ "$existing" == "$ip" ]]; then
                skip=true
                break
            fi
        done

        if [[ "$skip" != "true" ]]; then
            san_entries+=("IP.$ip_index = $ip")
            ((ip_index++))
        fi
    done < <(get_local_ips)

    printf '%s\n' "${san_entries[@]}"
}

# Generate certificates using OpenSSL
generate_with_openssl() {
    local cert_path="$OUTPUT_DIR/$CERT_NAME"
    local key_path="$OUTPUT_DIR/$KEY_NAME"

    # Check for existing certificates
    if [[ -f "$cert_path" || -f "$key_path" ]]; then
        if [[ "$FORCE" != "true" ]]; then
            warn "Certificate files already exist in $OUTPUT_DIR"
            read -p "Overwrite? [y/N]: " -r response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                info "Aborted."
                exit 1
            fi
        fi
    fi

    # Create output directory
    mkdir -p "$OUTPUT_DIR"

    # Create temporary OpenSSL config with SANs
    local config_file
    config_file=$(mktemp)
    # Clean up temp file on exit (use explicit path to avoid variable scoping issues)
    local cleanup_file="$config_file"
    trap "rm -f '$cleanup_file'" EXIT

    cat > "$config_file" << EOF
[req]
default_bits = $KEY_SIZE
prompt = no
default_md = sha256
x509_extensions = v3_req
distinguished_name = dn

[dn]
C = US
ST = Local
L = LAN
O = $ORGANIZATION
CN = $HOSTNAME

[v3_req]
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
$(build_san_extension)
EOF

    info "Generating TLS certificate..."
    info "  Hostname (CN): $HOSTNAME"
    info "  Organization: $ORGANIZATION"
    info "  Validity: $VALIDITY_DAYS days"
    info "  Key size: $KEY_SIZE bits"
    if [[ ${#SAN_HOSTS[@]} -gt 0 ]]; then
        info "  Custom SANs: ${SAN_HOSTS[*]}"
    fi
    info "  Certificate: $cert_path"
    info "  Private Key: $key_path"
    echo

    # Generate private key and certificate
    openssl req -x509 -nodes -newkey rsa:"$KEY_SIZE" \
        -keyout "$key_path" \
        -out "$cert_path" \
        -days "$VALIDITY_DAYS" \
        -config "$config_file" \
        2>/dev/null

    # Set secure permissions on private key
    chmod 600 "$key_path"
    chmod 644 "$cert_path"

    success "Certificate generated successfully!"
    echo
    info "To enable HTTPS, add to your .env file:"
    echo
    echo "  TLS_MODE=provided"
    echo "  TLS_CERT_PATH=$cert_path"
    echo "  TLS_KEY_PATH=$key_path"
    echo
    info "Or start the server with:"
    echo
    echo "  uvicorn backend.main:app --ssl-certfile=$cert_path --ssl-keyfile=$key_path"
    echo

    # Verify certificate
    if [[ "$QUIET" != "true" ]]; then
        info "Certificate details:"
        openssl x509 -in "$cert_path" -noout -subject -dates -ext subjectAltName 2>/dev/null || true
    fi
}

# Generate certificates using Python script
generate_with_python() {
    local args=()

    args+=("--hostname" "$HOSTNAME")
    args+=("--output-dir" "$OUTPUT_DIR")
    args+=("--cert-name" "$CERT_NAME")
    args+=("--key-name" "$KEY_NAME")
    args+=("--validity-days" "$VALIDITY_DAYS")
    args+=("--organization" "$ORGANIZATION")

    for san in "${SAN_HOSTS[@]}"; do
        args+=("--san" "$san")
    done

    if [[ "$FORCE" == "true" ]]; then
        args+=("--force")
    fi

    if [[ "$QUIET" == "true" ]]; then
        args+=("--quiet")
    fi

    cd "$PROJECT_ROOT"

    # Try using uv first, fall back to direct Python
    if command -v uv &> /dev/null; then
        uv run python scripts/generate_certs.py "${args[@]}"
    elif [[ -f "$PROJECT_ROOT/.venv/bin/python" ]]; then
        "$PROJECT_ROOT/.venv/bin/python" scripts/generate_certs.py "${args[@]}"
    else
        python3 scripts/generate_certs.py "${args[@]}"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            SHOW_HELP=true
            shift
            ;;
        -o|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -n|--hostname)
            HOSTNAME="$2"
            shift 2
            ;;
        -s|--san)
            SAN_HOSTS+=("$2")
            shift 2
            ;;
        -d|--days)
            VALIDITY_DAYS="$2"
            shift 2
            ;;
        --org)
            ORGANIZATION="$2"
            shift 2
            ;;
        --cert-name)
            CERT_NAME="$2"
            shift 2
            ;;
        --key-name)
            KEY_NAME="$2"
            shift 2
            ;;
        --key-size)
            KEY_SIZE="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        --use-python)
            USE_PYTHON=true
            shift
            ;;
        *)
            error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Show help if requested
if [[ "$SHOW_HELP" == "true" ]]; then
    print_help
    exit 0
fi

# Honor environment variables for paths
if [[ -n "${TLS_CERT_PATH:-}" ]]; then
    OUTPUT_DIR="$(dirname "$TLS_CERT_PATH")"
    CERT_NAME="$(basename "$TLS_CERT_PATH")"
fi

if [[ -n "${TLS_KEY_PATH:-}" ]]; then
    KEY_NAME="$(basename "$TLS_KEY_PATH")"
fi

# Generate certificates
if [[ "$USE_PYTHON" == "true" ]]; then
    generate_with_python
else
    check_openssl
    generate_with_openssl
fi
