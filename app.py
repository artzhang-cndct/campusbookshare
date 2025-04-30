import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_migrate import Migrate

# App Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['PROFILE_FOLDER'] = 'static/profile_pics'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROFILE_FOLDER'], exist_ok=True)

# Helpers
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_unread_message_count():
    if current_user.is_authenticated:
        unread_count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
        return {'unread_message_count': unread_count}
    return {'unread_message_count': 0}

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    location = db.Column(db.String(150))
    profile_image = db.Column(db.String(300))

    # Relationships
    resources = db.relationship('Resource', backref='owner', lazy=True)
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    reviews_written = db.relationship('Review', foreign_keys='Review.reviewer_id', backref='written_reviews', lazy=True)
    reviews_received = db.relationship('Review', foreign_keys='Review.reviewed_id', backref='received_reviews', lazy=True)

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    category = db.Column(db.String(100), nullable=False)
    availability = db.Column(db.Boolean, default=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_read = db.Column(db.Boolean, default=False)  # Column to track if the message has been read

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviewed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationships
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], overlaps="written_reviews")
    reviewed = db.relationship('User', foreign_keys=[reviewed_id], overlaps="received_reviews")
    
# Routes
@app.route('/')
def index():
    # Fetch all users
    users = User.query.all()

    # Fetch the top 3 rated users
    top_rated_users = db.session.query(
        User, db.func.avg(Review.rating).label('average_rating')
    ).join(Review, Review.reviewed_id == User.id).group_by(User.id).order_by(db.desc('average_rating')).limit(3).all()

    # Fetch the 3 most recent listings
    recent_listings = Resource.query.order_by(Resource.date_posted.desc()).limit(3).all()

    return render_template('home.html', users=users, top_rated_users=top_rated_users, recent_listings=recent_listings)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        location = request.form['location']

        # Check if the email is already in use
        if User.query.filter_by(email=email).first():
            flash('Sorry, that email is already in use.', 'danger')
            return render_template('register.html')  # Render the template directly to avoid duplicate flashes

        # Handle profile image upload
        profile_image = request.files.get('profile_image')
        profile_image_path = None
        if profile_image and allowed_file(profile_image.filename):
            filename = secure_filename(profile_image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_image.save(image_path)
            # Normalize the path to use forward slashes
            profile_image_path = os.path.join('uploads', filename).replace('\\', '/')

        # Create a new user
        user = User(name=name, email=email, password=password, location=location, profile_image=profile_image_path)
        db.session.add(user)
        db.session.commit()

        # Automatically log in the user after registration
        login_user(user)

        flash('Registration successful! Welcome to Your Listings.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your email and password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    listings = Resource.query.filter_by(owner_id=user.id).order_by(Resource.date_posted.desc()).all()

    # Calculate the average rating for the logged-in user
    reviews = Review.query.filter_by(reviewed_id=user.id).all()
    if reviews:
        average_rating = round(sum(review.rating for review in reviews) / len(reviews), 2)
    else:
        average_rating = None

    return render_template('dashboard.html', user=user, listings=listings, is_own_dashboard=True, average_rating=average_rating)

@app.route('/dashboard/<int:user_id>')
@login_required
def user_dashboard(user_id):
    # Fetch the user by ID
    user = User.query.get_or_404(user_id)
    listings = Resource.query.filter_by(owner_id=user.id).all()  # Fetch the user's listings
    is_own_dashboard = current_user.id == user.id  # Check if the logged-in user is viewing their own dashboard
    return render_template('dashboard.html', user=user, listings=listings, is_own_dashboard=is_own_dashboard)

@app.route('/listing/new', methods=['GET', 'POST'])
@login_required
def new_listing():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        availability = True if request.form['availability'] == 'True' else False

        image_file = request.files.get('image')
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = os.path.join('uploads', filename)
        else:
            image_path = None

        new_resource = Resource(
            title=title,
            description=description,
            category=category,
            availability=availability,
            image=image_path,
            owner_id=current_user.id
        )

        db.session.add(new_resource)
        db.session.commit()
        flash('Listing created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('new_listing.html')

@app.route('/create_listing', methods=['GET', 'POST'])
@login_required
def create_listing():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        availability = request.form['availability'] == 'True'
        image_file = request.files.get('image')

        # Handle image upload
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            # Normalize the path to use forward slashes
            image_url = os.path.join('uploads', filename).replace('\\', '/')
        else:
            image_url = None  # Optional: Handle default image

        # Create a new listing
        listing = Resource(
            title=title,
            description=description,
            image=image_url,
            category=category,
            availability=availability,
            owner_id=current_user.id
        )
        db.session.add(listing)
        db.session.commit()

        flash('Listing created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('create_listing.html')

@app.route('/listing/<int:listing_id>', methods=['GET'])
def listing_detail(listing_id):
    listing = Resource.query.get_or_404(listing_id)
    owner = listing.owner

    # Fetch reviews for the owner of the listing
    reviews = Review.query.filter_by(reviewed_id=owner.id).all()

    # Calculate the average rating for the owner
    if reviews:
        average_rating = round(sum(review.rating for review in reviews) / len(reviews), 2)
    else:
        average_rating = None

    return render_template('listing_detail.html', listing=listing, reviews=reviews, average_rating=average_rating)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').strip()

    if not query:
        flash("Please enter a search term.", "warning")
        return redirect(url_for('index'))

    # Perform case-insensitive search for users and listings
    user_results = User.query.filter(User.name.ilike(f"%{query}%")).all()
    listing_results = Resource.query.filter(
        (Resource.title.ilike(f"%{query}%")) | (Resource.description.ilike(f"%{query}%"))
    ).all()

    return render_template('search_results.html', query=query, user_results=user_results, listing_results=listing_results)

@app.route('/messages', methods=['GET', 'POST'])
@login_required
def messages():
    receiver_id = request.args.get('receiver_id', type=int)
    receiver = None
    messages = []

    # Fetch all users the current user has messaged or received messages from
    user_ids = db.session.query(Message.sender_id).filter_by(receiver_id=current_user.id).union(
        db.session.query(Message.receiver_id).filter_by(sender_id=current_user.id)
    ).distinct()
    users = User.query.filter(User.id.in_(user_ids)).all()

    # If a receiver_id is provided, fetch the receiver's details and messages
    if receiver_id:
        receiver = User.query.get_or_404(receiver_id)
        messages = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver.id)) |
            ((Message.sender_id == receiver.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.asc()).all()

    if request.method == 'POST' and receiver:
        # Handle sending a new message
        content = request.form['content']
        message = Message(content=content, sender_id=current_user.id, receiver_id=receiver.id)
        db.session.add(message)
        db.session.commit()
        return redirect(url_for('messages', receiver_id=receiver.id))

    return render_template('messages.html', users=users, receiver=receiver, messages=messages)

@app.route('/review/<int:user_id>', methods=['POST'])
@login_required
def review(user_id):
    user = User.query.get_or_404(user_id)

    # Prevent users from rating themselves
    if current_user.id == user.id:
        flash("You cannot rate your own profile.", "warning")
        return redirect(url_for('user_listings', user_id=user.id))

    rating = int(request.form['rating'])

    # Check if the current user has already reviewed this user
    existing_review = Review.query.filter_by(reviewer_id=current_user.id, reviewed_id=user.id).first()
    if existing_review:
        flash("You have already rated this user.", "warning")
        return redirect(url_for('user_listings', user_id=user.id))

    # Create a new review
    review = Review(rating=rating, reviewer_id=current_user.id, reviewed_id=user.id)
    db.session.add(review)
    db.session.commit()
    flash("Rating submitted successfully!", "success")
    return redirect(url_for('user_listings', user_id=user.id))

@app.route('/listing/edit/<int:listing_id>', methods=['GET', 'POST'])
@login_required
def edit_listing(listing_id):
    listing = Resource.query.get_or_404(listing_id)

    # Ensure only the owner can edit the listing
    if listing.owner_id != current_user.id:
        flash("You are not authorized to edit this listing.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        listing.title = request.form['title']
        listing.description = request.form['description']
        listing.category = request.form['category']
        listing.availability = request.form['availability'] == 'True'

        # Handle image upload
        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                listing.image = os.path.join('uploads', filename)

        # Handle image removal
        if 'remove_image' in request.form and request.form['remove_image'] == 'True':
            listing.image = None

        db.session.commit()
        flash("Listing updated successfully!", "success")
        return redirect(url_for('dashboard'))

    return render_template('edit_listing.html', listing=listing)

@app.route('/listing/delete/<int:listing_id>', methods=['POST'])
@login_required
def delete_listing(listing_id):
    listing = Resource.query.get_or_404(listing_id)

    if listing.owner_id != current_user.id:
        flash("You cannot delete someone else's listing.", 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(listing)
    db.session.commit()
    flash("Listing deleted successfully!", 'success')
    return redirect(url_for('dashboard'))

@app.route('/user/<int:user_id>')
def user_listings(user_id):
    user = User.query.get_or_404(user_id)
    listings = Resource.query.filter_by(owner_id=user.id).order_by(Resource.date_posted.desc()).all()

    # Calculate the average rating for the user
    reviews = Review.query.filter_by(reviewed_id=user.id).all()
    if reviews:
        average_rating = round(sum(review.rating for review in reviews) / len(reviews), 2)
    else:
        average_rating = None

    return render_template('user_listings.html', user=user, listings=listings, average_rating=average_rating)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.email = request.form['email']

        # Handle profile picture upload
        profile_image = request.files.get('profile_image')
        if profile_image and allowed_file(profile_image.filename):
            filename = secure_filename(profile_image.filename)
            image_path = os.path.join(app.config['PROFILE_FOLDER'], filename)
            profile_image.save(image_path)
            # Normalize the path to use forward slashes
            current_user.profile_image = os.path.join('profile_pics', filename).replace('\\', '/')

        # Handle password change
        password = request.form['password']
        if password:
            current_user.password = generate_password_hash(password, method='pbkdf2:sha256')

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html')

@app.route('/message/delete/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    if message.receiver_id != current_user.id:
        flash("You cannot delete someone else's message.", 'danger')
        return redirect(url_for('inbox'))
    db.session.delete(message)
    db.session.commit()
    flash("Message deleted successfully!", 'success')
    return redirect(url_for('inbox'))

# Initialize DB
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
