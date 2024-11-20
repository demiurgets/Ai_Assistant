from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class Interviews(Base):
    __tablename__ = 'interviews'

    id = Column(Integer, primary_key=True, nullable=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id'), nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    date = Column(Date, nullable=True)
    date_created = Column(DateTime, nullable=True, default=func.current_timestamp())
    date_updated = Column(DateTime, nullable=True, default=func.current_timestamp())

