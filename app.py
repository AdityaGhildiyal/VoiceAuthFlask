from flask import Flask, render_template, request, redirect, url_for, flash
import threading
import sqlite3
from voice_auth import SetupWindow, AuthWindow
from database import init_db, save_user_data, get_user_data
import ttkbootstrap as ttk
import queue
import time
import logging

app = Flask(__name__)
app.secret_key = "your-secret-key"

# Setup logging for Flask
logging.basicConfig(filename="flask.log", level=logging.DEBUG)

# Initialize database
init_db()

# Global variables
email_queue = queue.Queue()
setup_app = None
auth_app = None
tkinter_lock = threading.Lock()

def run_tkinter_setup(email):
    global setup_app
    with tkinter_lock:
        try:
            root = ttk.Window(themename="darkly")
            setup_app = SetupWindow(root, email_queue)
            root.mainloop()
        except Exception as e:
            logging.error(f"Error in SetupWindow: {str(e)}")
            raise

def run_tkinter_auth(email):
    global auth_app
    with tkinter_lock:
        try:
            root = ttk.Window(themename="darkly")
            auth_app = AuthWindow(root, email_queue)
            root.mainloop()
            return auth_app.auth_result
        except Exception as e:
            logging.error(f"Error in AuthWindow: {str(e)}")
            raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/setup', methods=['POST'])
def setup():
    email = request.form.get('email')
    if not email:
        flash("Email is required", "error")
        return redirect(url_for('index'))
    
    # Clear queue to avoid stale emails
    while not email_queue.empty():
        try:
            email_queue.get_nowait()
        except queue.Empty:
            break
    
    email_queue.put(email)
    flash("Email submitted. Setup window opening...", "success")
    
    try:
        # Run Tkinter setup in a separate thread
        setup_thread = threading.Thread(target=run_tkinter_setup, args=(email,), daemon=True)
        setup_thread.start()
        setup_thread.join(timeout=60)  # Wait for setup to complete, max 60s
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Setup error: {str(e)}")
        flash("An error occurred during setup. Please try again.", "error")
        return redirect(url_for('index'))

@app.route('/authenticate', methods=['POST'])
def authenticate():
    email = request.form.get('email')
    if not email:
        flash("Email is required", "error")
        return redirect(url_for('index'))
    
    # Clear queue to avoid stale emails
    while not email_queue.empty():
        try:
            email_queue.get_nowait()
        except queue.Empty:
            break
    
    email_queue.put(email)
    flash("Email submitted. Authentication window opening...", "success")
    
    try:
        # Run Tkinter auth in a separate thread
        auth_thread = threading.Thread(target=run_tkinter_auth, args=(email,), daemon=True)
        auth_thread.start()
        auth_thread.join(timeout=60)  # Wait for auth to complete, max 60s
        
        # Check auth result
        global auth_app
        if auth_app and auth_app.auth_result:
            return redirect(url_for('success'))
        return redirect(url_for('failure'))
    except Exception as e:
        logging.error(f"Authentication error: {str(e)}")
        flash("An error occurred during authentication. Please try again.", "error")
        return redirect(url_for('index'))

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/failure')
def failure():
    return render_template('failure.html')

def run_flask():
    app.run(debug=True, use_reloader=False, port=5000)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    flask_thread.join()