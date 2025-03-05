from app import app, db
from models import *

def init_database():
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        
        print("Adding sample recycling centers...")
        sample_centers = [
            RecyclingCenter(
                name='EcoRecycle Center',
                address='123 Green Street, Koramangala, Bangalore',
                latitude=12.9279,
                longitude=77.6271,
                contact_number='+91 98765 43210',
                operating_hours='Mon-Sat: 9 AM - 6 PM',
                is_active=True
            ),
            RecyclingCenter(
                name='GreenTech Recyclers',
                address='456 Earth Avenue, Indiranagar, Bangalore',
                latitude=12.9719,
                longitude=77.6412,
                contact_number='+91 98765 43211',
                operating_hours='Mon-Fri: 8 AM - 7 PM',
                is_active=True
            ),
            RecyclingCenter(
                name='E-Waste Solutions',
                address='789 Digital Lane, HSR Layout, Bangalore',
                latitude=12.9116,
                longitude=77.6474,
                contact_number='+91 98765 43212',
                operating_hours='Mon-Sun: 24/7',
                is_active=True
            )
        ]
        
        for center in sample_centers:
            db.session.add(center)
        
        try:
            db.session.commit()
            print("Sample recycling centers added successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error adding sample data: {e}")
            raise

if __name__ == '__main__':
    init_database()
