from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class Companies(Base):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, nullable=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    contact_person = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    zip = Column(String(20), nullable=True)
    created_date = Column(DateTime, nullable=True, default=func.current_timestamp())
    updated_date = Column(DateTime, nullable=True, default=func.current_timestamp())

