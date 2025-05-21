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
from database import save_user_data, get_user_data
import queue

# Setup logging
logging.basicConfig(filename="auth.log", level=logging.INFO)

class SetupWindow:
    def __init__(self, root, email_queue):
        self.root = root
        self.email_queue = email_queue
        self.root.title("Voice Setup")
        self.root.geometry("600x500")
        self.root.resizable(True, True)

        # GUI Elements
        self.label = ttk.Label(root, text="Voice Setup", font=("Arial", 18, "bold"), bootstyle="light")
        self.label.pack(pady=15)

        self.email_label = ttk.Label(root, text="Previously entered Email: None", font=("Arial", 12), bootstyle="light")
        self.email_label.pack(pady=5)

        self.status_text = ScrolledText(root, height=10, width=60, font=("Arial", 10), wrap="word",
                                      bootstyle="dark", padding=5)
        self.status_text.pack(pady=15)
        self.status_text.text.insert("end", "Enter your email in the web interface to start setup.\n")
        self.status_text.text.bind("<Key>", lambda e: "break")

        self.progress_bar = ttk.Progressbar(root, bootstyle="primary", mode="determinate", length=300)
        self.progress_bar.pack(pady=10)
        self.progress_bar.pack_forget()

        self.setup_button = ttk.Button(root, text="Start Setup", command=self.start_setup, bootstyle="primary", width=15)
        self.setup_button.pack(pady=5)

        # Initialize variables
        self.running = False
        self.recognizer = sr.Recognizer()
        self.current_email = None

        # Start polling for email
        self.root.after(100, self.check_email_queue)

    def check_email_queue(self):
        try:
            email = self.email_queue.get_nowait()
            self.current_email = email
            self.email_label.config(text=f"Previously entered Email: {email}")
            self.log_status(f"Email received: {email}")
            self.root.lift()
            self.root.focus_force()
        except queue.Empty:
            pass
        self.root.after(100, self.check_email_queue)

    def log_status(self, message):
        try:
            self.status_text.text.configure(state='normal')
            self.status_text.text.insert("end", f"{datetime.now().strftime('%H:%M:%S')}: {message}\n")
            self.status_text.text.see("end")
            self.status_text.text.configure(state='disabled')
            self.root.update()
            logging.info(message)
        except Exception as e:
            logging.error(f"Error updating status: {str(e)}")

    def save_encrypted_phrase(self, phrase):
        try:
            key = Fernet.generate_key()
            cipher = Fernet(key)
            encrypted = cipher.encrypt(phrase.encode())
            return encrypted, key
        except Exception as e:
            self.log_status(f"Error encrypting phrase: {str(e)}")
            return None, None

    def extract_features(self, audio_data):
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
                self.log_status("Error: Audio data is empty.")
                if isinstance(audio_data, bytes):
                    os.remove(temp_file)
                return None

            if sr != 22050:
                y = librosa.resample(y, orig_sr=sr, target_sr=22050)
                sr = 22050

            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            if mfccs.size == 0:
                self.log_status("Error: MFCC extraction resulted in empty features.")
                if isinstance(audio_data, bytes):
                    os.remove(temp_file)
                return None

            mfccs = mfccs.T
            mfccs_min = np.min(mfccs, axis=0)
            mfccs_max = np.max(mfccs, axis=0)
            mfccs = (mfccs - mfccs_min) / (mfccs_max - mfccs_min + 1e-8)

            if isinstance(audio_data, bytes):
                os.remove(temp_file)

            return mfccs
        except Exception as e:
            self.log_status(f"Error extracting features: {str(e)}")
            if isinstance(audio_data, bytes) and os.path.exists(temp_file):
                os.remove(temp_file)
            return None

    def average_features(self, audio1, audio2):
        feats1 = self.extract_features(audio1)
        feats2 = self.extract_features(audio2)
        if feats1 is None or feats2 is None:
            self.log_status("Error: Feature extraction failed for one or both audio samples.")
            return None
        max_len = max(len(feats1), len(feats2))
        feats1 = np.pad(feats1, ((0, max_len - len(feats1)), (0, 0)), mode='mean')
        feats2 = np.pad(feats2, ((0, max_len - len(feats2)), (0, 0)), mode='mean')
        return (feats1 + feats2) / 2

    def save_average_voice(self, audio1, audio2):
        avg_feats = self.average_features(audio1, audio2)
        if avg_feats is None:
            self.log_status("Error averaging voice features.")
            return None
        try:
            y_inv = librosa.feature.inverse.mfcc_to_audio(avg_feats.T, n_mels=13, sr=22050)
            temp_file = 'temp.wav'
            sf.write(temp_file, y_inv, 22050)
            with open(temp_file, 'rb') as f:
                voice_data = f.read()
            os.remove(temp_file)
            return voice_data
        except Exception as e:
            self.log_status(f"Error saving averaged voice: {e}")
            return None

    def record_audio(self, prompt, return_data=True):
        self.log_status(prompt)
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                if return_data:
                    wav_data = audio.get_wav_data(convert_rate=22050)
                    if len(wav_data) == 0:
                        self.log_status("Error: Recorded audio is empty.")
                        return None
                    return wav_data
                return audio
            except sr.WaitTimeoutError:
                self.log_status("No audio detected. Try again.")
                return None
            except Exception as e:
                self.log_status(f"Error recording audio: {e}")
                return None

    def run_setup(self, email):
        try:
            self.current_email = email
            self.email_label.config(text=f"Previously entered Email: {email}")
            self.progress_bar.pack(pady=10)
            self.progress_bar["value"] = 0
            self.root.update()

            self.log_status("Starting setup...")
            audio1 = self.record_audio("Recording first voice sample... Speak any sentence.")
            if not audio1:
                self.log_status("Setup failed due to voice recording error.")
                self.progress_bar.pack_forget()
                return

            self.progress_bar["value"] = 25
            self.root.update()

            audio2 = self.record_audio("Recording second voice sample... Speak another sentence.")
            if not audio2:
                self.log_status("Setup failed due to voice recording error.")
                self.progress_bar.pack_forget()
                return

            self.progress_bar["value"] = 50
            self.root.update()

            voice_data = self.save_average_voice(audio1, audio2)
            if not voice_data:
                self.log_status("Setup failed due to voice processing error.")
                self.progress_bar.pack_forget()
                return

            self.progress_bar["value"] = 75
            self.root.update()

            audio = self.record_audio("Speak your secret unlock phrase (e.g., 'Open my phone')...", return_data=False)
            if not audio:
                self.log_status("Setup failed due to phrase recording error.")
                self.progress_bar.pack_forget()
                return

            phrase = self.recognizer.recognize_google(audio)
            phrase_data, key_data = self.save_encrypted_phrase(phrase)
            if not phrase_data or not key_data:
                self.log_status("Setup failed due to phrase encryption error.")
                self.progress_bar.pack_forget()
                return

            save_user_data(email, voice_data, phrase_data, key_data)
            self.progress_bar["value"] = 100
            self.root.update()
            time.sleep(0.5)
            self.log_status("Setup complete! Voice and phrase saved.")
            messagebox.showinfo("Success", "Setup completed successfully!")
        except Exception as e:
            self.log_status(f"Setup error: {str(e)}")
            logging.error(f"Setup error for {email}: {str(e)}")
            messagebox.showerror("Error", "Setup failed. Please try again.")
        finally:
            self.progress_bar.pack_forget()
            self.running = False
            self.setup_button.config(state='normal')
            self.root.destroy()  # Close window

    def start_setup(self, email=None):
        if self.running:
            return
        email = email or self.current_email
        if not email:
            messagebox.showerror("Error", "Please enter an email address in the web interface.")
            return
        self.running = True
        self.setup_button.config(state='disabled')
        threading.Thread(target=self.run_setup, args=(email,), daemon=True).start()

