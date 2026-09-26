"""
Pipeline package root.
"""
from .detector import BBox as DetectorBBox, PlateDetector
from .ocr import UNREADABLE, PlateOCR

__all__ = ["PlateDetector", "DetectorBBox", "PlateOCR", "UNREADABLE"]
