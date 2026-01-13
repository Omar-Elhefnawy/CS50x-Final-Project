# Smart Desk Monitor
#### Video Demo:  https://youtu.be/uHJhfDd_hNk
#### Description:

## Overview
I was interested in integrating some electronics with some programming to make this project. While the technology these days is focusing on making anything smart, I came up with the idea of making the desk smart, and let's call this a **Smart Desk Monitor**. This project will be two parts: hardware and software. The hardware is responsible for sensing and ringing, while the software will be responsible for counting and saving. 

I will use an ultrasonic sensor, an LED, and a buzzer connected to Arduino Uno R3 and connected to the pc using a USB cable, and that is all for the hardware. I will be using Arduino IDE for hardware programming and Python, HTML, CSS, Flask, and JavaScript in making the website. The ultrasonic sensor should be placed on the desk and detect whether the user is working or not, if he isn't sitting at the working desk. In case he is working, an LED is expected to light up. If a user sits for an entire hour, the buzzer will notify him to take a break. The website will also be working on collecting data from the Arduino and saving the work session's date and duration into this user's profile.

The project addresses the modern need for productivity monitoring while promoting healthy work habits. By integrating hardware (Arduino and sensor) with a web dashboard, it offers real-time insights and historical data analysis. The login system ensures privacy, making it suitable for multi-user environments. The system's simplicity, cost-effectiveness (no Wi-Fi modules required), and focus on user well-being make it a standout CS50 project.

## File Descriptions

### `main.py`
This is the core Python script that orchestrates the Smart Desk Monitor. It uses Flask to serve the web application, `pyserial` for Arduino communication, and `sqlite3` for database operations. The script:
- Initialize Flask app, secret key, and Flask Login.
- Define the User class and the user loader to load users from the sqlite data base.
- init_db(): create users and sessions tables (and seed an admin user).
- sync_db_to_memory(user_id): load sessions for a user from the db into the in-memory work_sessions list and claim unassigned sessions for the logged-in user.
- /register, /login, /logout: user registration and authentication.
- / : index page — syncs db to memory and renders sessions and total hours.
- /timer: returns current session status and elapsed seconds.
- /debug_session: manual start/stop for debugging (persists a session to the db).
- /delete_session: delete a session that belongs to the current user.
- Maintains current_session_start and work_sessions (in-memory list of (id, start, end) tuples).
- Computes total hours for display on the index page.
- find_arduino_port() and open_serial(port): detect Arduino port and open serial connection.
- read_serial(): background thread that reads serial lines, parses PRESENCE messages, starts/stops in-memory sessions, and persists completed sessions to the db (stores user_id NULL for sensor-created sessions).
- Starts a daemon thread to run read_serial() if an Arduino port is found.
- Uses Locks (ser_lock, session_lock) to protect serial and session state.
- Runs the Flask development server when executed as main.
- signal_handler to close serial and exit.
  
### `index.html`
The main dashboard template, rendered when a user is logged in, displays:
- The logged-in user's name and a logout link.
- Total work hours calculated from session data.
- A real-time session status ("Working" or "Not Working") updated via JavaScript fetching the `/timer` endpoint.
- Tables listing work sessions (start time, end time, duration, delete session button).
For unauthenticated users, it shows a login/register prompt.

### `login.html`
This template provides a login form with fields for username and password. It displays error messages and includes a link to the registration page. The form submits to the `/login` route, which verifies credentials against the database.

### `register.html`
This template offers a registration form for new users, requiring a username and password. It submits to the `/register` route, which hashes the password and stores the user in the database. Errors (eg, "Username already exists") are displayed, and a link to the login page is provided.

### `data.db`
The sqlite database (auto-created by `main.py`) stores:
- `users`: User IDs, usernames, and hashed passwords.
- `sessions`: User-specific work sessions (start/end times) and reminders (time, message).

### `styles.css`
This is where I design the site (eg, fonts, colors, alignments)

## Design Choices

Several design decisions shaped the project to balance functionality, simplicity, and CS50 requirements:
- **Hardware Choice (Arduino Uno R3)**: Actually, Arduino Uno is easy to use, and there are a lot of online tutorials teaching how to integrate Python and Arduino.
- **SQLite3**: I gained a basic knowledge of how to use it from CS50's lecture, so this was an easy choice when it comes to the database.
- **Login System**: A username/password login with `werkzeug.security` was implemented for security and user-specific data tracking. Indeed, because we used it before in the hardest problem set in CS50, finance, Flask's `session` was used for simplicity over authentication. Password hashing ensures basic security; however, a production system would require a stronger secret key and HTTPS.
- **Threading for Serial Communication**: A dedicated thread reads Arduino data to prevent blocking the Flask server. Thread locks (`ser_lock`, `data_lock`) ensure safe access to shared resources, addressing potential race conditions in a multi-threaded environment.
- **Web Interface**: The Flask templates use minimal CSS for a clean, functional UI. JavaScript updates the timer dynamically, enhancing user experience without requiring a full frontend framework like React, which would exceed the project's scope.
- **Bootstrap**: Bootstrap helped in customizing the table so that the table looks dark and shines on hovering.
- **Error Handling**: Robust error handling (e.g., serial port retries, database integrity checks) ensures reliability. For instance, the port detection logic retries connections and falls back to manual input, addressing issues like the COM5 permission error you encountered.

## Setup and Usage
1. **Requirements**: Install Python dependencies (`pip install flask pyserial werkzeug`).
2. **Hardware**: Connect an Arduino Uno with an HC-SR04 sensor (trig to pin 9, echo to pin 10, vcc to 5v, gnd to gnd). Connect the buzzer to pin 8. Connect the LED to pin 13. Upload `Arduino-Setup.ino` sketch to Arduino Uno
3. **Run**: type (`python main.py`) in the terminal.
4. **Register/Login**: Create an account via `/register`, then log in at `/login`.
5. **Monitor**: View work sessions, last 7 days' sessions, and real-time status on the dashboard.

## AI
1. Gork -> Tutorial suggestions about how Python can collect the data from the sensors connected to the Arduino.
2. GitHub Copilot Chat -> bug fix and spot code errors.
3. Grammarly -> fix punctuation and grammar mistakes.


## Future Enhancements
Future iterations could include gamification (e.g., streaks for consistent work), email/SMS reminders, or a mobile app interface.

This project reflects my passion for blending hardware and software to solve real-world problems, making it a proud addition to my CS50 portfolio and resume.