# app/services/health_service.py

import psutil
import torch
from datetime import datetime
import logging

from app.db.base import prisma

logger = logging.getLogger(__name__)

class HealthService:
    def __init__(self):
        self.metricx_service_instance = None
        self.multi_engine_service_instance = None
        logger.info("HealthService initialized (services not yet set)")

    def set_services(self, metricx_service, multi_engine_service):
        self.metricx_service_instance = metricx_service
        self.multi_engine_service_instance = multi_engine_service
        logger.info("HealthService received MetricX and MultiEngine services")

    async def get_detailed_status(self):
        """Gathers detailed health status of the system and services."""
        db_status = "connected"
        try:
            if not prisma.is_connected():
                await prisma.connect()
            await prisma.translationrequest.count() # Test DB connection
        except Exception as e:
            db_status = f"error: {str(e)}"
            logger.error(f"Database health check failed: {e}")

        # System info
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        cuda_available = torch.cuda.is_available()
        cuda_devices = torch.cuda.device_count() if cuda_available else 0

        metricx_ready = False
        if self.metricx_service_instance:
            try:                
                metricx_ready = self.metricx_service_instance is not None
            except Exception as e:
                logger.warning(f"MetricX service check failed: {e}")
                metricx_ready = False

        multi_engine_ready = False
        available_engines_list = []
        if self.multi_engine_service_instance:
            try:
                multi_engine_ready = self.multi_engine_service_instance.is_initialized() # Assuming this method exists
                available_engines_list = list(self.multi_engine_service_instance.engine_configs.keys()) # Assuming this attribute exists
            except Exception as e:
                logger.warning(f"Multi-engine service check failed: {e}")
                multi_engine_ready = False

        status = "healthy"
        if db_status.startswith("error") or not metricx_ready or not multi_engine_ready:
            status = "unhealthy"

        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "database": db_status,
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "cuda_available": cuda_available,
                "cuda_devices": cuda_devices
            },
            "metricx_available": metricx_ready,
            "translation_service_available": True, 
            "local_engines_available": multi_engine_ready,
            "available_engines": available_engines_list
        }