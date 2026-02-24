"""Fichero D11s thermal label printer - BLE interface."""

from fichero.printer import (
    PrinterClient,
    PrinterError,
    PrinterNotFound,
    PrinterNotReady,
    PrinterStatus,
    PrinterTimeout,
    connect,
)

__all__ = [
    "PrinterClient",
    "PrinterError",
    "PrinterNotFound",
    "PrinterNotReady",
    "PrinterStatus",
    "PrinterTimeout",
    "connect",
]
