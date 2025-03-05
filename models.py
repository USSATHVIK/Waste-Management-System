from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    carbon_offset = db.Column(db.Float, default=0.0)  # Stores carbon offset in kg CO2e
    
    # Relationships
    waste_collections = db.relationship('WasteCollection', backref='user', lazy=True)
    recycling_activities = db.relationship('RecyclingActivity', backref='user', lazy=True)
    incentives = db.relationship('Incentive', backref='user', lazy=True)
    pickup_schedules = db.relationship('PickupSchedule', backref='user', lazy=True)
    logins = db.relationship('UserLogin', backref='user', lazy=True)
    green_activities = db.relationship('GreenActivity', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class UserLogin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # IPv6 addresses can be up to 45 chars
    user_agent = db.Column(db.String(255))  # Browser/device info
    status = db.Column(db.String(20), default='success')  # success, failed, etc.

class WasteCollection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scheduled_date = db.Column(db.DateTime, nullable=False)
    waste_type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class RecyclingCenter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(250), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    contact_number = db.Column(db.String(20))
    operating_hours = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)

class Incentive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points_earned = db.Column(db.Integer, nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)
    date_earned = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))

class WasteStatistics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_waste = db.Column(db.Float, nullable=False)
    recycled_waste = db.Column(db.Float, nullable=False)
    waste_type = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    carbon_offset = db.Column(db.Float, default=0.0)

class PickupSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pickup_date = db.Column(db.DateTime, nullable=False)
    waste_type = db.Column(db.String(50), nullable=False)
    quantity_estimate = db.Column(db.Float)
    status = db.Column(db.String(20), nullable=False, default='Scheduled')
    pickup_address = db.Column(db.String(250), nullable=False)
    special_instructions = db.Column(db.Text)

class RecyclingActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)
    points_earned = db.Column(db.Integer, nullable=False, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)

class GreenActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., 'recycling', 'transport', 'energy'
    description = db.Column(db.String(200))
    carbon_offset = db.Column(db.Float, nullable=False)  # kg CO2e saved
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GreenActivity {self.activity_type} - {self.carbon_offset}kg CO2e>'

class WasteGuideline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    waste_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    disposal_method = db.Column(db.String(100), nullable=False)
    recycling_tips = db.Column(db.Text)
    image_url = db.Column(db.String(200))