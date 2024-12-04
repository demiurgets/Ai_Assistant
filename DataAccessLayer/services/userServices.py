from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.users import Users
from DataAccessLayer.models.user_location import UserLocation
from DataAccessLayer.models.locations import Locations


import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import bcrypt

#TO RUN THIS SCRIPT THRU TERMINAL, RUN python -m DataAccessLayer.services  FROM ROOT

# Load environment variables
load_dotenv(override=True)

# Database configuration
dbname = os.getenv('dbname', 'qonda')
user = os.getenv('user', 'postgres')
password = os.getenv('password', 'Not24get!')
host = os.getenv('host', 'localhost')
port = os.getenv('pg_port', '5432')

print(host)
print(port)

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
db_session = Session()

# Function to convert user model to dictionary
def user_to_dict(user):
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "password": user.password,
        "phone": user.phone,
        "company_id": user.company_id,
        "user_type_id": user.user_type_id,
        "address": user.address,
        "city": user.city,
        "state": user.state,
        "zip": user.zip,
        "status_id": user.status_id,
        "focus_percentage": user.focus_percentage,
        "created_date": user.created_date,
        "updated_date": user.updated_date,
        "start_date": user.start_date,
        "profile_img_url": user.profile_img_url,
    }
    
#from DataAccessLayer.models import Base
#from sqlalchemy import create_engine


#def test_alchemy():
#    engine = create_engine(database_url)
#    Base.metadata.create_all(engine)  # This creates all tables defined by Base subclasses

#test_alchemy()
    
    
    
def user_with_location_to_dict(user, location_data):
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "password": user.password,
        "phone": user.phone,
        "company_id": user.company_id,
        "user_type_id": user.user_type_id,
        "address": user.address,
        "city": user.city,
        "state": user.state,
        "zip": user.zip,
        "status_id": user.status_id,
        "focus_percentage": user.focus_percentage,
        "created_date": user.created_date,
        "updated_date": user.updated_date,
        "start_date": user.start_date,
        "profile_img_url": user.profile_img_url,
        "location_ids": location_data
    }
    


# 1. Get all users
def get_all_users():
    try:
        users = db_session.query(Users).all()
        return [user_to_dict(user) for user in users]
    except SQLAlchemyError as e:
        print(f"Error fetching all users: {e}")
        return []

# 2. Get user by ID
def get_user_by_id(user_id):
    try:
        user = db_session.query(Users).filter(Users.id == user_id).first()
        if not user:
            return None
        user_locations = db_session.query(
            UserLocation.location_id,
            Locations.name
        ).join(Locations, UserLocation.location_id == Locations.id).filter(UserLocation.user_id == user.id).all()
        
        location_data = [{"id": ul.location_id, "name": ul.name} for ul in user_locations]

        return user_with_location_to_dict(user, location_data)
    except SQLAlchemyError as e:
        print(f"Error fetching user by ID: {e}")
        return None

# 3. Get users by status
def get_users_by_status(status_id):
    try:
        users = db_session.query(Users).filter(Users.status_id == status_id).all()
        return [user_to_dict(user) for user in users]
    except SQLAlchemyError as e:
        print(f"Error fetching users by status: {e}")
        return []

# 4. Create a new user


# def create_user(user_data):
#     try:
#         # Encrypt the password
#         plain_password = user_data.get("password")
#         if not plain_password:
#             raise ValueError("Password is required")
#         hashed_password = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())

#         # Create a new user
#         new_user = Users(
#             first_name=user_data.get("first_name"),
#             last_name=user_data.get("last_name"),
#             email=user_data.get("email"),
#             password=hashed_password.decode('utf-8'),  # Store as a string
#             phone=user_data.get("phone"),
#             company_id=user_data.get("company_id"),
#             user_type_id=user_data.get("user_type_id"),
#             location_id=user_data.get("location_id"),
#             address=user_data.get("address"),
#             city=user_data.get("city"),
#             state=user_data.get("state"),
#             zip=user_data.get("zip"),
#             status_id=user_data.get("status_id"),
#             focus_percentage=user_data.get("focus_percentage"),
#             start_date=user_data.get("start_date"),
#             profile_img_url=user_data.get("profile_img_url"),
#         )
#         db_session.add(new_user)
#         db_session.commit()
#         return user_to_dict(new_user)
#     except SQLAlchemyError as e:
#         print(f"Error creating user: {e}")
#         db_session.rollback()
#         return None
#     except ValueError as e:
#         print(f"Error: {e}")
#         return None

