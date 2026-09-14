"""GPU integration tests package.

Tests in this package are marked with @pytest.mark.gpu and run on the
self-hosted GPU runner with NVIDIA RTX A5500.

These tests are designed to run WITHOUT database dependencies since
the GPU runner may not have PostgreSQL available.
"""
