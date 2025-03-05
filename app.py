from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from datetime import datetime, timezone, UTC
from models import db, User, WasteCollection, RecyclingCenter, Incentive, WasteStatistics, PickupSchedule, RecyclingActivity, WasteGuideline, UserLogin
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect

# Load environment variables
load_dotenv()

# Initialize Flask
app = Flask(__name__)

# Ensure the instance folder exists
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# Configure Flask app
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(instance_path, 'ecotrack.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

# Upload Configuration
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))
app.config['ALLOWED_EXTENSIONS'] = set(os.getenv('ALLOWED_EXTENSIONS', 'png,jpg,jpeg,gif').split(','))

# Initialize extensions
print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")  # Debug print
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

mail = Mail(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        # Get client info
        ip_address = request.remote_addr
        user_agent = request.user_agent.string
        
        try:
            if user and user.check_password(password):
                # Successful login
                login_user(user)
                
                # Record successful login
                login_record = UserLogin(
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status='success'
                )
                db.session.add(login_record)
                db.session.commit()
                
                flash('Welcome back!', 'success')
                return redirect(url_for('dashboard'))
            else:
                # Record failed login attempt if user exists
                if user:
                    login_record = UserLogin(
                        user_id=user.id,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        status='failed'
                    )
                    db.session.add(login_record)
                    db.session.commit()
                
                flash('Invalid email or password', 'danger')
                
        except Exception as e:
            print(f"Login error: {e}")
            db.session.rollback()
            flash('An error occurred during login. Please try again.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Enhanced validation
            if not username or len(username) < 3:
                flash('Username must be at least 3 characters long', 'danger')
                return redirect(url_for('register'))
                
            if not email or '@' not in email:
                flash('Please provide a valid email address', 'danger')
                return redirect(url_for('register'))
                
            if not password or len(password) < 6:
                flash('Password must be at least 6 characters long', 'danger')
                return redirect(url_for('register'))
            
            # Check for existing username
            if User.query.filter_by(username=username).first():
                flash('Username already taken', 'danger')
                return redirect(url_for('register'))
                
            # Check for existing email
            if User.query.filter_by(email=email).first():
                flash('Email already registered', 'danger')
                return redirect(url_for('register'))
            
            # Create new user
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            # Log in the user immediately after registration
            login_user(user)
            
            # Initialize user's waste statistics
            stats = WasteStatistics(
                user_id=user.id,
                total_waste=0.0,
                recycled_waste=0.0,
                waste_type='Initial',
                date=datetime.now(UTC).date(),
                carbon_offset=0.0
            )
            db.session.add(stats)
            db.session.commit()
            
            flash('Registration successful! Welcome to EcoTrack!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

# Main routes
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        # Get waste collections for calculations
        waste_collections = WasteCollection.query.filter_by(user_id=current_user.id).order_by(WasteCollection.created_at.desc()).all()
        
        # Calculate totals
        total_waste = sum(float(collection.quantity) for collection in waste_collections) if waste_collections else 0.0
        recycled_waste = sum(float(collection.quantity) for collection in waste_collections if collection.status == 'Recycled') if waste_collections else 0.0
        carbon_offset = recycled_waste * 2.5  # Example: 2.5 kg CO2 per kg recycled
        
        # Get or create waste statistics
        stats = WasteStatistics.query.filter_by(user_id=current_user.id).order_by(WasteStatistics.date.desc()).first()
        
        if not stats:
            # Create new statistics record
            stats = WasteStatistics(
                user_id=current_user.id,
                total_waste=total_waste,
                recycled_waste=recycled_waste,
                carbon_offset=carbon_offset,
                waste_type='Total',
                date=datetime.now(UTC).date()
            )
            db.session.add(stats)
            db.session.commit()
        else:
            # Update existing statistics
            stats.total_waste = total_waste
            stats.recycled_waste = recycled_waste
            stats.carbon_offset = carbon_offset
            stats.date = datetime.now(UTC).date()
            db.session.commit()
        
        # Get recent activities
        activities = RecyclingActivity.query.filter_by(user_id=current_user.id).order_by(RecyclingActivity.date.desc()).limit(5).all()
        
        return render_template('dashboard.html', 
                             stats=[stats],  # Wrap in list since template expects iterable
                             activities=activities,
                             waste_collections=waste_collections,
                             total_waste=total_waste,
                             recycled_waste=recycled_waste,
                             carbon_offset=carbon_offset)
                             
    except Exception as e:
        print(f"Dashboard error: {e}")
        flash('Error loading dashboard data', 'danger')
        return render_template('dashboard.html', 
                             stats=[{'total_waste': 0, 'recycled_waste': 0, 'carbon_offset': 0}],
                             activities=[],
                             waste_collections=[],
                             total_waste=0,
                             recycled_waste=0,
                             carbon_offset=0)

@app.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule_pickup():
    try:
        if request.method == 'POST':
            # Get form data
            pickup_date = request.form.get('pickup_date')
            waste_type = request.form.get('waste_type')
            quantity = request.form.get('quantity')
            address = request.form.get('address')
            instructions = request.form.get('instructions', '')

            # Basic validation
            if not all([pickup_date, waste_type, quantity, address]):
                flash('Please fill in all required fields.', 'danger')
                return redirect(url_for('schedule_pickup'))

            try:
                # Convert date string to datetime object
                pickup_date = datetime.strptime(pickup_date, '%Y-%m-%d')
                quantity = float(quantity)

                # Validate date is in the future
                if pickup_date.date() < datetime.now(UTC).date():
                    flash('Pickup date must be in the future.', 'danger')
                    return redirect(url_for('schedule_pickup'))

                # Validate quantity
                if not (0.1 <= quantity <= 100):
                    flash('Quantity must be between 0.1 and 100 kg.', 'danger')
                    return redirect(url_for('schedule_pickup'))

            except (ValueError, TypeError):
                flash('Invalid date or quantity format.', 'danger')
                return redirect(url_for('schedule_pickup'))

            try:
                # Create new pickup schedule
                new_pickup = PickupSchedule(
                    user_id=current_user.id,
                    pickup_date=pickup_date,
                    waste_type=waste_type,
                    quantity_estimate=quantity,
                    pickup_address=address,
                    special_instructions=instructions,
                    status='Scheduled'
                )

                # Points calculation
                points_per_kg = {
                    'Plastic': 15,
                    'Paper': 10,
                    'Glass': 12,
                    'Metal': 20,
                    'Organic': 8,
                    'Electronic': 25
                }
                base_points = int(quantity * points_per_kg.get(waste_type, 10))

                # Create recycling activity
                activity = RecyclingActivity(
                    user_id=current_user.id,
                    activity_type='Pickup Scheduled',
                    description=f'Scheduled {quantity} kg of {waste_type} waste pickup',
                    points_earned=base_points,
                    date=datetime.now(UTC)
                )

                # Add to database and commit
                db.session.add(new_pickup)
                db.session.add(activity)
                
                # Update user points
                current_user.points += base_points
                
                # Commit all changes
                db.session.commit()

                flash(f'Pickup scheduled successfully! You earned {base_points} points.', 'success')
                return redirect(url_for('dashboard'))

            except Exception as e:
                db.session.rollback()
                print(f"Database Error: {str(e)}")
                flash('Failed to schedule pickup. Please try again.', 'danger')
                return redirect(url_for('schedule_pickup'))

        # GET request - show schedule page with existing pickups
        existing_pickups = PickupSchedule.query.filter_by(
            user_id=current_user.id
        ).order_by(
            PickupSchedule.pickup_date.desc()
        ).all()

        return render_template('schedule.html', existing_pickups=existing_pickups)

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        flash('An unexpected error occurred.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/locator')
def recycling_centers():
    try:
        # Fetch all active recycling centers
        centers = RecyclingCenter.query.filter_by(is_active=True).all()
        
        # If no centers exist, add sample data for Bangalore area
        if not centers:
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
            
            try:
                for center in sample_centers:
                    db.session.add(center)
                db.session.commit()
                centers = sample_centers
            except Exception as db_error:
                db.session.rollback()
                print(f"Error adding sample centers: {str(db_error)}")
                raise
        
        # Prepare centers data for template
        centers_data = []
        for center in centers:
            center_data = {
                'id': center.id,
                'name': center.name,
                'address': center.address,
                'contact': center.contact_number,
                'latitude': float(center.latitude),
                'longitude': float(center.longitude),
                'operating_hours': center.operating_hours,
                'waste_types': ['Plastic', 'Paper', 'Glass', 'Metal', 'Electronic', 'Organic']
            }
            centers_data.append(center_data)
        
        return render_template('locator.html', centers=centers_data)
    
    except Exception as e:
        import traceback
        print(f"Error in recycling_centers route: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        flash('Unable to load recycling centers. Please try again later.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/incentives')
@login_required
def incentives():
    user_points = current_user.points
    activities = RecyclingActivity.query.filter_by(user_id=current_user.id).all()
    return render_template('incentives.html', points=user_points, activities=activities)

@app.route('/guidelines')
def guidelines():
    guidelines = WasteGuideline.query.all()
    return render_template('guidelines.html', guidelines=guidelines)

@app.route('/waste-details', methods=['GET'])
@login_required
def waste_details():
    try:
        # Debug: Print current user information
        print(f"Current User ID: {current_user.id}")
        print(f"Current User Email: {current_user.email}")
        
        # Fetch waste collections for the current user, ordered by most recent first
        waste_collections = WasteCollection.query.filter_by(user_id=current_user.id).order_by(WasteCollection.created_at.desc()).limit(50).all()
        
        # Debug: Print number of waste collections
        print(f"Number of Waste Collections: {len(waste_collections)}")
        
        # Prepare collections data with additional formatting
        collections_data = []
        for collection in waste_collections:
            # Debug: Print each collection details
            print(f"Collection Details: ID={collection.id}, Type={collection.waste_type}, Quantity={collection.quantity}, Status={collection.status}")
            
            # Calculate points for this collection
            points_per_kg = {
                'Plastic': 15, 'Paper': 10, 'Glass': 12, 
                'Metal': 20, 'Organic': 8, 'Electronic': 25
            }
            base_points = int(collection.quantity * points_per_kg.get(collection.waste_type, 10))
            
            # Bonus points for recycled status
            if collection.status == 'Recycled':
                base_points = int(base_points * 1.5)
            
            collections_data.append({
                'id': collection.id,
                'created_at': collection.created_at.strftime('%Y-%m-%d %H:%M'),
                'waste_type': collection.waste_type,
                'quantity': collection.quantity,
                'status': collection.status,
                'notes': collection.notes or 'No additional notes',
                'points_earned': base_points
            })
        
        # Prepare waste type distribution for chart
        waste_type_counts = {}
        for collection in waste_collections:
            waste_type_counts[collection.waste_type] = waste_type_counts.get(collection.waste_type, 0) + 1
        
        # Debug: Print waste type counts
        print(f"Waste Type Counts: {waste_type_counts}")
        
        return render_template(
            'waste_details.html', 
            waste_collections=waste_collections, 
            collections_data=collections_data,
            waste_type_counts=waste_type_counts
        )
    
    except Exception as e:
        # Log the full error details
        import traceback
        print(f"Error in waste_details route: {str(e)}")
        print(traceback.format_exc())
        
        # Flash a user-friendly error message
        flash('Unable to load waste details. Please try again later.', 'danger')
        
        # Redirect to dashboard or handle the error appropriately
        return redirect(url_for('dashboard'))

@app.route('/add-waste-details', methods=['POST'])
@login_required
def add_waste_details():
    try:
        waste_type = request.form.get('waste_type')
        quantity = float(request.form.get('quantity', 0))
        status = request.form.get('status', 'Pending')
        notes = request.form.get('notes', '')
        
        if not waste_type or quantity <= 0:
            flash('Please provide valid waste details', 'danger')
            return redirect(url_for('dashboard'))
        
        # Create waste collection record
        current_time = datetime.now(UTC)
        collection = WasteCollection(
            user_id=current_user.id,
            waste_type=waste_type,
            quantity=quantity,
            status=status,
            notes=notes,
            scheduled_date=current_time
        )
        db.session.add(collection)
        
        # Calculate points based on waste quantity and type
        points_per_kg = {
            'Plastic': 15,    # Higher points for plastic due to recycling importance
            'Paper': 10,      # Medium points for paper
            'Glass': 12,      # Medium-high points for glass
            'Metal': 20,      # Highest points for metal due to value
            'Organic': 8      # Lower points for organic waste
        }
        
        base_points = int(quantity * points_per_kg.get(waste_type, 10))  # Default 10 points if type not found
        
        # Bonus points for recycled status
        if status == 'Recycled':
            base_points = int(base_points * 1.5)  # 50% bonus for recycled waste
        
        # Update user's points
        current_user.points += base_points
        
        # Create recycling activity record
        activity = RecyclingActivity(
            user_id=current_user.id,
            activity_type='Waste Added',
            description=f'Added {quantity} kg of {waste_type} waste',
            date=current_time,
            points_earned=base_points
        )
        db.session.add(activity)
        
        # Update user's waste statistics
        stats = WasteStatistics.query.filter_by(user_id=current_user.id).order_by(WasteStatistics.date.desc()).first()
        if not stats:
            stats = WasteStatistics(
                user_id=current_user.id,
                total_waste=quantity,
                recycled_waste=quantity if status == 'Recycled' else 0,
                waste_type=waste_type,
                date=current_time.date(),
                carbon_offset=quantity * 2.5 if status == 'Recycled' else 0
            )
            db.session.add(stats)
        else:
            stats.total_waste += quantity
            if status == 'Recycled':
                stats.recycled_waste += quantity
                stats.carbon_offset += quantity * 2.5
            stats.date = current_time.date()
        
        db.session.commit()
        flash('Waste details added successfully!', 'success')
        
    except ValueError:
        flash('Please enter a valid quantity', 'danger')
    except Exception as e:
        db.session.rollback()
        print(f"Error adding waste details: {str(e)}")
        flash('An error occurred while adding waste details', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/delete-waste/<int:activity_id>', methods=['POST'])
@login_required
def delete_waste(activity_id):
    try:
        # Get the activity record
        activity = RecyclingActivity.query.filter_by(id=activity_id, user_id=current_user.id).first()
        
        if not activity:
            flash('Record not found.', 'danger')
            return redirect(url_for('dashboard'))
            
        # Parse the quantity from the description
        description_parts = activity.description.split()
        quantity = float(description_parts[1])  # Gets the number before 'kg'
        waste_type = description_parts[4]  # Gets the waste type
        
        # Find and delete the corresponding waste collection
        waste_collection = WasteCollection.query.filter_by(
            user_id=current_user.id,
            waste_type=waste_type,
            quantity=quantity
        ).first()
        
        if waste_collection:
            # Update user's points
            current_user.points -= activity.points_earned
            
            # Update waste statistics
            stats = WasteStatistics.query.filter_by(user_id=current_user.id).order_by(WasteStatistics.date.desc()).first()
            if stats:
                stats.total_waste -= quantity
                if waste_collection.status == 'Recycled':
                    stats.recycled_waste -= quantity
                    stats.carbon_offset -= quantity * 2.5
            
            # Delete the records
            db.session.delete(waste_collection)
            db.session.delete(activity)
            db.session.commit()
            
            flash('Waste record deleted successfully!', 'success')
        else:
            flash('Associated waste collection not found.', 'warning')
            db.session.delete(activity)
            db.session.commit()
            
    except Exception as e:
        print(f"Error deleting waste: {str(e)}")
        db.session.rollback()
        flash('An error occurred while deleting the waste record.', 'danger')
    
    return redirect(url_for('dashboard'))

# Carbon offset calculation and routes
def calculate_carbon_offset(activity_type, quantity):
    """Calculate carbon offset based on activity type and quantity"""
    offset_factors = {
        'recycling_paper': 0.9,      # kg CO2e per kg of paper recycled
        'recycling_plastic': 1.5,    # kg CO2e per kg of plastic recycled
        'recycling_glass': 0.3,      # kg CO2e per kg of glass recycled
        'recycling_metal': 4.0,      # kg CO2e per kg of metal recycled
        'public_transport': 0.1,     # kg CO2e per km traveled
        'cycling': 0.2,              # kg CO2e per km traveled (compared to driving)
        'tree_planting': 20,         # kg CO2e per tree per year
    }
    return offset_factors.get(activity_type, 0) * quantity

@app.route('/base')
@login_required
def dashboard():
    user = current_user
    
    # Get user's waste collections
    collections = WasteCollection.query.filter_by(user_id=user.id).all()
    
    # Calculate total carbon offset from waste collections
    total_offset = 0
    for collection in collections:
        if collection.waste_type == 'Paper':
            total_offset += calculate_carbon_offset('recycling_paper', collection.quantity)
        elif collection.waste_type == 'Plastic':
            total_offset += calculate_carbon_offset('recycling_plastic', collection.quantity)
        elif collection.waste_type == 'Glass':
            total_offset += calculate_carbon_offset('recycling_glass', collection.quantity)
        elif collection.waste_type == 'Metal':
            total_offset += calculate_carbon_offset('recycling_metal', collection.quantity)
    
    # Get user's green activities
    activities = GreenActivity.query.filter_by(user_id=user.id).all()
    
    # Add offset from other green activities
    for activity in activities:
        total_offset += activity.carbon_offset
    
    # Update user's total carbon offset
    user.carbon_offset = total_offset
    db.session.commit()
    
    return render_template('dashboard.html',
                         user=user,
                         collections=collections,
                         activities=activities,
                         carbon_offset=total_offset)

@app.route('/offset-calculator')
@login_required
def offset_calculator():
    return render_template('offset_calculator.html')

@app.route('/add-green-activity', methods=['POST'])
@login_required
def add_green_activity():
    try:
        activity_type = request.form.get('activity_type')
        quantity = float(request.form.get('quantity'))
        description = request.form.get('description')
        
        # Calculate carbon offset
        offset = calculate_carbon_offset(activity_type, quantity)
        
        # Create new activity
        activity = GreenActivity(
            user_id=current_user.id,
            activity_type=activity_type,
            description=description,
            carbon_offset=offset
        )
        
        db.session.add(activity)
        db.session.commit()
        
        flash('Green activity added successfully!', 'success')
    except Exception as e:
        flash('Error adding green activity. Please try again.', 'danger')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('dashboard'))

# Database initialization
def init_db():
    print("Starting database initialization...")
    print(f"Instance path: {instance_path}")
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    try:
        with app.app_context():
            # Drop all existing tables (optional, use carefully)
            # db.drop_all()
            
            print("Creating database tables...")
            db.create_all()
            
            # Verify table creation
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Created tables: {tables}")
            
            print("Database tables created successfully!")
            
            # Check if we need to add sample data
            if User.query.count() == 0:
                print("Adding sample data...")
                try:
                    # Create a sample user if no users exist
                    sample_user = User(
                        username='testuser',
                        email='test@ecotrack.com',
                        points=0
                    )
                    sample_user.set_password('password123')
                    db.session.add(sample_user)
                    
                    # Add sample recycling center
                    center = RecyclingCenter(
                        name='EcoCenter Main',
                        address='123 Green Street, Eco City',
                        latitude=37.7749,
                        longitude=-122.4194,
                        contact_number='555-0123',
                        operating_hours='Mon-Fri: 9AM-5PM',
                        accepted_materials='Paper, Plastic, Glass, Metal'
                    )
                    db.session.add(center)
                    
                    # Commit sample data
                    db.session.commit()
                    print("Sample data added successfully!")
                    
                except Exception as sample_error:
                    db.session.rollback()
                    print(f"Error adding sample data: {sample_error}")
            
    except Exception as e:
        print(f"Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        raise

# Add database diagnostics route
@app.route('/db-diagnostics')
@login_required
def database_diagnostics():
    try:
        # Check database connection
        try:
            db.session.execute('SELECT 1')
            connection_status = 'Successful'
        except Exception as conn_error:
            connection_status = f'Failed: {conn_error}'
        
        # Check table existence
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        # Count records in key tables
        table_counts = {}
        for table in ['user', 'pickup_schedule', 'recycling_activity', 'recycling_center']:
            try:
                count = db.session.execute(f'SELECT COUNT(*) FROM {table}').scalar()
                table_counts[table] = count
            except Exception as count_error:
                table_counts[table] = f'Error: {count_error}'
        
        diagnostics = {
            'connection_status': connection_status,
            'tables_found': tables,
            'table_record_counts': table_counts,
            'database_uri': app.config['SQLALCHEMY_DATABASE_URI']
        }
        
        return jsonify(diagnostics)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Sample data initialization
def add_sample_waste_data(user_id):
    sample_data = [{
        'waste_type': 'Plastic',
        'quantity': 2.5,
        'notes': 'Weekly household plastic waste including water bottles and packaging',
        'status': 'Collected'
    },
    {
        'waste_type': 'Paper',
        'quantity': 3.0,
        'notes': 'Old newspapers, magazines, and cardboard boxes',
        'status': 'Collected'
    },
    {
        'waste_type': 'Organic',
        'quantity': 4.0,
        'notes': 'Kitchen waste and garden trimmings',
        'status': 'Collected'
    },
    {
        'waste_type': 'Glass',
        'quantity': 1.5,
        'notes': 'Used glass bottles and jars',
        'status': 'Collected'
    },
    {
        'waste_type': 'Electronic',
        'quantity': 0.8,
        'notes': 'Old phone chargers and broken headphones',
        'status': 'Collected'
    },
    {
        'waste_type': 'Metal',
        'quantity': 1.2,
        'notes': 'Used aluminum cans and metal containers',
        'status': 'Collected'
    }]
    
    for data in sample_data:
        new_collection = WasteCollection(
            user_id=user_id,
            waste_type=data['waste_type'],
            quantity=data['quantity'],
            notes=data['notes'],
            scheduled_date=datetime.now(UTC),
            status=data['status']
        )
        db.session.add(new_collection)
    
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error adding sample data: {str(e)}")
        return False

# Add route to initialize sample data
@app.route('/initialize-sample-data')
@login_required
def initialize_sample_data():
    if add_sample_waste_data(current_user.id):
        flash('Sample waste data has been added successfully!', 'success')
    else:
        flash('Error adding sample data.', 'danger')
    return redirect(url_for('waste_details'))

# API routes
@app.route('/api/waste-stats')
@login_required
def get_waste_stats():
    try:
        # Get user's waste statistics
        stats = WasteStatistics.query.filter_by(user_id=current_user.id).order_by(WasteStatistics.date.desc()).first()
        
        if not stats:
            return jsonify({
                'total_waste': 0,
                'recycled_waste': 0,
                'carbon_offset': 0,
                'recycling_rate': 0
            })
        
        # Calculate recycling rate
        recycling_rate = (stats.recycled_waste / stats.total_waste * 100) if stats.total_waste > 0 else 0
        
        return jsonify({
            'total_waste': float(stats.total_waste),
            'recycled_waste': float(stats.recycled_waste),
            'carbon_offset': float(stats.carbon_offset),
            'recycling_rate': round(recycling_rate, 2)
        })
    except Exception as e:
        print(f"Error in get_waste_stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch waste statistics'}), 500

@app.route('/login-history')
@login_required
def login_history():
    # Get user's login history
    history = UserLogin.query.filter_by(user_id=current_user.id)\
        .order_by(UserLogin.login_time.desc())\
        .all()
    
    return render_template('login_history.html', login_history=history)

# Test route for environment variables
@app.route('/test-config')
def test_config():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
        
    config_status = {
        'flask_config': {
            'debug': app.debug,
            'testing': app.testing,
            'secret_key_set': app.config['SECRET_KEY'] is not None,
        },
        'database_config': {
            'database_url_set': app.config['SQLALCHEMY_DATABASE_URI'] is not None,
            'track_modifications': app.config['SQLALCHEMY_TRACK_MODIFICATIONS'],
        },
        'mail_config': {
            'mail_server': app.config['MAIL_SERVER'],
            'mail_port': app.config['MAIL_PORT'],
            'mail_use_tls': app.config['MAIL_USE_TLS'],
            'mail_username_set': app.config['MAIL_USERNAME'] is not None,
            'mail_password_set': app.config['MAIL_PASSWORD'] is not None,
        },
        'upload_config': {
            'upload_folder': app.config['UPLOAD_FOLDER'],
            'max_content_length': app.config['MAX_CONTENT_LENGTH'],
            'allowed_extensions': list(app.config['ALLOWED_EXTENSIONS']),
        }
    }
    
    # Test database connection
    try:
        db.session.execute('SELECT 1')
        config_status['database_config']['connection_test'] = 'success'
    except Exception as e:
        config_status['database_config']['connection_test'] = f'failed: {str(e)}'
    
    # Create upload folder if it doesn't exist
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        try:
            os.makedirs(upload_folder)
            config_status['upload_config']['folder_creation'] = 'success'
        except Exception as e:
            config_status['upload_config']['folder_creation'] = f'failed: {str(e)}'
    else:
        config_status['upload_config']['folder_creation'] = 'already exists'
    
    return jsonify(config_status)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500

@app.errorhandler(403)
def forbidden_error(error):
    return jsonify({
        'error': 'Forbidden',
        'message': 'You do not have permission to access this resource'
    }), 403

@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({
        'error': 'Bad Request',
        'message': 'The server could not understand the request'
    }), 400

if __name__ == '__main__':
    print("Starting application...")
    try:
        init_db()
        print("Database initialized successfully!")
        app.run(debug=True)
    except Exception as e:
        print(f"Error starting application: {str(e)}")