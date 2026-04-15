#!/usr/bin/env python3
"""
MEF Portal - Startup Script
Educational Flow Management System
"""

import os
import sys
from dotenv import load_dotenv

# Load .env file FIRST so DATABASE_URL is available before anything else
load_dotenv()

from app import create_app
from app.extensions import db

def check_dependencies():
    """Check if all required dependencies are installed"""
    required_packages = {
        'flask': 'flask',
        'flask-wtf': 'flask_wtf',
        'bleach': 'bleach',
        'flask-login': 'flask_login',
        'flask-sqlalchemy': 'flask_sqlalchemy'
    }
    missing_packages = []
    
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"Missing packages: {', '.join(missing_packages)}")
        print("Install them using: pip install -r requirements.txt")
        return False
    return True

def main():
    """Main startup function"""
    print("Starting MEF Portal...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Create App
    app = create_app()
    
    # Initialize database schemas if they don't exist
    print("Setting up SQLAlchemy schemas...")
    try:
        with app.app_context():
            db.create_all()
            print("Database setup complete.")
    except Exception as e:
        print(f"Database setup failed: {e}")
    
    # Run the Flask app
    try:
        print("MEF Portal is starting...")
        print("Access the portal at: http://localhost:5000")
        print("=" * 50)
        
        _debug = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
        app.run(
            host=os.getenv('FLASK_HOST', '0.0.0.0'),
            port=int(os.getenv('FLASK_PORT', 5000)),
            debug=_debug  # S-007 FIX: never hardcode True
        )
    except Exception as e:
        print(f"Failed to start the application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
