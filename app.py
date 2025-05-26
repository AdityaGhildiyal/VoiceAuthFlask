from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import threading
import sqlite3
from voice_auth import UnifiedVoiceWindow
from database import init_db, save_user_data, get_user_data
import ttkbootstrap as ttk
import queue
import time
import logging
import uuid
import atexit
from threading import Lock, Event

app = Flask(__name__)
app.secret_key = "your-secret-key"

# Setup logging for Flask
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("flask.log"),
        logging.StreamHandler()
    ]
)

# Initialize database
init_db()

class VoiceAppManager:
    def __init__(self):
        self.voice_window = None
        self.tkinter_thread = None
        self.operation_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.lock = Lock()
        self.running = False
        
    def start_tkinter_window(self):
        """Start the unified Tkinter window in a separate thread"""
        if self.running:
            return
            
        def run_tkinter():
            try:
                self.running = True
                root = ttk.Window(themename="darkly")
                self.voice_window = UnifiedVoiceWindow(
                    root, 
                    self.operation_queue, 
                    self.result_queue
                )
                
                # Set up window close callback
                def on_closing():
                    logging.info("Tkinter window closing")
                    self.running = False
                    root.quit()
                
                root.protocol("WM_DELETE_WINDOW", on_closing)
                root.mainloop()
                
            except Exception as e:
                logging.error(f"Error in Tkinter thread: {e}")
            finally:
                self.running = False
                
        self.tkinter_thread = threading.Thread(target=run_tkinter, daemon=True)
        self.tkinter_thread.start()
        
        # Wait a moment for window to initialize
        time.sleep(1)
        
    def send_operation(self, operation_type, email):
        """Send operation to Tkinter window"""
        if not self.running:
            return False
            
        operation_id = str(uuid.uuid4())
        operation = {
            'id': operation_id,
            'type': operation_type,
            'email': email,
            'timestamp': time.time()
        }
        
        try:
            self.operation_queue.put(operation, timeout=1)
            return operation_id
        except queue.Full:
            logging.error("Operation queue is full")
            return None
            
    def get_result(self, operation_id, timeout=1):
        """Get result from Tkinter window"""
        try:
            while True:
                result = self.result_queue.get(timeout=timeout)
                if result['operation_id'] == operation_id:
                    return result
                # Put back if not our result
                self.result_queue.put(result)
        except queue.Empty:
            return None
            
    def check_status(self):
        """Check if Tkinter window is running"""
        return self.running
        
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.voice_window and hasattr(self.voice_window, 'root'):
            try:
                self.voice_window.root.quit()
            except:
                pass

# Global manager instance
voice_manager = VoiceAppManager()

def cleanup_on_exit():
    """Clean up on application exit"""
    logging.info("Cleaning up on exit...")
    voice_manager.cleanup()

# Register cleanup function
atexit.register(cleanup_on_exit)

@app.route('/')
def index():
    # Start Tkinter window if not running
    if not voice_manager.check_status():
        voice_manager.start_tkinter_window()
        
    return render_template('index.html')

@app.route('/setup', methods=['POST'])
def setup():
    email = request.form.get('email')
    if not email:
        flash("Email is required", "error")
        return redirect(url_for('index'))
    
    # Ensure Tkinter window is running
    if not voice_manager.check_status():
        voice_manager.start_tkinter_window()
        time.sleep(1)  # Give it time to start
        
    if not voice_manager.check_status():
        flash("Voice interface is not available. Please try again.", "error")
        return redirect(url_for('index'))
    
    # Send setup operation to Tkinter window
    operation_id = voice_manager.send_operation('setup', email)
    if not operation_id:
        flash("Failed to start setup. Please try again.", "error")
        return redirect(url_for('index'))
    
    # Store operation details in session
    session['operation_id'] = operation_id
    session['email'] = email
    session['operation'] = 'setup'
    session['start_time'] = time.time()
    
    flash("Setup operation sent to voice interface. Please check the voice window to complete setup.", "info")
    return redirect(url_for('status'))

