from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class Assistants(Base):
    __tablename__ = 'assistants'

    id = Column(Integer, primary_key=True, nullable=True)
    addresse_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    assistant_id = Column(String(225), nullable=True)
    name = Column(String(225), nullable=True)
    date_created = Column(DateTime, nullable=True, default=func.current_timestamp())
    date_updated = Column(DateTime, nullable=True, default=func.current_timestamp())

