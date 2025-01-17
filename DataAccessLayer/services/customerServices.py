from sqlalchemy.orm import Session, sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine
from uuid import UUID
import uuid

from DataAccessLayer.models.customer import Customer, CustomerSetting, SettingType
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

dbname = os.getenv("settingsdbName")
user = os.getenv("user", "postgres")
password = os.getenv("password", "Not24get!")
host = os.getenv("host", "localhost")
port = os.getenv("pg_port", "5432")

print(f"Host: {host}")
print(f"Port: {port}")

# Database connection setup
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)

def setting_to_dict(setting):
    return {
        "setting_type": setting.setting_type.setting_name,
        "value": setting.value_customer_setting
    }
def get_customer_settings(customer_id):
    try:
        if not isinstance(customer_id, uuid.UUID):
            customer_uuid = uuid.UUID(str(customer_id))
        else:
            customer_uuid = customer_id
    except ValueError:
        print(f"Invalid UUID format: {customer_id}")
        return {}
    
    try:
        settings = db_session.query(CustomerSetting).join(SettingType).filter(CustomerSetting.id_customer == customer_uuid).all()
        return {setting.setting_type.setting_name: setting.value_customer_setting for setting in settings}
    except SQLAlchemyError as e:
        print(f"Error fetching settings for customer {customer_id}: {e}")
        db_session.rollback()
        return {}

def get_all_customers():
    try:
        customers = db_session.query(Customer).all()
        return [{"id": str(customer.id_customer), "name": customer.name_customer} for customer in customers]
    except SQLAlchemyError as e:
        print(f"Error fetching all customers: {e}")
        db_session.rollback()
        return []

def create_customer(customer_data, settings_data):
    try:
        new_customer = Customer(name_customer=customer_data.get("name"))
        db_session.add(new_customer)
        db_session.flush()  # Retrieve generated ID

        for setting_name, value in settings_data.items():
            setting_type = db_session.query(SettingType).filter_by(setting_name=setting_name).first()
            if not setting_type:
                setting_type = SettingType(setting_name=setting_name)
                db_session.add(setting_type)
                db_session.flush()
            
            customer_setting = CustomerSetting(
                id_customer=new_customer.id_customer,
                id_setting=setting_type.id_setting,
                value_customer_setting=value
            )
            db_session.add(customer_setting)
        
        db_session.commit()
        return {"id": str(new_customer.id_customer), "name": new_customer.name_customer}
    except SQLAlchemyError as e:
        print(f"Error creating customer: {e}")
        db_session.rollback()
        return None

def update_customer_setting(customer_id, setting_name, new_value):
    try:
        customer_uuid = uuid.UUID(customer_id)
    except ValueError:
        print(f"Invalid UUID format: {customer_id}")
        return False
    
    try:
        setting_type = db_session.query(SettingType).filter_by(setting_name=setting_name).first()
        if not setting_type:
            print(f"Setting '{setting_name}' not found.")
            return False

        customer_setting = db_session.query(CustomerSetting).filter_by(
            id_customer=customer_uuid, id_setting=setting_type.id_setting
        ).first()

        if customer_setting:
            customer_setting.value_customer_setting = new_value
        else:
            customer_setting = CustomerSetting(
                id_customer=customer_uuid,
                id_setting=setting_type.id_setting,
                value_customer_setting=new_value
            )
            db_session.add(customer_setting)
        
        db_session.commit()
        return True
    except SQLAlchemyError as e:
        print(f"Error updating setting for customer {customer_id}: {e}")
        db_session.rollback()
        return False

def delete_customer(customer_id):
    try:
        customer_uuid = uuid.UUID(customer_id)
    except ValueError:
        print(f"Invalid UUID format: {customer_id}")
        return False
    
    try:
        db_session.query(CustomerSetting).filter_by(id_customer=customer_uuid).delete(synchronize_session=False)
        db_session.query(Customer).filter_by(id_customer=customer_uuid).delete(synchronize_session=False)
        db_session.commit()
        return True
    except SQLAlchemyError as e:
        print(f"Error deleting customer {customer_id}: {e}")
        db_session.rollback()
        return False
