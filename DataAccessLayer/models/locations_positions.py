from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from DataAccessLayer.models import Base

from sqlalchemy import func

class LocationsPositions(Base):
    __tablename__ = 'locations_positions'
    
    location_id = Column(Integer, ForeignKey('locations.id'), primary_key=True, nullable=False)
    position_id = Column(Integer, ForeignKey('positions.id'), primary_key=True, nullable=False)
    max_openings = Column(Integer, nullable=True)
    filled_openings = Column(Integer, nullable=True)
