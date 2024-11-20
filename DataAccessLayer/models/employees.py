from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class Employees(Base):
    __tablename__ = 'employees'

    id = Column(Integer, primary_key=True, nullable=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)
    assistant_thread_id = Column(String(225), nullable=True)
    age = Column(Integer, nullable=True)
    address = Column(String(100), nullable=True)
    status = Column(String(50), nullable=True, default='hired')
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    hiring_date = Column(Date, nullable=True, default=func.current_date())
    created_at = Column(DateTime, nullable=True, default=func.current_timestamp())
    date_created = Column(DateTime, nullable=True, default=func.current_timestamp())
    date_updated = Column(DateTime, nullable=True, default=func.current_timestamp())

