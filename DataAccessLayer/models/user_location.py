from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class UserLocation(Base):
    __tablename__ = 'user_location'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True, nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'), primary_key=True, nullable=False)

