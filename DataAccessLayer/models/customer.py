from sqlalchemy import Column, String, Integer, ForeignKey, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()

# Customer Table
class Customer(Base):
    __tablename__ = 'customer'
    
    id_customer = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, name="id_customer")
    name_customer = Column(String, nullable=False, name="name_customer")
    
    # Relationship to CustomerSetting
    settings = relationship("CustomerSetting", back_populates="customer", cascade="all, delete-orphan")

# SettingType Table
class SettingType(Base):
    __tablename__ = 'setting_type'
    
    id_setting = Column(Integer, primary_key=True, autoincrement=True, name="id_setting")
    setting_name = Column(String, nullable=False, unique=True, name="setting_name")
    
    # Relationship to CustomerSetting
    customer_settings = relationship("CustomerSetting", back_populates="setting_type", cascade="all, delete-orphan")

# CustomerSetting Table
class CustomerSetting(Base):
    __tablename__ = 'customer_setting'
    
    id_customer_setting = Column(Integer, primary_key=True, autoincrement=True, name="id_customer_setting")
    id_customer = Column(UUID(as_uuid=True), ForeignKey('customer.id_customer'), nullable=False, name="id_customer")
    id_setting = Column(Integer, ForeignKey('setting_type.id_setting'), nullable=False, name="id_setting")
    value_customer_setting = Column(String, nullable=False, name="value_customer_setting")
    
    # Relationships
    customer = relationship("Customer", back_populates="settings")
    setting_type = relationship("SettingType", back_populates="customer_settings")
