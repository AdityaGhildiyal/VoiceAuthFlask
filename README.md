HOW TO EXECUTE :

pip install flask ttkbootstrap numpy librosa speechrecognition opencv-python fastdtw soundfile fuzzywuzzy cryptography pillow pyaudio<br>
python app.py


🔐 Voice Authentication System
A Python-based multi-factor authentication system that uses voice biometrics and a spoken passphrase to verify identity. It includes intruder detection via webcam capture for added security.

📌 Features
Voice Registration & Authentication

Passphrase Matching

Intruder Detection via Webcam

Encryption of Sensitive Data

Logging & Retry Mechanism

🧠 Core Functionality
🛠️ Setup Phase
Voice Registration
Records two voice samples (e.g., “This is me”, “Hello again”) and averages them to create a robust profile.

Phrase Registration
Captures a secret phrase (e.g., “Open my device”), transcribes and encrypts it.

Output Files:

authorized_voice.wav: Averaged voice sample

authorized_phrase.txt: Encrypted phrase

key.key: Encryption key

auth.log: Setup log

🔐 Authentication Phase
Voice Verification

Records a new voice sample

Extracts MFCC features and compares using DTW

Pass Threshold: DTW distance < 500

Phrase Verification

Transcribes phrase via Google API

Compares with stored phrase using fuzzywuzzy

Pass Threshold: Similarity > 90%

Intruder Detection

On 3 failed attempts, captures webcam image as intruder.jpg

⚙️ Technical Implementation
🧩 Libraries & Dependencies
Category	Libraries Used
Audio Processing	librosa, soundfile, speech_recognition, PyAudio
Voice Matching	fastdtw, scipy, numpy
Phrase Matching	fuzzywuzzy, python-Levenshtein
Encryption	cryptography (Fernet)
Image Capture	opencv-python
Logging	logging

🛠️ Setup Process
Voice Recording

Two 5-second samples → authorized_voice1.wav, authorized_voice2.wav

Feature Extraction

MFCC (13-coefficients), normalized via min-max scaling

Averaging

Padded and averaged → authorized_voice.wav

Phrase Recording

Transcribed via Google Speech API

Encrypted with Fernet → authorized_phrase.txt

Logging

Events recorded in auth.log

🔄 Authentication Process
Voice Recording

Records a 5-second sample → test_voice.wav

Voice Matching

Normalized MFCC + DTW comparison

Success: DTW score < 500

Phrase Matching

Transcribes and compares with stored phrase

Success: Similarity > 90%

Retry Logic

Up to 3 attempts allowed

Intruder Capture

Fails after 3 attempts → intruder.jpg saved via webcam

🗃️ File Management
File	Description
authorized_voice.wav	Averaged registered voice
authorized_phrase.txt	Encrypted phrase
key.key	Encryption key
auth.log	Logs of all setup/auth events
intruder.jpg	Webcam photo on 3 failed auth attempts
Temp Files	test_voice.wav, authorized_voice1.wav, authorized_voice2.wav (auto-deleted)

⏱️ Performance
Phase	Time	Notes
Setup	~11–12 sec	Voice + phrase recording & processing
Auth Attempt	~6–7 sec	Fast, real-time evaluation
Accuracy	High	DTW < 500 & fuzzy match > 90% recommended

✅ Strengths
✔️ Multi-Factor Security: Combines biometric (voice) and knowledge (phrase)

✔️ Intruder Detection: Webcam photo on failure

✔️ Error Handling & Logs: Tracks all key events and errors

✔️ Encryption: Protects sensitive data (passphrase)

✔️ Natural Variation Tolerance: 2-sample average + MFCC normalization

⚠️ Limitations
❌ Internet Dependency: Google API needed for transcription

❌ Noise Sensitivity: Background noise affects accuracy

❌ No Liveness Detection: Replay attacks possible

❌ Voice File Unencrypted: authorized_voice.wav can be stolen

❌ Webcam Requirement: Intruder detection fails if unavailable

❌ Static Threshold: DTW threshold fixed at 500 (not user-adaptive)

🧪 Testing Summary
Scenario	Outcome
✅ Quiet Room	Auth success (~DTW 200-400, similarity ~95–100%)
❌ Wrong Voice	DTW > 500 → Auth fails
❌ Wrong Phrase	Similarity < 90% → Auth fails
❌ No Mic	Logs error: "No audio detected"
❌ No Internet	Transcription fails, process halted
❌ No Webcam	Photo not captured; continues silently

💡 Recommendations
🔄 Offline API: Replace Google API with vosk or whisper

🔐 Voice Encryption: Encrypt authorized_voice.wav

🔍 Liveness Check: Add random passphrase prompt

📊 Adaptive Threshold: Per-user DTW calibration

🔉 Noise Filtering: Preprocess with librosa noise reduction

🎙️ More Samples: Use 3+ voice samples during setup

🏁 Operational Workflow
Setup
User runs the setup script

Records two voice samples

Records secret phrase

Saves all necessary files

Logs setup in auth.log

Authentication
Records a test voice and phrase

Compares voice (DTW < 500)

Compares phrase (similarity > 90%)

On success: ✅ Access Granted

On 3 failures: 🚫 intruder.jpg captured, logs updated