# 4. Create a new user
def create_user(user_data):
    try:
        # Get the password
        plain_password = user_data.get("password")
        if not plain_password:
            raise ValueError("Password is required")

        # Create a new user
        new_user = Users(
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            email=user_data.get("email"),
            password=plain_password,  # Store as plain text
            phone=user_data.get("phone"),
            company_id=user_data.get("company_id"),
            user_type_id=user_data.get("user_type_id"),
            address=user_data.get("address"),
            city=user_data.get("city"),
            state=user_data.get("state"),
            zip=user_data.get("zip"),
            status_id=user_data.get("status_id"),
            focus_percentage=user_data.get("focus_percentage"),
            start_date=user_data.get("start_date"),
            profile_img_url=user_data.get("profile_img_url"),
        )
        
        
        db_session.add(new_user)
        db_session.commit()
        
        location_ids = user_data.get("location_ids", [])
        if location_ids:
            for location_id in location_ids:
                user_location = UserLocation(user_id=new_user.id, location_id=location_id)
                db_session.add(user_location)

            db_session.commit()
            
        user_locations = db_session.query(
            UserLocation.location_id,
            Locations.name
        ).join(Locations, UserLocation.location_id == Locations.id).filter(UserLocation.user_id == new_user.id).all()
        
        location_data = [{"id": ul.location_id, "name": ul.name} for ul in user_locations]
        
        return user_with_location_to_dict(new_user,location_data)
    except SQLAlchemyError as e:
        print(f"Error creating user: {e}")
        db_session.rollback()
        return None
    except ValueError as e:
        print(f"Error: {e}")
        return None

# 5. Update user by ID
def update_user(user_id, update_data):
    try:
        user = db_session.query(Users).filter(Users.id == user_id).first()
        if not user:
            return None
        
        # Update user fields (except for location_ids)
        for key, value in update_data.items():
            if key != "location_ids":  # Skip location_ids here
                setattr(user, key, value)
        
        # If location_ids are provided in the update_data, modify the user's locations
        if "location_ids" in update_data:
            # Remove the existing user_location associations
            db_session.query(UserLocation).filter(UserLocation.user_id == user_id).delete()

            # Add new user_location associations
            location_ids = update_data["location_ids"]
            for location_id in location_ids:
                user_location = UserLocation(user_id=user.id, location_id=location_id)
                db_session.add(user_location)

        db_session.commit()

        # Fetch the updated locations of the user
        user_locations = db_session.query(
            UserLocation.location_id,
            Locations.name
        ).join(Locations, UserLocation.location_id == Locations.id).filter(UserLocation.user_id == user.id).all()
        
        location_data = [{"id": ul.location_id, "name": ul.name} for ul in user_locations]
        
        return user_with_location_to_dict(user, location_data)
    
    except SQLAlchemyError as e:
        print(f"Error updating user: {e}")
        db_session.rollback()
        return None


# 6. Delete user by ID
def delete_user(user_id):
    try:
        user = db_session.query(Users).filter(Users.id == user_id).first()
        if not user:
            return False
        db_session.delete(user)
        db_session.commit()
        return True
    except SQLAlchemyError as e:
        print(f"Error deleting user: {e}")
        db_session.rollback()
        return False

# def validate_password(user_email, plain_password):
#     try:
#         user = db_session.query(Users).filter(Users.email == user_email).first()
#         if not user:
#             return False
        
