"""TensorRT engine building for YOLO26."""

import time

from scripts.redeploy.core import output
from scripts.redeploy.core.runtime import ContainerRuntime
from scripts.redeploy.models import DeployConfig


class TensorRTBuilder:
    """Build TensorRT engines for optimized inference."""

    def __init__(self, runtime: ContainerRuntime, config: DeployConfig):
        """Initialize TensorRT builder.

        Args:
            runtime: Container runtime instance
            config: Deployment configuration
        """
        self.runtime = runtime
        self.config = config

    async def rebuild_yolo26_engine(self, force: bool = False) -> bool:
        """Rebuild YOLO26 TensorRT engine.

        This runs the export inside the ai-yolo26 container to ensure
        the engine is compatible with the container's TensorRT version.

        Args:
            force: If True, rebuild even if valid engine exists

        Returns:
            True if engine built successfully or already valid
        """
        output.header("Checking YOLO26 TensorRT Engine")

        model_path = self.config.ai_models_path / "model-zoo/yolo26/yolo26m.pt"
        engine_path = self.config.ai_models_path / "model-zoo/yolo26/exports/yolo26m_fp16.engine"

        if self.config.dry_run:
            output.dry_run("Would check/rebuild TensorRT engine")
            return True

        # Check if model exists
        if not model_path.exists():
            output.fail(f"Model not found: {model_path}")
            return False

        # OPTIMIZATION: Check if engine already exists and is valid
        if not force and self.verify_engine():
            # Additional check: ensure engine is newer than model
            if engine_path.stat().st_mtime >= model_path.stat().st_mtime:
                output.success("TensorRT engine is valid and up-to-date, skipping rebuild")
                return True
            else:
                output.info("TensorRT engine is older than model, rebuilding...")

        output.step(f"Building TensorRT engine from {model_path}...")
        output.info("This may take 2-5 minutes...")

        # Ensure exports directory exists
        exports_dir = engine_path.parent
        exports_dir.mkdir(parents=True, exist_ok=True)

        start = time.monotonic()

        # Run export inside the yolo26 container
        # We use a temporary container with the same image
        container_name = "tensorrt-builder-temp"

        # Remove any existing temp container
        self.runtime.rm(container_name, force=True)

        # Start container with model mounted
        container_id = self.runtime.run(
            image="ai-yolo26",
            name=container_name,
            detach=True,
            volumes=[
                f"{self.config.ai_models_path}/model-zoo/yolo26:/models/yolo26:z",
            ],
            devices=[f"nvidia.com/gpu={self.config.gpu_ai_services}"],
            extra_args=[
                "--security-opt=label=disable",
                "-e",
                "CUDA_VISIBLE_DEVICES=0",
            ],
        )

        if not container_id:
            output.fail("Failed to start TensorRT builder container")
            return False

        try:
            # Wait for container to be ready
            import asyncio

            await asyncio.sleep(5)

            # Run the export command
            export_cmd = [
                "python",
                "-c",
                """
import torch
from ultralytics import YOLO

print("Loading PyTorch model from /models/yolo26/yolo26m.pt...")
model = YOLO("/models/yolo26/yolo26m.pt")

print("Exporting to TensorRT FP16 engine...")
model.export(
    format="engine",
    device=0,
    half=True,
    simplify=True,
    workspace=4,
)

print("TensorRT engine exported to: /models/yolo26/yolo26m.engine")

# Move to exports directory
import shutil
import os
src = "/models/yolo26/yolo26m.engine"
dst = "/models/yolo26/exports/yolo26m_fp16.engine"
os.makedirs(os.path.dirname(dst), exist_ok=True)
if os.path.exists(src):
    shutil.move(src, dst)
    print(f"Engine file size: {os.path.getsize(dst) / 1024 / 1024:.1f} MB")
    print("TensorRT engine rebuild successful!")
else:
    print("ERROR: Engine file not created")
    exit(1)
""",
            ]

            result = self.runtime.exec(
                container_name,
                export_cmd,
            )

            duration = time.monotonic() - start

            # Stream the output
            if result.stdout:
                for line in result.stdout.split("\n"):
                    if line.strip():
                        output.info(line)

            if result.returncode == 0:
                output.success(f"TensorRT engine rebuilt ({duration:.1f}s)")

                # Verify engine exists
                if engine_path.exists():
                    size_mb = engine_path.stat().st_size / 1024 / 1024
                    output.info(f"Engine file: {engine_path} ({size_mb:.0f}M)")
                    return True
                else:
                    output.fail("Engine file not found after build")
                    return False
            else:
                output.fail("TensorRT engine build failed")
                if result.stderr:
                    output.error(result.stderr[:500])
                return False

        finally:
            # Clean up temp container
            self.runtime.stop(container_name, timeout=5)
            self.runtime.rm(container_name, force=True)

    def verify_engine(self) -> bool:
        """Verify TensorRT engine exists and is valid.

        Returns:
            True if engine is valid
        """
        engine_path = self.config.ai_models_path / "model-zoo/yolo26/exports/yolo26m_fp16.engine"

        if not engine_path.exists():
            output.warn(f"TensorRT engine not found: {engine_path}")
            return False

        # Check file size (should be > 30MB for yolo26m)
        size_mb = engine_path.stat().st_size / 1024 / 1024
        if size_mb < 30:
            output.warn(f"TensorRT engine seems too small: {size_mb:.1f}MB")
            return False

        output.success(f"TensorRT engine valid: {engine_path} ({size_mb:.0f}MB)")
        return True
