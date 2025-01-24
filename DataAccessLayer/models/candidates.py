from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class Candidates(Base):
    __tablename__ = 'candidates'

    id = Column(Integer, primary_key=True, nullable=True, autoincrement=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    thread_id = Column(String(255), nullable=False)
    age = Column(Integer, nullable=True)
    email = Column(String(255), nullable=True)
    experience = Column(String(255), nullable=False)
    lead_source = Column(String(255), nullable=False)
    availability = Column(String(255), nullable=False)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    zip = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    position_id = Column(Integer, ForeignKey('positions.id'), nullable=True)
    status_id = Column(Integer, nullable=True)
    interview_date = Column(Date, nullable=True)
    enrollment_start = Column(Date, nullable=True)
    enrollment_end = Column(Date, nullable=True)
    created_date = Column(DateTime, nullable=True, default=func.current_timestamp())
    updated_date = Column(DateTime, nullable=True, default=func.current_timestamp())
    profile_img_url = Column(String(255), nullable=True)
    files_id = Column(Integer, ForeignKey('files.id'), nullable=True)
    conversation = Column(Text, nullable=True)
    lead_source_id = Column(Integer, nullable=True)
    candidate_identifier = Column(String(20), nullable=True)

