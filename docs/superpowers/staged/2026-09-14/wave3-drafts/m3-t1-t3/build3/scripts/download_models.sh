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
echo "[2/9] Downloading Depth Anything v2 Tiny..."
huggingface-cli download depth-anything/Depth-Anything-V2-Tiny --local-dir "$MODELS_DIR/depth-anything-v2-tiny" --local-dir-use-symlinks False

# YOLOv8n-pose (from Ultralytics)
echo ""
echo "[3/9] Downloading YOLOv8n-pose..."
mkdir -p "$MODELS_DIR/yolov8n-pose"
python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')" && mv yolov8n-pose.pt "$MODELS_DIR/yolov8n-pose/"

# SigLIP 2 Base - replaces CLIP ViT-L for re-identification (NEM-5561)
echo ""
echo "[4/12] Downloading SigLIP 2 Base ONNX..."
huggingface-cli download onnx-community/siglip2-base-patch16-224-ONNX --local-dir "$MODELS_DIR/siglip2-base-patch16-224" --local-dir-use-symlinks False

# Age Classifier
echo ""
echo "[5/12] Downloading Age Classifier..."
huggingface-cli download nateraw/vit-age-classifier --local-dir "$MODELS_DIR/vit-age-classifier" --local-dir-use-symlinks False

# OSNet-AIN x1.0 Re-ID (NEM-5562: upgraded from x0.25 for 4x better accuracy)
echo ""
echo "[6/12] Downloading OSNet-AIN x1.0 Re-ID..."
python -c "
import torchreid
import os
model = torchreid.models.build_model(name='osnet_ain_x1_0', num_classes=1, pretrained=True)
os.makedirs('$MODELS_DIR/osnet-ain-x1-0', exist_ok=True)
import torch
torch.save(model.state_dict(), '$MODELS_DIR/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth')
print('OSNet-AIN x1.0 saved successfully')
"

# Vehicle Classifier
echo ""
echo "[7/12] Vehicle Classifier..."
echo "Note: Vehicle classifier may require manual download or training"
mkdir -p "$MODELS_DIR/vehicle-segment-classification"

# Pet Classifier
echo ""
echo "[8/12] Pet Classifier..."
echo "Note: Pet classifier may require manual download or training"
mkdir -p "$MODELS_DIR/pet-classifier"

# Threat Detection
echo ""
echo "[9/12] Downloading Threat Detection..."
huggingface-cli download Subh775/Threat-Detection-YOLOv8n --local-dir "$MODELS_DIR/threat-detection-yolov8n" --local-dir-use-symlinks False

# Smoke/fire detection - CRITICAL safety model (NEM-5566)
echo ""
echo "[10/12] Downloading Smoke/Fire Detection..."
huggingface-cli download luminous0219/fire-and-smoke-detection-yolov8 --local-dir "$MODELS_DIR/smoke-fire-yolov8n" --local-dir-use-symlinks False

# YOLO-World open-vocabulary detection (NEM-5566)
echo ""
echo "[11/12] Downloading YOLO-World..."
mkdir -p "$MODELS_DIR/yolo-world-s"
python -c "from ultralytics import YOLOWorld; YOLOWorld('yolov8s-worldv2.pt')" && mv yolov8s-worldv2.pt "$MODELS_DIR/yolo-world-s/" 2>/dev/null || echo "  Note: YOLO-World download via ultralytics"

# Gender Classifier (NEM-5566)
echo ""
echo "[12/12] Downloading Gender Classifier..."
huggingface-cli download rizvandwiki/gender-classification --local-dir "$MODELS_DIR/vit-gender-classifier" --local-dir-use-symlinks False

echo ""
echo "============================================"
echo "Download complete!"
echo "Total size: $(du -sh $MODELS_DIR | cut -f1)"
echo "============================================"
echo ""
echo "Models downloaded:"
ls -la "$MODELS_DIR"
