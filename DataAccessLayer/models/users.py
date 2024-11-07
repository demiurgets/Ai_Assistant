from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, nullable=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True)
    user_type_id = Column(Integer, nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    zip = Column(String(20), nullable=True)
    status_id = Column(Integer, nullable=True)
    focus_percentage = Column(Float, nullable=True)
    created_date = Column(DateTime, nullable=True, default=func.current_timestamp())
    updated_date = Column(DateTime, nullable=True, default=func.current_timestamp())
    start_date = Column(Date, nullable=True)
    profile_img_url = Column(String(255), nullable=True)

