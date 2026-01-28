#!/bin/bash
set -e

MODELS_DIR="${MODELS_DIR:-./models}"
mkdir -p "$MODELS_DIR"

echo "============================================"
echo "Downloading AI models from HuggingFace..."
echo "Models directory: $MODELS_DIR"
echo "============================================"

# Check for huggingface-cli
if ! command -v huggingface-cli &> /dev/null; then
    echo "Installing huggingface_hub..."
    pip install huggingface_hub
fi

# FashionCLIP
echo ""
echo "[1/9] Downloading FashionCLIP..."
huggingface-cli download patrickjohncyh/fashion-clip --local-dir "$MODELS_DIR/fashion-clip" --local-dir-use-symlinks False

# Depth Anything v2
echo ""
echo "[2/9] Downloading Depth Anything v2 Small..."
huggingface-cli download depth-anything/Depth-Anything-V2-Small --local-dir "$MODELS_DIR/depth-anything-v2-small" --local-dir-use-symlinks False

# YOLOv8n-pose (from Ultralytics)
echo ""
echo "[3/9] Downloading YOLOv8n-pose..."
mkdir -p "$MODELS_DIR/yolov8n-pose"
python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')" && mv yolov8n-pose.pt "$MODELS_DIR/yolov8n-pose/"

# X-CLIP 16-frame patch16 model (NEM-3908: upgraded for +4% accuracy)
echo ""
echo "[4/9] Downloading X-CLIP base-patch16-16-frames..."
huggingface-cli download microsoft/xclip-base-patch16-16-frames --local-dir "$MODELS_DIR/xclip-base-patch16-16-frames" --local-dir-use-symlinks False

# Age Classifier
echo ""
echo "[5/9] Downloading Age Classifier..."
huggingface-cli download nateraw/vit-age-classifier --local-dir "$MODELS_DIR/vit-age-classifier" --local-dir-use-symlinks False

# OSNet Re-ID
echo ""
echo "[6/9] Downloading OSNet x0.25 Re-ID..."
python -c "
import torchreid
import os
model = torchreid.models.build_model(name='osnet_x0_25', num_classes=1, pretrained=True)
os.makedirs('$MODELS_DIR/osnet-x0-25', exist_ok=True)
import torch
torch.save(model.state_dict(), '$MODELS_DIR/osnet-x0-25/osnet_x0_25.pth')
print('OSNet saved successfully')
"

# Vehicle Classifier (if exists on HF, otherwise note manual download)
echo ""
echo "[7/9] Vehicle Classifier..."
echo "Note: Vehicle classifier may require manual download or training"
mkdir -p "$MODELS_DIR/vehicle-segment-classification"

# Pet Classifier
echo ""
echo "[8/9] Pet Classifier..."
echo "Note: Pet classifier may require manual download or training"
mkdir -p "$MODELS_DIR/pet-classifier"

# Threat Detection (placeholder - need to find suitable model)
echo ""
echo "[9/9] Threat Detection..."
echo "Note: Threat detection model requires selection from available options"
echo "Suggested: Search HuggingFace for 'weapon detection yolov8'"
mkdir -p "$MODELS_DIR/threat-detection-yolov8n"

echo ""
echo "============================================"
echo "Download complete!"
echo "Total size: $(du -sh $MODELS_DIR | cut -f1)"
echo "============================================"
echo ""
echo "Models downloaded:"
ls -la "$MODELS_DIR"
