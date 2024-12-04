from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from DataAccessLayer.models import Base

from sqlalchemy import func

class Locations(Base):
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True, nullable=True)
    name = Column(String(255), nullable=True)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    zip = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)

    users = relationship("Users", secondary='user_location', back_populates="locations")
