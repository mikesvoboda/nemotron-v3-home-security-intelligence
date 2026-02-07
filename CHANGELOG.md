# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- YOLO26 object detection migration replacing YOLOv8, with TensorRT acceleration
- Model zoo with on-demand VRAM management and LRU eviction (Florence-2, CLIP, enrichment models)
- Zone configuration system with detection zones, dwell time tracking, and line crossing
- Face recognition pipeline with person re-identification and demographics
- Household management for linking recognized individuals to residents
- ONVIF camera discovery via WS-Discovery and onvif-zeep
- MQTT integration for camera event ingestion
- WebSocket real-time event system for live dashboard updates
- GPU optimization pipeline with batch processing and multi-model orchestration
- Comprehensive TDD infrastructure with 11,000+ tests across backend and frontend
- Full documentation restructure with user, operator, developer, and architecture guides
- Mermaid diagrams for system visualization
- SetupGuardMiddleware for first-time admin registration flow

### Changed

- README.md streamlined to focus on quick start
- Documentation reorganized into logical sections
- Auth model updated: single-user local deployment with SetupGuardMiddleware guard
- Batch processing tuned to 90-second windows with 30-second idle timeout

## [0.1.0] - 2024-12-21

### Added

- Initial MVP release
- YOLO26v2 object detection integration
- Nemotron LLM risk analysis
- React dashboard with real-time updates
- PostgreSQL + Redis backend
- WebSocket event streaming
