from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from DataAccessLayer.models import Base

from sqlalchemy import func

class User_types(Base):
    __tablename__ = 'user_types'

    id = Column(Integer, primary_key=True, nullable=True)
    name = Column(String(255), nullable=False)

