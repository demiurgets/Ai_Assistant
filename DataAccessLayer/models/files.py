from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class Files(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True, nullable=True)
    name = Column(String(255), nullable=True)
    uri = Column(String(255), nullable=True)
    type = Column(String(50), nullable=True)
    date_created = Column(DateTime, nullable=True, default=func.current_timestamp())
    date_updated = Column(DateTime, nullable=True, default=func.current_timestamp())

