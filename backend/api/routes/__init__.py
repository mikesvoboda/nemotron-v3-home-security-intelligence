"""API route handlers."""

from .alertmanager import router as alertmanager_router
from .alerts import alerts_instance_router
from .alerts import router as alerts_router
from .analytics_zones import router as analytics_zones_router
from .audit import router as audit_router
from .backup import router as backup_router
from .calibration import router as calibration_router
from .entities import router as entities_router
from .exports import router as exports_router
from .feedback import router as feedback_router
from .gpu_config import router as gpu_config_router
from .heatmaps import router as heatmaps_router
from .hierarchy import area_router as area_router
from .hierarchy import property_router as property_router
from .hierarchy import router as hierarchy_router
from .household import router as household_router
from .jobs import router as jobs_router
from .logs import router as logs_router
from .notification_preferences import router as notification_preferences_router
from .outbound_webhooks import router as outbound_webhooks_router
from .rum import router as rum_router
from .scheduled_reports import router as scheduled_reports_router
from .services import router as services_router
from .settings_api import router as settings_api_router
from .summaries import router as summaries_router
from .system_settings import router as system_settings_router
from .tracks import router as tracks_router
from .zone_anomalies import router as zone_anomalies_router
from .zone_household import router as zone_household_router
from .zones import router as zones_router

__all__ = [
    "alertmanager_router",
    "alerts_instance_router",
    "alerts_router",
    "analytics_zones_router",
    "area_router",
    "audit_router",
    "backup_router",
    "calibration_router",
    "entities_router",
    "exports_router",
    "feedback_router",
    "gpu_config_router",
    "heatmaps_router",
    "hierarchy_router",
    "household_router",
    "jobs_router",
    "logs_router",
    "notification_preferences_router",
    "outbound_webhooks_router",
    "property_router",
    "rum_router",
    "scheduled_reports_router",
    "services_router",
    "settings_api_router",
    "summaries_router",
    "system_settings_router",
    "tracks_router",
    "zone_anomalies_router",
    "zone_household_router",
    "zones_router",
]
