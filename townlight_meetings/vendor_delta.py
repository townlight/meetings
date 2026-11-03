"""Compatibility exports for TownlightCore vendor delta request planning."""

from __future__ import annotations

from townlight_core.connectors import (
    DELTA_QUERY_PARAMS,
    VendorDeltaRequestPlan,
    plan_vendor_delta_request,
)

__all__ = [
    "DELTA_QUERY_PARAMS",
    "VendorDeltaRequestPlan",
    "plan_vendor_delta_request",
]