@app.route('/authenticate', methods=['POST'])
def authenticate():
    email = request.form.get('email')
    if not email:
        flash("Email is required", "error")
        return redirect(url_for('index'))
    
    # Check if user exists in database
    user_data = get_user_data(email)
    if not user_data:
        flash("No voice data found for this email. Please setup your voice first.", "error")
        return redirect(url_for('index'))
    
    # Ensure Tkinter window is running
    if not voice_manager.check_status():
        voice_manager.start_tkinter_window()
        time.sleep(1)  # Give it time to start
        
    if not voice_manager.check_status():
        flash("Voice interface is not available. Please try again.", "error")
        return redirect(url_for('index'))
    
    # Send authentication operation to Tkinter window
    operation_id = voice_manager.send_operation('authenticate', email)
    if not operation_id:
        flash("Failed to start authentication. Please try again.", "error")
        return redirect(url_for('index'))
    
    # Store operation details in session
    session['operation_id'] = operation_id
    session['email'] = email
    session['operation'] = 'authenticate'
    session['start_time'] = time.time()
    
    flash("Authentication operation sent to voice interface. Please check the voice window to complete authentication.", "info")
    return redirect(url_for('status'))

@app.route('/status')
def status():
    """Status page to check operation progress"""
    operation_id = session.get('operation_id')
    email = session.get('email')
    operation = session.get('operation')
    start_time = session.get('start_time')
    
    if not operation_id or not email or not operation:
        flash("No active operation found.", "error")
        return redirect(url_for('index'))
    
    # Check for timeout (5 minutes)
    if start_time and (time.time() - start_time) > 300:
        session.clear()
        flash("Operation timed out. Please try again.", "error")
        return redirect(url_for('index'))
    
    # Check for results
    result = voice_manager.get_result(operation_id, timeout=0.1)
    if result:
        session.clear()  # Clear session data
        
        if result['status'] == 'success':
            if operation == 'setup':
                flash("Voice setup completed successfully!", "success")
                return redirect(url_for('index'))
            elif operation == 'authenticate':
                if result.get('authenticated', False):
                    return redirect(url_for('success'))
                else:
                    return redirect(url_for('failure'))
        elif result['status'] == 'error':
            flash(f"Operation failed: {result.get('message', 'Unknown error')}", "error")
            return redirect(url_for('index'))
        elif result['status'] == 'cancelled':
            flash("Operation was cancelled.", "error")
            return redirect(url_for('index'))
    
    # Still in progress
    return render_template('status.html', 
                         email=email, 
                         operation=operation, 
                         status='in_progress')

@app.route('/help')
def help():
    """Help and support page"""
    return render_template('help.html')

@app.route('/check_status')
def check_status():
    """AJAX endpoint to check operation status"""
    operation_id = session.get('operation_id')
    if not operation_id:
        return jsonify({'status': 'no_operation'})
    
    result = voice_manager.get_result(operation_id, timeout=0.1)
    if result:
        return jsonify(result)
    
    return jsonify({'status': 'in_progress'})

@app.route('/cancel')
def cancel():
    """Cancel current operation"""
    operation_id = session.get('operation_id')
    if operation_id:
        # Send cancel operation
        voice_manager.send_operation('cancel', '')
        session.clear()
        flash("Operation cancelled.", "info")
    return redirect(url_for('index'))

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/failure')
def failure():
    return render_template('failure.html')

@app.route('/restart_voice_window')
def restart_voice_window():
    """Restart the voice window if it's not responding"""
    voice_manager.cleanup()
    time.sleep(1)
    voice_manager.start_tkinter_window()
    flash("Voice interface restarted.", "info")
    return redirect(url_for('index'))

def run_flask():
    app.run(debug=True, use_reloader=False, port=5000, threaded=True)

if __name__ == "__main__":
    try:
        # Start Tkinter window first
        voice_manager.start_tkinter_window()
        
        # Start Flask
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        flask_thread.join()
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
    finally:
        cleanup_on_exit()