class AuthWindow:
    def __init__(self, root, email_queue):
        self.root = root
        self.email_queue = email_queue
        self.root.title("Voice Authentication")
        self.root.geometry("600x500")
        self.root.resizable(True, True)

        # GUI Elements
        self.label = ttk.Label(root, text="Voice Authentication", font=("Arial", 18, "bold"), bootstyle="light")
        self.label.pack(pady=15)

        self.email_label = ttk.Label(root, text="Previously entered Email: None", font=("Arial", 12), bootstyle="light")
        self.email_label.pack(pady=5)

        self.status_text = ScrolledText(root, height=10, width=60, font=("Arial", 10), wrap="word",
                                      bootstyle="dark", padding=5)
        self.status_text.pack(pady=15)
        self.status_text.text.insert("end", "Enter your email in the web interface to start authentication.\n")
        self.status_text.text.bind("<Key>", lambda e: "break")

        self.auth_button = ttk.Button(root, text="Start Authentication", command=self.start_authentication, bootstyle="primary", width=15)
        self.auth_button.pack(pady=5)

        # Initialize variables
        self.running = False
        self.recognizer = sr.Recognizer()
        self.current_email = None
        self.auth_result = False

        # Start polling for email
        self.root.after(100, self.check_email_queue)

    def check_email_queue(self):
        try:
            email = self.email_queue.get_nowait()
            self.current_email = email
            self.email_label.config(text=f"Previously entered Email: {email}")
            self.log_status(f"Email received: {email}")
            self.root.lift()
            self.root.focus_force()
        except queue.Empty:
            pass
        self.root.after(100, self.check_email_queue)

    def log_status(self, message):
        try:
            self.status_text.text.configure(state='normal')
            self.status_text.text.insert("end", f"{datetime.now().strftime('%H:%M:%S')}: {message}\n")
            self.status_text.text.see("end")
            self.status_text.text.configure(state='disabled')
            self.root.update()
            logging.info(message)
        except Exception as e:
            logging.error(f"Error updating status: {str(e)}")

    def load_encrypted_phrase(self, key_data, phrase_data):
        try:
            cipher = Fernet(key_data)
            return cipher.decrypt(phrase_data).decode().strip().lower()
        except Exception as e:
            self.log_status(f"Error loading phrase: {e}")
            return None

    def extract_features(self, audio_data):
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
                self.log_status("Error: Audio data is empty.")
                if isinstance(audio_data, bytes):
                    os.remove(temp_file)
                return None

            if sr != 22050:
                y = librosa.resample(y, orig_sr=sr, target_sr=22050)
                sr = 22050

            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            if mfccs.size == 0:
                self.log_status("Error: MFCC extraction resulted in empty features.")
                if isinstance(audio_data, bytes):
                    os.remove(temp_file)
                return None

            mfccs = mfccs.T
            mfccs_min = np.min(mfccs, axis=0)
            mfccs_max = np.max(mfccs, axis=0)
            mfccs = (mfccs - mfccs_min) / (mfccs_max - mfccs_min + 1e-8)

            if isinstance(audio_data, bytes):
                os.remove(temp_file)

            return mfccs
        except Exception as e:
            self.log_status(f"Error extracting features: {str(e)}")
            if isinstance(audio_data, bytes) and os.path.exists(temp_file):
                os.remove(temp_file)
            return None

    def record_audio(self, prompt, return_data=True):
        self.log_status(prompt)
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                if return_data:
                    wav_data = audio.get_wav_data(convert_rate=22050)
                    if len(wav_data) == 0:
                        self.log_status("Error: Recorded audio is empty.")
                        return None
                    return wav_data
                return audio
            except sr.WaitTimeoutError:
                self.log_status("No audio detected. Try again.")
                return None
            except Exception as e:
                self.log_status(f"Error recording audio: {e}")
                return None

    def capture_intruder(self):
        self.log_status("Capturing intruder photo...")
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            self.log_status("Camera not available.")
            return
        for _ in range(10):
            cam.read()
            time.sleep(0.1)
        ret, frame = cam.read()
        if ret:
            cv2.imwrite("static/intruder.jpg", frame)
            self.log_status("Intruder photo saved.")
        else:
            self.log_status("Failed to capture image.")
        cam.release()

    def match_voice(self, stored_voice_data):
        if not stored_voice_data:
            self.log_status("No authorized voice sample found for this email.")
            return False

        audio_data = self.record_audio("Recording voice for authentication...", return_data=True)
        if not audio_data:
            return False

        with open('temp_stored.wav', 'wb') as f:
            f.write(stored_voice_data)
        with open('temp_test.wav', 'wb') as f:
            f.write(audio_data)

        auth_features = self.extract_features('temp_stored.wav')
        test_features = self.extract_features('temp_test.wav')

        os.remove('temp_stored.wav')
        os.remove('temp_test.wav')

        if auth_features is None or test_features is None:
            self.log_status("Error in feature extraction.")
            return False

        distance, _ = fastdtw(auth_features, test_features, dist=euclidean)
        self.log_status(f"Voice Match Score: {distance:.2f}")
        if distance >= 500:
            self.log_status("Voice mismatch. Try speaking clearly, closer to the microphone.")
        return distance < 500

    def verify_phrase(self, key_data, phrase_data):
        audio = self.record_audio("Speak your unlock phrase...", return_data=False)
        if not audio:
            return False

        try:
            spoken_phrase = self.recognizer.recognize_google(audio).strip().lower()
            stored_phrase = self.load_encrypted_phrase(key_data, phrase_data)
            if stored_phrase is None:
                return False
            similarity = fuzz.ratio(spoken_phrase, stored_phrase)
            self.log_status(f"Phrase Similarity: {similarity}%")
            return similarity > 90
        except Exception as e:
            self.log_status(f"Error recognizing phrase: {e}")
            return False

    def run_authentication(self, email):
        try:
            self.current_email = email
            self.email_label.config(text=f"Previously entered Email: {email}")
            user_data = get_user_data(email)
            if not user_data:
                self.log_status("No user data found for this email. Please run Setup first.")
                return False

            voice_data, phrase_data, key_data = user_data
            max_attempts = 3
            for attempt in range(max_attempts):
                self.log_status(f"Authentication Attempt {attempt + 1}/{max_attempts}")
                voice_ok = self.match_voice(voice_data)
                phrase_ok = self.verify_phrase(key_data, phrase_data)
                if voice_ok and phrase_ok:
                    self.log_status("Access Granted! Redirecting to success page...")
                    logging.info(f"Authentication successful for {email} at {datetime.now()}")
                    self.auth_result = True
                    return True
                else:
                    self.log_status("Authentication failed.")
            self.log_status("Max attempts reached. Capturing intruder photo...")
            self.capture_intruder()
            logging.info(f"Authentication failed for {email} at {datetime.now()}")
            messagebox.showwarning("Failed", "Authentication failed. Intruder photo captured.")
            return False
        except Exception as e:
            self.log_status(f"Authentication error: {str(e)}")
            logging.error(f"Authentication error for {email}: {str(e)}")
            messagebox.showerror("Error", "Authentication failed. Please try again.")
            return False

    def start_authentication(self):
        if self.running:
            return
        if not self.current_email:
            messagebox.showerror("Error", "Please enter an email address in the web interface.")
            return
        self.running = True
        self.auth_button.config(state='disabled')
        self.auth_result = self.run_authentication(self.current_email)
        self.auth_button.config(state='normal')
        self.running = False
        self.root.destroy()  # Close window