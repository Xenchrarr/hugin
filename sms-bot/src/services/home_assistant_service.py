from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from src.api.core import HuginCoreClient

logger = logging.getLogger(__name__)

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))


def trigger_automation(entity_id: str, *, variables: Optional[Dict[str, Any]] = None) -> Any:
    logger.info("Triggering automation: %s", entity_id)
    return _core.trigger_automation(entity_id, variables=variables)
