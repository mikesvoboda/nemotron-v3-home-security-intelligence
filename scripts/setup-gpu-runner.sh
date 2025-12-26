#!/bin/bash
# GPU Runner Setup Script for GitHub Actions
# Run with: sudo ./scripts/setup-gpu-runner.sh

set -e

# Configuration
RUNNER_VERSION="2.321.0"
RUNNER_USER="github-runner"
RUNNER_DIR="/opt/actions-runner"
REPO_URL="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== GitHub Actions GPU Runner Setup ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (sudo)${NC}"
    exit 1
fi

# Step 1: Verify GPU
echo -e "${YELLOW}Step 1: Verifying GPU...${NC}"
if nvidia-smi > /dev/null 2>&1; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader)
    echo -e "${GREEN}✓ GPU detected: $GPU_NAME${NC}"
else
    echo -e "${RED}Error: nvidia-smi failed. Is the NVIDIA driver installed?${NC}"
    exit 1
fi

# Step 2: Check NVIDIA Container Toolkit
echo -e "${YELLOW}Step 2: Checking NVIDIA Container Toolkit...${NC}"
if command -v nvidia-ctk > /dev/null 2>&1; then
    echo -e "${GREEN}✓ NVIDIA Container Toolkit installed${NC}"
else
    echo -e "${YELLOW}Installing NVIDIA Container Toolkit...${NC}"
    if [ -f /etc/fedora-release ]; then
        dnf install -y nvidia-container-toolkit
    elif [ -f /etc/debian_version ]; then
        # Add NVIDIA repo for Debian/Ubuntu
        distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
            gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
        curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
        apt-get update
        apt-get install -y nvidia-container-toolkit
    fi
    echo -e "${GREEN}✓ NVIDIA Container Toolkit installed${NC}"
fi

# Step 3: Configure Docker for GPU
echo -e "${YELLOW}Step 3: Configuring Docker for GPU...${NC}"
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
echo -e "${GREEN}✓ Docker configured for GPU${NC}"

# Step 4: Test Docker GPU access
echo -e "${YELLOW}Step 4: Testing Docker GPU access...${NC}"
# Try multiple CUDA image tags (NVIDIA changed their tagging scheme)
CUDA_IMAGES=(
    "nvidia/cuda:12.0.0-base-ubuntu22.04"
    "nvidia/cuda:12.2.0-base-ubuntu22.04"
    "nvidia/cuda:11.8.0-base-ubuntu22.04"
)

GPU_TEST_PASSED=false
for IMAGE in "${CUDA_IMAGES[@]}"; do
    echo "  Testing with $IMAGE..."
    if docker run --rm --gpus all "$IMAGE" nvidia-smi > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Docker GPU access working with $IMAGE${NC}"
        GPU_TEST_PASSED=true
        break
    fi
done

if [ "$GPU_TEST_PASSED" = false ]; then
    echo -e "${YELLOW}Warning: Docker GPU test failed with pre-built images.${NC}"
    echo -e "${YELLOW}This may be due to image availability. Continuing anyway...${NC}"
    echo -e "${YELLOW}You can manually test later with: docker run --rm --gpus all ubuntu nvidia-smi${NC}"
fi

# Step 5: Create runner user
echo -e "${YELLOW}Step 5: Creating runner user...${NC}"
if id "$RUNNER_USER" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ User $RUNNER_USER already exists${NC}"
else
    useradd -m -s /bin/bash "$RUNNER_USER"
    echo -e "${GREEN}✓ Created user $RUNNER_USER${NC}"
fi

# Add to required groups
usermod -aG docker "$RUNNER_USER"
usermod -aG video "$RUNNER_USER"
echo -e "${GREEN}✓ Added to docker and video groups${NC}"

# Step 6: Create runner directory
echo -e "${YELLOW}Step 6: Setting up runner directory...${NC}"
mkdir -p "$RUNNER_DIR"
chown "$RUNNER_USER:$RUNNER_USER" "$RUNNER_DIR"
echo -e "${GREEN}✓ Created $RUNNER_DIR${NC}"

# Step 7: Download runner
echo -e "${YELLOW}Step 7: Downloading GitHub Actions Runner v${RUNNER_VERSION}...${NC}"
cd "$RUNNER_DIR"

if [ -f "config.sh" ]; then
    echo -e "${GREEN}✓ Runner already downloaded${NC}"
else
    RUNNER_ARCHIVE="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
    curl -sL -o "$RUNNER_ARCHIVE" \
        "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_ARCHIVE}"

    tar xzf "$RUNNER_ARCHIVE"
    rm "$RUNNER_ARCHIVE"
    chown -R "$RUNNER_USER:$RUNNER_USER" "$RUNNER_DIR"
    echo -e "${GREEN}✓ Runner downloaded and extracted${NC}"
fi

# Step 8: Get registration token
echo -e "${YELLOW}Step 8: Getting registration token...${NC}"
echo ""
echo -e "${YELLOW}Please run the following command to get a fresh token:${NC}"
echo ""
echo "  gh api repos/mikesvoboda/nemotron-v3-home-security-intelligence/actions/runners/registration-token -X POST --jq '.token'"
echo ""
read -p "Enter the registration token: " RUNNER_TOKEN

if [ -z "$RUNNER_TOKEN" ]; then
    echo -e "${RED}Error: No token provided${NC}"
    exit 1
fi

# Step 9: Configure runner
echo -e "${YELLOW}Step 9: Configuring runner...${NC}"
sudo -u "$RUNNER_USER" ./config.sh \
    --url "$REPO_URL" \
    --token "$RUNNER_TOKEN" \
    --name "rtx-a5500-runner" \
    --labels "self-hosted,linux,gpu,rtx-a5500" \
    --work "_work" \
    --unattended \
    --replace

echo -e "${GREEN}✓ Runner configured${NC}"

# Step 10: Install as service
echo -e "${YELLOW}Step 10: Installing as systemd service...${NC}"
./svc.sh install "$RUNNER_USER"
./svc.sh start
echo -e "${GREEN}✓ Service installed and started${NC}"

# Verify
echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
./svc.sh status
echo ""
echo -e "${GREEN}Runner is now registered and running!${NC}"
echo ""
echo "Verify at: https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/settings/actions/runners"
echo ""
echo "To manually control the service:"
echo "  sudo /opt/actions-runner/svc.sh status"
echo "  sudo /opt/actions-runner/svc.sh start"
echo "  sudo /opt/actions-runner/svc.sh stop"
echo ""
