from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector


from DataAccessLayer.models import Base

from sqlalchemy import func

class Positions(Base):
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, nullable=True)
    name = Column(String(225), nullable=True)
    description = Column(String(225), nullable=True)
    key_responsibilities = Column(ARRAY(Text), nullable=True)
    qualifications = Column(ARRAY(Text), nullable=True)
    benefits = Column(ARRAY(Text), nullable=True)
    salary_range = Column(String(225), nullable=True)
    salary_currency = Column(String(225), nullable=True)
    salary_period = Column(String(225), nullable=True)
    job_type = Column(String(225), nullable=True)
    location_type = Column(String(225), nullable=True)
    date_created = Column(DateTime, nullable=True, default=func.current_timestamp())
    date_updated = Column(DateTime, nullable=True, default=func.current_timestamp())
    is_active = Column(Boolean, nullable=True)
    position_embedding = Column(Vector(1536))
    working_hours = Column(String(225), nullable=True)

    locations = relationship("Locations", secondary='locations_positions', back_populates="positions")

