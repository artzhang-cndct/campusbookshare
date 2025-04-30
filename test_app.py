import unittest
from app import app, db, User, Resource, Message, Review
from flask import url_for
from werkzeug.security import generate_password_hash

class CampusBookshareTestCase(unittest.TestCase):
    def setUp(self):
        # Configure the app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # In-memory database
        self.app = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()

        # Create a test user
        self.test_user = User(
            name="Test User",
            email="test@example.com",
            password=generate_password_hash("password", method='pbkdf2:sha256'),
            location="Test Location"
        )
        db.session.add(self.test_user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_user_registration(self):
        response = self.app.post('/register', data={
            'name': 'New User',
            'email': 'newuser@example.com',
            'password': 'password',
            'location': 'New Location'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after successful registration
        user = User.query.filter_by(email='newuser@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'New User')

    def test_invalid_registration(self):
        response = self.app.post('/register', data={
            'name': '',
            'email': 'invalidemail',
            'password': '',
            'location': ''
        })
        self.assertEqual(response.status_code, 200)  # Should not redirect
        self.assertIn(b'All fields are required.', response.data)  # Error message

    def test_user_login(self):
        response = self.app.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after successful login

    def test_invalid_login(self):
        response = self.app.post('/login', data={
            'email': 'nonexistent@example.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)  # Should not redirect
        self.assertIn(b'Login failed. Check your email and password.', response.data)  # Error message

    def test_create_listing(self):
        with self.app:
            self.app.post('/login', data={
                'email': 'test@example.com',
                'password': 'password'
            })
            response = self.app.post('/create_listing', data={
                'title': 'Test Listing',
                'description': 'This is a test listing.',
                'category': 'Books',
                'availability': 'True'
            })
            self.assertEqual(response.status_code, 302)  # Redirect after successful creation
            listing = Resource.query.filter_by(title='Test Listing').first()
            self.assertIsNotNone(listing)
            self.assertEqual(listing.description, 'This is a test listing.')

    def test_send_message(self):
        with self.app:
            self.app.post('/login', data={
                'email': 'test@example.com',
                'password': 'password'
            })
            new_user = User(
                name="Receiver User",
                email="receiver@example.com",
                password=generate_password_hash("password", method='pbkdf2:sha256'),
                location="Receiver Location"
            )
            db.session.add(new_user)
            db.session.commit()

            response = self.app.post(f'/messages?receiver_id={new_user.id}', data={
                'content': 'Hello, this is a test message.'
            })
            self.assertEqual(response.status_code, 302)  # Redirect after sending the message
            message = Message.query.filter_by(content='Hello, this is a test message.').first()
            self.assertIsNotNone(message)
            self.assertEqual(message.receiver_id, new_user.id)
    
    def test_add_review(self):
        with self.app:
            self.app.post('/login', data={
                'email': 'test@example.com',
                'password': 'password'
            })
            new_user = User(
                name="Reviewed User",
                email="reviewed@example.com",
                password=generate_password_hash("password", method='pbkdf2:sha256'),
                location="Reviewed Location"
            )
            db.session.add(new_user)
            db.session.commit()

            response = self.app.post(f'/review/{new_user.id}', data={
                'rating': 5
            })
            self.assertEqual(response.status_code, 302)  # Redirect after adding the review
            review = Review.query.filter_by(reviewer_id=self.test_user.id, reviewed_id=new_user.id).first()
            self.assertIsNotNone(review)
            self.assertEqual(review.rating, 5)

    def test_invalid_review_submission(self):
        with self.app:
            self.app.post('/login', data={
                'email': 'test@example.com',
                'password': 'password'
            })
            new_user = User(
                name="Reviewed User",
                email="reviewed@example.com",
                password=generate_password_hash("password", method='pbkdf2:sha256'),
                location="Reviewed Location"
            )
            db.session.add(new_user)
            db.session.commit()

            response = self.app.post(f'/review/{new_user.id}', data={
                'rating': 10  # Invalid rating
            })
            self.assertEqual(response.status_code, 200)  # Should not redirect
            self.assertIn(b'Rating must be between 1 and 5.', response.data)  # Error message

    def test_search_functionality(self):
        with self.app:
            self.app.post('/login', data={
                'email': 'test@example.com',
                'password': 'password'
            })
            # Create a listing
            self.app.post('/create_listing', data={
                'title': 'Searchable Listing',
                'description': 'This listing is for testing search functionality.',
                'category': 'Books',
                'availability': 'True'
            })

            response = self.app.get('/search?query=Searchable')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Searchable Listing', response.data)

    def test_messaging_interface(self):
        with self.app:
            self.app.post('/login', data={
                'email': 'test@example.com',
                'password': 'password'
            })
            new_user = User(
                name="Receiver User",
                email="receiver@example.com",
                password=generate_password_hash("password", method='pbkdf2:sha256'),
                location="Receiver Location"
            )
            db.session.add(new_user)
            db.session.commit()

            # Send a message
            self.app.post(f'/messages?receiver_id={new_user.id}', data={
                'content': 'Test message for messaging interface.'
            })

            # Access the messaging interface
            response = self.app.get(f'/messages?receiver_id={new_user.id}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Test message for messaging interface.', response.data)

    def test_user_dashboard(self):
        with self.app:
            self.app.post('/login', data={
                'email': 'test@example.com',
                'password': 'password'
            })
            response = self.app.get('/dashboard')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Test User', response.data)

    def test_full_workflow_listing_creation(self):
        # Register a new user
        self.app.post('/register', data={
            'name': 'Workflow User',
            'email': 'workflow@example.com',
            'password': 'password',
            'location': 'Workflow Location'
        })

        # Log in as the new user
        self.app.post('/login', data={
            'email': 'workflow@example.com',
            'password': 'password'
        })

        # Create a listing
        response = self.app.post('/create_listing', data={
            'title': 'Workflow Listing',
            'description': 'This is a workflow test listing.',
            'category': 'Books',
            'availability': 'True'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after creation

        # Verify the listing appears on the homepage
        response = self.app.get('/')
        self.assertIn(b'Workflow Listing', response.data)

    def test_full_messaging_workflow(self):
        # Create a second user
        new_user = User(
            name="Second User",
            email="seconduser@example.com",
            password=generate_password_hash("password", method='pbkdf2:sha256'),
            location="Second Location"
        )
        db.session.add(new_user)
        db.session.commit()

        # Log in as the first user
        self.app.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })

        # Send a message to the second user
        response = self.app.post(f'/messages?receiver_id={new_user.id}', data={
            'content': 'Hello, Second User!'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after sending

        # Log in as the second user
        self.app.post('/login', data={
            'email': 'seconduser@example.com',
            'password': 'password'
        })

        # Reply to the first user
        response = self.app.post(f'/messages?receiver_id={self.test_user.id}', data={
            'content': 'Hello, Test User!'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after replying

        # Verify the conversation
        response = self.app.get(f'/messages?receiver_id={self.test_user.id}')
        self.assertIn(b'Hello, Test User!', response.data)
        self.assertIn(b'Hello, Second User!', response.data)

    def test_user_browsing_listings(self):
        # Create a listing
        self.app.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })
        self.app.post('/create_listing', data={
            'title': 'Browsing Test Listing',
            'description': 'This listing is for browsing tests.',
            'category': 'Books',
            'availability': 'True'
        })

        # Log out and browse as a guest
        self.app.get('/logout')
        response = self.app.get('/')
        self.assertIn(b'Browsing Test Listing', response.data)

    def test_user_profile_update(self):
        with self.app:
            self.app.post('/login', data={
                'email': 'test@example.com',
                'password': 'password'
            })

            # Update profile
            response = self.app.post('/profile', data={
                'name': 'Updated User',
                'email': 'updated@example.com',
                'location': 'Updated Location',
                'password': ''
            })
            self.assertEqual(response.status_code, 302)  # Redirect after update

            # Verify the update
            user = User.query.filter_by(email='updated@example.com').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.name, 'Updated User')
            self.assertEqual(user.location, 'Updated Location')

if __name__ == '__main__':
    loader = unittest.TestLoader()
    tests = loader.loadTestsFromTestCase(CampusBookshareTestCase)
    print(f"Discovered tests: {[test.id() for test in tests]}")
    unittest.main()