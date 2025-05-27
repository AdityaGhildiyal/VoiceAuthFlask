import os
import numpy as np
import librosa
import speech_recognition as sr
import cv2
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
import soundfile as sf
from fuzzywuzzy import fuzz
from cryptography.fernet import Fernet
from datetime import datetime
import logging
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from tkinter import messagebox
import threading
import time
import queue
from database import save_user_data, get_user_data

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("auth.log"),
        logging.StreamHandler()
    ]
)

class UnifiedVoiceWindow:
    def __init__(self, root, operation_queue, result_queue):
        self.root = root
        self.operation_queue = operation_queue
        self.result_queue = result_queue
        
        # Window setup
        self.root.title("Voice Authentication System")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # Current operation tracking
        self.current_operation = None
        self.current_email = None
        self.running_operation = False
        
        # Voice recognition
        self.recognizer = sr.Recognizer()
        
        # Authentication state
        self.auth_attempts = 0
        self.max_attempts = 3
        self.audio_samples = {'auth_voice': None, 'auth_phrase': None}
        
        # Initialize GUI
        self.setup_gui()
        
        # Start operation monitor
        self.monitor_operations()
        
    def setup_gui(self):
        """Setup the GUI elements"""
        # Title
        self.title_label = ttk.Label(
            self.root, 
            text="Voice Authentication System", 
            font=("Arial", 20, "bold"), 
            bootstyle="primary"
        )
        self.title_label.pack(pady=15)
        
        # Status frame
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=X, padx=20, pady=5)
        
        ttk.Label(status_frame, text="Current Operation:", font=("Arial", 12, "bold")).pack(anchor=W)
        self.operation_label = ttk.Label(status_frame, text="Waiting for operations...", font=("Arial", 12))
        self.operation_label.pack(anchor=W)
        
        ttk.Label(status_frame, text="Email:", font=("Arial", 12, "bold")).pack(anchor=W, pady=(10,0))
        self.email_label = ttk.Label(status_frame, text="None", font=("Arial", 12))
        self.email_label.pack(anchor=W)
        
        # Instructions
        self.instructions_frame = ttk.LabelFrame(self.root, text="Instructions", padding=10)
        self.instructions_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
        
        self.instructions_text = ScrolledText(
            self.instructions_frame, 
            height=12, 
            width=70, 
            font=("Arial", 10), 
            wrap="word",
            bootstyle="dark"
        )
        self.instructions_text.pack(fill=BOTH, expand=True)
        
        # Make text read-only
        self.instructions_text.text.bind("<Key>", lambda e: "break")
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self.root, 
            bootstyle="primary", 
            mode="determinate", 
            length=400
        )
        
        # Control buttons frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=X, padx=20, pady=10)
        
        self.start_button = ttk.Button(
            control_frame, 
            text="Start Operation", 
            command=self.start_current_operation,
            bootstyle="success",
            width=15
        )
        self.start_button.pack(side=LEFT, padx=5)
        
        self.cancel_button = ttk.Button(
            control_frame, 
            text="Cancel", 
            command=self.cancel_operation,
            bootstyle="danger",
            width=15
        )
        self.cancel_button.pack(side=LEFT, padx=5)
        
        self.clear_button = ttk.Button(
            control_frame, 
            text="Clear Messages", 
            command=self.clear_messages,
            bootstyle="secondary",
            width=15
        )
        self.clear_button.pack(side=LEFT, padx=5)
        
        # Initial state
        self.start_button.config(state='disabled')
        self.cancel_button.config(state='disabled')
        
        # Add initial message
        self.log_message("Voice Authentication System Ready")
        self.log_message("Waiting for operations from web interface...")
        self.log_message("=" * 50)
        
    def monitor_operations(self):
        """Monitor for incoming operations"""
        try:
            operation = self.operation_queue.get_nowait()
            self.handle_new_operation(operation)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.monitor_operations)
        
    def handle_new_operation(self, operation):
        """Handle new operation from Flask"""
        operation_type = operation['type']
        email = operation['email']
        operation_id = operation['id']
        
        if operation_type == 'cancel':
            self.cancel_operation()
            return
            
        if self.running_operation:
            result = {
                'operation_id': operation_id,
                'status': 'error',
                'message': 'Another operation is already in progress'
            }
            self.result_queue.put(result)
            return
            
        # Set up new operation
        self.current_operation = {
            'type': operation_type,
            'email': email,
            'id': operation_id
        }
        
        self.current_email = email
        self.operation_label.config(text=f"{operation_type.title()} Operation")
        self.email_label.config(text=email)
        
        if operation_type == 'setup':
            self.setup_setup_operation()
        elif operation_type == 'authenticate':
            self.setup_auth_operation()
            
        self.start_button.config(state='normal')
        self.cancel_button.config(state='normal')
        
    def setup_setup_operation(self):
        """Setup GUI for setup operation"""
        self.clear_messages()
        self.log_message("=== VOICE SETUP OPERATION ===")
        self.log_message(f"Email: {self.current_email}")
        self.log_message("")
        self.log_message("This process will:")
        self.log_message("1. Record two voice samples for voice recognition")
        self.log_message("2. Record your secret unlock phrase")
        self.log_message("3. Save encrypted voice data to database")
        self.log_message("")
        self.log_message("Click 'Start Operation' when ready to begin.")
        self.log_message("Make sure you're in a quiet environment with a working microphone.")
        
    def setup_auth_operation(self):
        """Setup GUI for authentication operation"""
        self.clear_messages()
        self.log_message("=== VOICE AUTHENTICATION OPERATION ===")
        self.log_message(f"Email: {self.current_email}")
        self.log_message("")
        self.log_message("This process will:")
        self.log_message("1. Record your voice for verification")
        self.log_message("2. Ask you to speak your unlock phrase")
        self.log_message("3. Compare with stored voice data")
        self.log_message("")
        self.log_message(f"You have {self.max_attempts} attempts for authentication.")
        self.log_message("Click 'Start Operation' when ready to begin.")
        
    def start_current_operation(self):
        """Start the current operation"""
        if not self.current_operation or self.running_operation:
            return
            
        self.running_operation = True
        self.start_button.config(state='disabled')
        
        if self.current_operation['type'] == 'setup':
            threading.Thread(target=self.run_setup, daemon=True).start()
        elif self.current_operation['type'] == 'authenticate':
            threading.Thread(target=self.run_authentication, daemon=True).start()
            
    def cancel_operation(self):
        """Cancel current operation"""
        if not self.current_operation:
            return
            
        result = {
            'operation_id': self.current_operation['id'],
            'status': 'cancelled'
        }
        self.result_queue.put(result)
        
        self.reset_operation_state()
        self.log_message("Operation cancelled by user.")
        
    def reset_operation_state(self):
        """Reset operation state"""
        self.current_operation = None
        self.current_email = None
        self.running_operation = False
        self.auth_attempts = 0
        self.audio_samples = {'auth_voice': None, 'auth_phrase': None}
        self.operation_label.config(text="Waiting for operations...")
        self.email_label.config(text="None")
        self.start_button.config(state='disabled')
        self.cancel_button.config(state='disabled')
        self.progress_bar.pack_forget()
        
    def clear_messages(self):
        """Clear instruction messages"""
        self.instructions_text.text.delete(1.0, 'end')
        
    def log_message(self, message):
        """Add message to instructions"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.instructions_text.text.insert('end', f"[{timestamp}] {message}\n")
            self.instructions_text.text.see('end')
            self.root.update()
            logging.info(message)
        except Exception as e:
            logging.error(f"Error logging message: {str(e)}")
            
    def send_result(self, status, **kwargs):
        """Send result back to Flask"""
        result = {
            'operation_id': self.current_operation['id'],
            'status': status,
            **kwargs
        }
        self.result_queue.put(result)
        
    def extract_features(self, audio_data):
        """Extract MFCC features from audio"""
        try:
            if isinstance(audio_data, bytes):
                temp_file = 'temp_audio.wav'
                with open(temp_file, 'wb') as f:
                    f.write(audio_data)
                audio_path = temp_file
            else:
                audio_path = audio_data

            y, sr = sf.read(audio_path)
            if len(y) == 0:
                self.log_message("Error: Audio data is empty.")
                if isinstance(audio_data, bytes):
                    os.remove(temp_file)
                return None

            if sr != 22050:
                y = librosa.resample(y, orig_sr=sr, target_sr=22050)
                sr = 22050

            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            if mfccs.size == 0:
                self.log_message("Error: MFCC extraction resulted in empty features.")
                if isinstance(audio_data, bytes):
                    os.remove(temp_file)
                return None

            mfccs = mfccs.T
            mfccs_min = np.min(mfccs, axis=0)
            mfccs_max = np.max(mfccs, axis=0)
            mfccs = (mfccs - mfccs_min) / (mfccs_max - mfccs_min + 1e-8)

            if isinstance(audio_data, bytes):
                os.remove(temp_file)

            self.log_message(f"Extracted MFCCs: shape {mfccs.shape}")
            return mfccs
        except Exception as e:
            self.log_message(f"Error extracting features: {str(e)}")
            if isinstance(audio_data, bytes) and os.path.exists('temp_audio.wav'):
                os.remove(temp_file)
            return None

    def record_audio(self, prompt, return_data=True):
        """Record audio from microphone"""
        self.log_message(prompt)
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                if return_data:
                    wav_data = audio.get_wav_data(convert_rate=22050)
                    if len(wav_data) == 0:
                        self.log_message("Error: Recorded audio is empty.")
                        return None
                    self.log_message("Audio recorded successfully.")
                    return wav_data
                return audio
            except sr.WaitTimeoutError:
                self.log_message("No audio detected within 5 seconds. Try again.")
                return None
            except Exception as e:
                self.log_message(f"Error recording audio: {str(e)}")
                return None

    def save_encrypted_phrase(self, phrase):
        """Encrypt and save phrase"""
        try:
            key = Fernet.generate_key()
            cipher = Fernet(key)
            encrypted = cipher.encrypt(phrase.encode())
            self.log_message("Phrase encrypted successfully.")
            return encrypted, key
        except Exception as e:
            self.log_message(f"Error encrypting phrase: {str(e)}")
            return None, None

    def average_features(self, audio1, audio2):
        """Average features from two audio samples"""
        feats1 = self.extract_features(audio1)
        feats2 = self.extract_features(audio2)
        if feats1 is None or feats2 is None:
            self.log_message("Error: Feature extraction failed for one or both audio samples.")
            return None
        max_len = max(len(feats1), len(feats2))
        feats1 = np.pad(feats1, ((0, max_len - len(feats1)), (0, 0)), mode='mean')
        feats2 = np.pad(feats2, ((0, max_len - len(feats2)), (0, 0)), mode='mean')
        self.log_message("Features averaged successfully.")
        return (feats1 + feats2) / 2

    def save_average_voice(self, audio1, audio2):
        """Save averaged voice data"""
        avg_feats = self.average_features(audio1, audio2)
        if avg_feats is None:
            self.log_message("Error averaging voice features.")
            return None
        try:
            y_inv = librosa.feature.inverse.mfcc_to_audio(avg_feats.T, n_mels=128, sr=22050)
            temp_file = 'temp.wav'
            sf.write(temp_file, y_inv, 22050)
            with open(temp_file, 'rb') as f:
                voice_data = f.read()
            os.remove(temp_file)
            self.log_message(f"Saved averaged voice, size: {len(voice_data)} bytes")
            return voice_data
        except Exception as e:
            self.log_message(f"Error saving averaged voice: {str(e)}")
            return None

    def run_setup(self):
        """Run setup operation"""
        try:
            self.progress_bar.pack(pady=10)
            self.progress_bar["value"] = 0
            self.root.update()

            self.log_message("Starting voice setup...")
            
            # Record first voice sample
            audio1 = self.record_audio("Recording first voice sample... Speak any sentence clearly.")
            if not audio1:
                self.send_result('error', message='First voice recording failed')
                self.reset_operation_state()
                return

            self.progress_bar["value"] = 33
            self.root.update()

            # Record second voice sample
            audio2 = self.record_audio("Recording second voice sample... Speak another sentence clearly.")
            if not audio2:
                self.send_result('error', message='Second voice recording failed')
                self.reset_operation_state()
                return

            self.progress_bar["value"] = 66
            self.root.update()

            # Record unlock phrase
            audio = self.record_audio("Speak your secret unlock phrase (e.g., 'Open my phone')...", return_data=False)
            if not audio:
                self.send_result('error', message='Phrase recording failed')
                self.reset_operation_state()
                return

            try:
                phrase = self.recognizer.recognize_google(audio)
                self.log_message(f"Recognized phrase: '{phrase}'")
                
                # Process voice data
                voice_data = self.save_average_voice(audio1, audio2)
                if not voice_data:
                    self.send_result('error', message='Voice processing failed')
                    self.reset_operation_state()
                    return

                phrase_data, key_data = self.save_encrypted_phrase(phrase)
                if not phrase_data or not key_data:
                    self.send_result('error', message='Phrase encryption failed')
                    self.reset_operation_state()
                    return

                # Save to database
                save_user_data(self.current_email, voice_data, phrase_data, key_data)
                
                self.progress_bar["value"] = 100
                self.root.update()
                time.sleep(0.5)
                
                self.log_message("Setup completed successfully!")
                messagebox.showinfo("Success", "Voice setup completed successfully!")
                self.send_result('success')
                
            except sr.UnknownValueError:
                self.log_message("Error: Could not understand the phrase.")
                self.send_result('error', message='Speech recognition failed')
            except sr.RequestError as e:
                self.log_message(f"Error: Speech recognition service error: {str(e)}")
                self.send_result('error', message='Speech recognition service error')
            except Exception as e:
                self.log_message(f"Setup error: {str(e)}")
                self.send_result('error', message=str(e))
                
        except Exception as e:
            self.log_message(f"Unexpected setup error: {str(e)}")
            self.send_result('error', message=str(e))
        finally:
            self.progress_bar.pack_forget()
            self.reset_operation_state()

    def load_encrypted_phrase(self, key_data, phrase_data):
        """Load and decrypt phrase"""
        try:
            cipher = Fernet(key_data)
            decrypted = cipher.decrypt(phrase_data).decode().strip().lower()
            self.log_message("Phrase decrypted successfully.")
            return decrypted
        except Exception as e:
            self.log_message(f"Error decrypting phrase: {str(e)}")
            return None

    def match_voice(self, stored_voice_data):
        """Match voice against stored data"""
        if not stored_voice_data:
            self.log_message("No authorized voice sample found for this email.")
            return False

        audio_data = self.record_audio("Recording your voice for authentication...", return_data=True)
        if not audio_data:
            return False

        try:
            with open('temp_stored.wav', 'wb') as f:
                f.write(stored_voice_data)
            with open('temp_test.wav', 'wb') as f:
                f.write(audio_data)

            auth_features = self.extract_features('temp_stored.wav')
            test_features = self.extract_features('temp_test.wav')

            os.remove('temp_stored.wav')
            os.remove('temp_test.wav')

            if auth_features is None or test_features is None:
                self.log_message("Error in feature extraction.")
                return False

            distance, _ = fastdtw(auth_features, test_features, dist=euclidean)
            self.log_message(f"Voice Match Score: {distance:.2f}")
            
            if distance >= 500:
                self.log_message("Voice mismatch. Try speaking clearly, closer to the microphone.")
                return False
            self.log_message("Voice match successful!")
            return True
                
        except Exception as e:
            self.log_message(f"Error in voice matching: {str(e)}")
            return False

    def verify_phrase(self, key_data, phrase_data):
        """Verify spoken phrase"""
        audio = self.record_audio("Now speak your unlock phrase...", return_data=False)
        if not audio:
            return False

        try:
            spoken_phrase = self.recognizer.recognize_google(audio).strip().lower()
            stored_phrase = self.load_encrypted_phrase(key_data, phrase_data)
            if stored_phrase is None:
                self.log_message("Error: Failed to load stored phrase.")
                return False
                
            self.log_message(f"You said: '{spoken_phrase}'")
            similarity = fuzz.ratio(spoken_phrase, stored_phrase)
            self.log_message(f"Phrase Similarity: {similarity}%")
            
            if similarity > 80:
                self.log_message("Phrase match successful!")
                return True
            self.log_message("Phrase mismatch. Try speaking the exact phrase.")
            return False
                
        except sr.UnknownValueError:
            self.log_message("Error: Could not understand the phrase.")
            return False
        except sr.RequestError as e:
            self.log_message(f"Error: Speech recognition service error: {str(e)}")
            return False
        except Exception as e:
            self.log_message(f"Error verifying phrase: {str(e)}")
            return False

    def capture_intruder(self):
        """Capture intruder photo"""
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.log_message("Error: Could not access camera.")
                return False
            ret, frame = cap.read()
            if ret:
                filename = f"intruder_{self.current_email}_{time.time()}.jpg"
                cv2.imwrite(filename, frame)
                self.log_message(f"Intruder photo saved as {filename}")
                cap.release()
                return True
            cap.release()
            self.log_message("Error: Failed to capture photo.")
            return False
        except Exception as e:
            self.log_message(f"Error capturing intruder: {str(e)}")
            return False

    def run_authentication(self):
        """Run authentication operation"""
        try:
            self.progress_bar.pack(pady=10)
            self.progress_bar["value"] = 0
            self.root.update()

            user_data = get_user_data(self.current_email)
            if not user_data:
                self.log_message("Error: No user data found for this email.")
                self.send_result('error', message='No user data found')
                self.reset_operation_state()
                return

            voice_data, phrase_data, key_data = user_data  # Unpack 3 values
            self.auth_attempts += 1

            self.log_message(f"Authentication attempt {self.auth_attempts}/{self.max_attempts}")
            
            # Record and match voice
            self.progress_bar["value"] = 50
            self.root.update()
            voice_ok = self.match_voice(voice_data)
            if not voice_ok:
                self.handle_auth_failure()
                return

            # Record and verify phrase
            self.progress_bar["value"] = 75
            self.root.update()
            phrase_ok = self.verify_phrase(key_data, phrase_data)
            if not phrase_ok:
                self.handle_auth_failure()
                return

            # Success
            self.progress_bar["value"] = 100
            self.root.update()
            time.sleep(0.5)
            
            self.log_message("Authentication successful!")
            messagebox.showinfo("Success", "Authentication successful!")
            self.send_result('success', authenticated=True)
            self.reset_operation_state()

        except Exception as e:
            self.log_message(f"Authentication error: {str(e)}")
            self.handle_auth_failure()
        finally:
            self.progress_bar.pack_forget()
            self.reset_operation_state()

    def handle_auth_failure(self):
        """Handle authentication failure"""
        if self.auth_attempts >= self.max_attempts:
            self.log_message("Maximum authentication attempts reached.")
            self.capture_intruder()
            self.send_result('success', authenticated=False)
            self.reset_operation_state()
        else:
            self.log_message(f"Authentication failed. {self.max_attempts - self.auth_attempts} attempts remaining.")
            self.audio_samples = {'auth_voice': None, 'auth_phrase': None}
            self.progress_bar["value"] = 0
            self.running_operation = False
            self.start_button.config(state='normal')
            self.root.update()