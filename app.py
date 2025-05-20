from flask import Flask, render_template, request, redirect, url_for, flash
import threading
import sqlite3
from voice_auth import VoiceAuthApp
from database import init_db, save_user_data, get_user_data
import ttkbootstrap as ttk
import queue
import time

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Required for flash messages

# Initialize database
init_db()

# Global variables
voice_app = None
email_queue = queue.Queue()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/setup', methods=['POST'])
def setup():
    email = request.form.get('email')
    if not email:
        flash("Email is required", "error")
        return redirect(url_for('index'))
    email_queue.put(email)
    flash("Email submitted. Please check the Tkinter GUI for setup.", "success")
    voice_app.start_setup(email)
    return redirect(url_for('index'))

@app.route('/authenticate', methods=['POST'])
def authenticate():
    email = request.form.get('email')
    if not email:
        flash("Email is required", "error")
        return redirect(url_for('index'))
    email_queue.put(email)
    flash("Email submitted. Please check the Tkinter GUI for authentication.", "success")
    success = voice_app.start_authentication(email)
    if success:
        return redirect(url_for('success'))
    return redirect(url_for('index'))

@app.route('/success')
def success():
    return render_template('success.html')

def run_flask():
    app.run(debug=False, use_reloader=False, port=5000)

def run_tkinter():
    global voice_app
    root = ttk.Window(themename="darkly")
    voice_app = VoiceAuthApp(root, email_queue)
    root.mainloop()

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    tkinter_thread = threading.Thread(target=run_tkinter, daemon=True)
    flask_thread.start()
    tkinter_thread.start()
    flask_thread.join()
    tkinter_thread.join()