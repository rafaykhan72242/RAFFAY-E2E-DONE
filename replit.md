# Overview

This is a multi-user Python automation application created by **Prince Malhotra** that uses Selenium WebDriver to perform browser-based **Facebook Group Name & Nickname Lock System**. The application features a beautiful web interface with secure user authentication and individual user configurations.

**Key Features:**
- Multi-user authentication system with signup/login
- Beautiful gradient UI with modern design
- User-specific configuration storage
- Encrypted cookie storage for privacy
- **Group Name Lock** - Automatically reverts any changes to the locked group name
- **Nickname Lock** - Automatically reverts any changes to member nicknames (planned feature)
- Real-time monitoring and logging
- **Persistent lock state** - Auto-resumes monitoring after Streamlit restart
- **Duplicate thread prevention** - Ensures single monitoring instance per user

# User Preferences

Preferred communication style: Simple, everyday language (Hindi/English mix).

# System Architecture

## Core Application Structure

### Streamlit Web App (streamlit_app.py)
- **Beautiful Multi-User Interface** with gradient design and Poppins font
- **Authentication System**: Secure signup/login with SHA-256 password hashing
- **User Dashboard**: Personal lock configuration management
- **Live Lock System Control**: Start/stop monitoring with real-time logs
- **Group Name Lock**: Automatically detect and revert group name changes
- **Nickname Management**: Add/remove locked nicknames for group members
- **Prince Malhotra Branding**: Throughout the application with lock emoji 🔒

### Database Layer (database.py)
- **SQLite Database**: Stores user accounts and lock configurations
- **Secure Password Hashing**: Uses SHA-256 for password security
- **Cookie Encryption**: Fernet encryption for Facebook cookies
- **Lock Configuration Storage**: Stores locked group name and member nicknames (JSON)
- **User Isolation**: Each user's data is completely separate and private

## Security Architecture

### Password Security
- **SHA-256 Hashing**: All passwords are hashed with SHA-256
- **Secure Verification**: Password verification uses hash comparison
- **No Plain Text**: Passwords are never stored in plain text

### Cookie Privacy
- **Fernet Encryption**: Facebook cookies are encrypted before storage
- **Never Displayed**: Cookies are never shown in the UI after saving
- **Per-User Storage**: Each user's cookies are stored separately and securely

### User Isolation
- **Database Foreign Keys**: User configs are linked to user IDs
- **Session Management**: Streamlit session state tracks logged-in users
- **No Data Leakage**: Users can only see their own configurations

## User Flow

1. **New User Signup**:
   - User creates account with username and password
   - System creates encrypted user record with SHA-256
   - Empty lock configuration is initialized for the user
   - User sees blank configuration interface

2. **Login**:
   - User enters credentials
   - System verifies with hash comparison
   - User's saved lock configuration is loaded
   - Cookies remain encrypted and hidden

3. **Lock Configuration**:
   - Group/Conversation ID (Facebook group ID from URL)
   - Locked Group Name (the desired group name to maintain)
   - Facebook Cookies (required for authentication, encrypted storage)
   - Locked Nicknames (member ID → nickname mapping in JSON)

4. **Lock System**:
   - Start lock monitoring with saved config
   - Browser opens in headless mode
   - System continuously monitors group name
   - Automatically reverts any changes to group name
   - Logs appear in real-time
   - Runs until manually stopped
   - Lock state persists in database
   - Auto-resumes after Streamlit restart
   - Logout automatically stops lock system

## Browser Automation Framework

Uses Selenium WebDriver with Chrome driver for browser automation:
- **Headless Chrome**: Runs without visible browser window
- **Cookie Injection**: Adds Facebook cookies for authentication
- **Message Input Detection**: Advanced selectors to find message box
- **Message Rotation**: Cycles through user's message list
- **Real-time Logging**: Shows progress and errors

## Data Flow Architecture

1. User logs in → SHA-256 verifies password
2. User lock config loads from SQLite → cookies decrypted
3. **Auto-start check**: If lock_enabled=1 in DB, resume lock monitoring
4. User starts lock system → config passed to monitoring thread
5. Selenium opens Facebook → injects cookies → navigates to group
6. Continuously checks group name → compares with locked value
7. If changed → opens group settings → reverts group name
8. Real-time logs update UI → user sees progress
9. Lock system runs until user clicks stop or logs out
10. **Streamlit restart**: On app reload, lock system auto-resumes for users
11. **Thread safety**: Duplicate prevention ensures only one thread per user

## UI/UX Design

### Design Elements
- **Gradient Backgrounds**: Purple-blue gradients (#667eea to #764ba2)
- **Modern Typography**: Poppins font family
- **Smooth Animations**: Hover effects and transitions
- **Rounded Corners**: 10-15px border radius throughout
- **Box Shadows**: Elevated card designs
- **Responsive Layout**: Wide layout with proper spacing

### Color Scheme
- Primary: Purple-blue gradient
- Success: Green gradient
- Error: Pink-yellow gradient
- Background: Light gray gradient for cards
- Text: Dark for readability
- Logs: Terminal-style dark background with green text

### Branding
- **Prince Malhotra** name in header and footer
- Lock emoji 🔒 as favicon and in header
- "Auto-Revert Group Name & Nicknames" tagline
- Copyright footer with ❤️

# External Dependencies

## Core Runtime Dependencies
- **Python 3.11**: Python runtime environment
- **Streamlit**: Web UI framework for the interface
- **Selenium**: Browser automation framework
- **bcrypt**: Secure password hashing
- **cryptography**: Fernet encryption for cookies
- **SQLite3**: Built-in database (no external DB needed)

## System Dependencies (for Cloud Deployment)
- **Chromium**: Headless browser for automation
- **Chromium-driver**: Browser driver for Selenium

## Deployment Files
- **requirements.txt**: Python package dependencies
- **packages.txt**: System packages for Streamlit Cloud

## Database Files
- **users.db**: SQLite database (auto-created)
- **.encryption_key**: Fernet key for cookie encryption (auto-generated)

## Security Implementation
- SHA-256 for password hashing
- Fernet symmetric encryption for cookie storage
- Session-based authentication via Streamlit session state
- No passwords or cookies ever exposed in UI or logs
- User isolation prevents cross-user data access
