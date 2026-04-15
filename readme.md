# MEF Portal - Educational Flow Management System

A Flask-based web application for managing student leave requests and mentor approvals.

## Features

- Student registration and login
- Leave request submission
- Mentor approval workflow
- PDF generation for approved requests
- Dashboard with request statistics
- Status tracking for all requests

## Prerequisites

- Python 3.7 or higher
- MySQL Server 5.7 or higher
- pip (Python package installer)

## Installation

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd "multigate eduflow portal"
   ```

2. **Create and activate virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate.bat
   
   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database**
   
   Edit `config.py` to match your MySQL settings:
   ```python
   DB_HOST = 'localhost'
   DB_USER = 'your_mysql_username'
   DB_PASSWORD = 'your_mysql_password'
   DB_NAME = 'mefportal'
   ```

5. **Start MySQL server**
   
   Make sure your MySQL server is running and accessible.

## Running the Application

### Option 1: Using the startup script (Recommended)
```bash
python run.py
```

### Option 2: Direct execution
```bash
python app.py
```

The application will be available at: http://127.0.0.1:5000

## Database Setup

The application will automatically create the required database and tables on first run. If you encounter database issues:

1. **Manual database creation:**
   ```sql
   CREATE DATABASE mefportal;
   USE mefportal;
   ```

2. **Check MySQL user permissions:**
   ```sql
   GRANT ALL PRIVILEGES ON mefportal.* TO 'your_username'@'localhost';
   FLUSH PRIVILEGES;
   ```

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Ensure MySQL server is running
   - Check credentials in `config.py`
   - Verify database exists and user has permissions

2. **Missing Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Port Already in Use**
   - Change port in `config.py`
   - Or kill the process using the port

4. **Template Errors**
   - Ensure all template files are present in `templates/` directory
   - Check for syntax errors in HTML files

### Testing Routes

- **Flask Test**: http://127.0.0.1:5000/test
- **Database Test**: http://127.0.0.1:5000/test-db
- **Debug Users**: http://127.0.0.1:5000/debug-users

## Project Structure

```
multigate eduflow portal/
├── app.py              # Main Flask application
├── config.py           # Configuration settings
├── run.py              # Startup script
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── static/            # Static files (CSS, images)
├── templates/         # HTML templates
└── instance/          # Database files (SQLite fallback)
```

## Configuration

### Environment Variables

You can override default settings using environment variables:

```bash
export DB_HOST=localhost
export DB_USER=your_username
export DB_PASSWORD=your_password
export DB_NAME=mefportal
export FLASK_DEBUG=True
```

### Database Configuration

The application supports MySQL as the primary database. The database schema includes:

- **users table**: User accounts and profiles
- **requests table**: Leave requests and approvals

## Security Notes

- Change the default secret key in production
- Use environment variables for sensitive data
- Ensure proper MySQL user permissions
- Enable HTTPS in production

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Verify all prerequisites are met
3. Check the application logs for error messages

## License

This project is for educational purposes.
