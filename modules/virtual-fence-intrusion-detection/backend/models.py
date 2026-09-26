from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base
from geoalchemy2 import Geometry

Base = declarative_base()

class Geofence(Base):
    """
    The active, approved geofence definition.
    The edge worker uses this table to perform spatial intersection checks.
    """
    __tablename__ = 'geofences'

    zone_id = Column(String, primary_key=True)
    camera_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # 'warning' or 'critical'
    schedule = Column(String, nullable=False)  # 'always', 'night-only'
    
    # PostGIS geometry for the boundary. For pixel-space, a simple Polygon.
    polygon = Column(Geometry(geometry_type='POLYGON', srid=4326), nullable=False)
    
    version = Column(Integer, default=1)
    last_updated_by = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GeofenceProposal(Base):
    """
    Tracks proposed changes to geofences to enforce the 2-Person Authorization rule.
    """
    __tablename__ = 'geofence_proposals'

    proposal_id = Column(String, primary_key=True)
    zone_id = Column(String, nullable=True) # Null if creating a brand new zone
    camera_id = Column(String, nullable=False)
    
    proposed_name = Column(String, nullable=False)
    proposed_severity = Column(String, nullable=False)
    proposed_schedule = Column(String, nullable=False)
    proposed_polygon = Column(Geometry(geometry_type='POLYGON', srid=4326), nullable=False)
    
    status = Column(String, default='pending') # 'pending', 'approved', 'rejected', 'expired'
    
    proposed_by = Column(String, nullable=False)
    proposed_at = Column(DateTime, default=datetime.utcnow)
    
    decided_by = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_reason = Column(Text, nullable=True)
    
    # Default expiry is 30 minutes from proposal creation
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=30))