#         hashed_password = user.password.encode('utf-8')
#         if bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password):
#             return True
#         else:
#             return False
#     except SQLAlchemyError as e:
#         print(f"Error validating password: {e}")
#         return False

def validate_password(user_email, plain_password):
    try:
        user = db_session.query(Users).filter(Users.email == user_email).first()
        if not user:
            return False
        
        if user.password == plain_password:
            return True
        else:
            return False
    except SQLAlchemyError as e:
        print(f"Error validating password: {e}")
        return False


# 7. Update user status
def update_user_status(user_id, new_status):
    try:
        user = db_session.query(Users).filter(Users.id == user_id).first()
        if not user:
            return None
        
        user.status_id = new_status
        db_session.commit()
        return user_to_dict(user)
    
    except SQLAlchemyError as e:
        print(f"Error updating user: {e}")
        db_session.rollback()
        return None


# 8. Get user by email
def get_user_by_email(email):
    
    try:
        user = db_session.query(Users).filter(Users.email == email).first()
        return user_to_dict(user) if user else None
    except SQLAlchemyError as e:
        print(f"Error fetching user by email: {e}")
        
        
        return None
# Define 6 dummy users in JSON format
dummy_users = [
    {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "password": "password123",
        "phone": "555-1001",
        "company_id": 1,
        "address": "123 Apple St",
        "city": "Austin",
        "state": "TX",
        "zip": "73301",
        "focus_percentage": 90.0,
        "start_date": "2024-01-10",
        "profile_img_url": "http://example.com/images/alice.jpg",
    },
    {
        "first_name": "Bob",
        "last_name": "Johnson",
        "email": "bob.johnson@example.com",
        "password": "password123",
        "phone": "555-1002",
        "company_id": 1,
        "address": "456 Banana Ave",
        "city": "Dallas",
        "state": "TX",
        "zip": "75201",
        "focus_percentage": 85.0,
        "start_date": "2024-02-15",
        "profile_img_url": "http://example.com/images/bob.jpg",
    },
    {
        "first_name": "Charlie",
        "last_name": "Williams",
        "email": "charlie.williams@example.com",
        "password": "password123",
        "phone": "555-1003",
        "company_id": 1,
        "address": "789 Cherry Blvd",
        "city": "Houston",
        "state": "TX",
        "zip": "77001",
        "focus_percentage": 92.0,
        "start_date": "2024-03-20",
        "profile_img_url": "http://example.com/images/charlie.jpg",
    },
    {
        "first_name": "Diana",
        "last_name": "Brown",
        "email": "diana.brown@example.com",
        "password": "password123",
        "phone": "555-1004",
        "company_id": 1,
        "address": "321 Date Dr",
        "city": "San Antonio",
        "state": "TX",
        "zip": "78201",
        "focus_percentage": 88.5,
        "start_date": "2024-04-05",
        "profile_img_url": "http://example.com/images/diana.jpg",
    },
    {
        "first_name": "Eve",
        "last_name": "Miller",
        "email": "eve.miller@example.com",
        "password": "password123",
        "phone": "555-1005",
        "company_id": 1,
        "address": "654 Elm St",
        "city": "Austin",
        "state": "TX",
        "zip": "73302",
        "focus_percentage": 95.0,
        "start_date": "2024-05-01",
        "profile_img_url": "http://example.com/images/eve.jpg",
    },
    {
        "first_name": "Frank",
        "last_name": "Davis",
        "email": "frank.davis@example.com",
        "password": "password123",
        "phone": "555-1006",
        "company_id": 1,
        "address": "987 Fig Ln",
        "city": "Houston",
        "state": "TX",
        "zip": "77002",
        "focus_percentage": 85.0,
        "start_date": "2024-06-12",
        "profile_img_url": "http://example.com/images/frank.jpg",
    }
]

# Loop through the list of dummy users and call the create_user function
#for user in dummy_users:
#    create_user(user)
#    print(f"Created user: {user['first_name']} {user['last_name']}")


#delete_user(3)
