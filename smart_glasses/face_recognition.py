import cv2
import numpy as np
import os
import pickle
import threading
import time
import json
import logging
from datetime import datetime
from .base import SmartGlasses

logger = logging.getLogger(__name__)

# The face_recognition package needs dlib, a native library that is often not
# installed (or not installable) on the target device. Everything in this
# module degrades to a no-op when it is missing instead of raising.
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    logger.warning("face_recognition module not available (requires the dlib and "
                   "face_recognition packages) - face recognition features will be disabled")
    FACE_RECOGNITION_AVAILABLE = False

UNAVAILABLE_MESSAGE = "Face recognition is not available on this device"

class FaceRecognizer(SmartGlasses):
    """Face recognition, person identification, emotion detection, and name learning"""

    def __init__(self, config=None, face_db_path="face_database.pkl", metadata_path="face_metadata.json"):
        # Initialize the base class
        super().__init__(config)

        # Paths for face database and metadata
        self.face_db_path = face_db_path
        self.metadata_path = metadata_path

        # Safe defaults so every method works (as a no-op) even when the
        # library is missing and the rest of __init__ is skipped.
        self.known_faces = {}
        self.face_metadata = {}
        self.learning_mode = False
        self.new_face_name = None
        self.new_face_encoding = None
        self.emotion_model_loaded = False

        # Check if face_recognition is available
        self.face_recognition_available = FACE_RECOGNITION_AVAILABLE
        if not self.face_recognition_available:
            logger.warning("Face recognition functionality is disabled: the face_recognition "
                           "and dlib packages are not installed")
            return

        # Load or create face database
        if os.path.exists(face_db_path):
            with open(face_db_path, 'rb') as f:
                self.known_faces = pickle.load(f)
            logger.info(f"Loaded {len(self.known_faces)} known faces from database")
        else:
            logger.info("Created new face database")

        # Load or create metadata
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                self.face_metadata = json.load(f)
            logger.info(f"Loaded metadata for {len(self.face_metadata)} persons")
        else:
            logger.info("Created new face metadata storage")

        # Face detection parameters
        self.detection_interval = 0.5  # seconds between detection attempts
        self.last_detection_time = 0

        # Recognition settings
        self.face_recognition_tolerance = 0.6  # Lower is more strict

        # Emotion labels
        self.emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

        # Load emotion detection model (placeholder, you would need a real model)
        # self.emotion_model = load_emotion_model()

        logger.info("Face recognizer initialized")

    def _unavailable(self):
        """Log and announce that face recognition cannot be used."""
        logger.warning("Face recognition requested but the face_recognition/dlib packages are not installed")
        self.speak(UNAVAILABLE_MESSAGE)

    def detect_faces(self, frame):
        """Detect faces in the frame"""
        if not self.face_recognition_available:
            self._unavailable()
            return [], None
            
        # Convert to RGB for face_recognition library
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Get face locations
        face_locations = face_recognition.face_locations(rgb_frame)
        
        return face_locations, rgb_frame
    
    def recognize_faces(self, frame):
        """Detect and recognize faces in the frame"""
        if not self.face_recognition_available:
            self._unavailable()
            return frame
            
        current_time = time.time()
        
        # Limit face detection rate to avoid excessive CPU usage
        if current_time - self.last_detection_time < self.detection_interval:
            return frame
        
        self.last_detection_time = current_time
        
        # Detect faces
        face_locations, rgb_frame = self.detect_faces(frame)
        
        if face_locations:
            # Get face encodings for all faces in the frame
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            
            # Loop through each face
            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                name = "Unknown"
                
                # Check if the face matches any known faces
                if self.known_faces:
                    matches = []
                    for known_name, known_encodings in self.known_faces.items():
                        # Compare this face to known faces
                        for known_encoding in known_encodings:
                            match = face_recognition.compare_faces(
                                [known_encoding], face_encoding, tolerance=self.face_recognition_tolerance
                            )[0]
                            if match:
                                matches.append(known_name)
                                break
                    
                    # Use the name that appeared most often
                    if matches:
                        from collections import Counter
                        name = Counter(matches).most_common(1)[0][0]
                
                # If in learning mode and an unknown face is detected
                if self.learning_mode and name == "Unknown" and self.new_face_name:
                    self.learn_face(self.new_face_name, face_encoding)
                    name = self.new_face_name
                    self.speak(f"I've learned to recognize {name}")
                    self.learning_mode = False
                    self.new_face_name = None
                
                # Get estimated age, gender and emotion
                age_estimate = "unknown age"
                gender_estimate = "unknown gender"
                emotion = "neutral"
                
                # Actually, these would be determined by ML models in a real implementation
                # Here we just use placeholders
                
                # Update metadata for known person
                if name != "Unknown":
                    if name not in self.face_metadata:
                        self.face_metadata[name] = {
                            "encounters": 0,
                            "first_seen": datetime.now().isoformat(),
                            "last_seen": datetime.now().isoformat(),
                            "estimated_age": age_estimate,
                            "estimated_gender": gender_estimate,
                            "notes": ""
                        }
                    
                    # Update encounter data
                    self.face_metadata[name]["encounters"] += 1
                    self.face_metadata[name]["last_seen"] = datetime.now().isoformat()
                    
                    # Save the updated metadata
                    self.save_metadata()
                
                # Draw rectangle and label on the frame
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)
                
                # Announce the person
                person_id = f"person_{name}"
                if person_id not in self.last_announced or (current_time - self.last_announced[person_id]) > self.announcement_cooldown:
                    message = f"I see {name}"
                    if name in self.face_metadata:
                        encounters = self.face_metadata[name]["encounters"]
                        if encounters > 1:
                            message += f", who I've seen {encounters} times before"
                    
                    threading.Thread(target=self.speak, args=(message,)).start()
                    self.last_announced[person_id] = current_time
        
        return frame
    
    def learn_face(self, name, face_encoding):
        """Learn a new face and associate with the given name"""
        if not self.face_recognition_available:
            self._unavailable()
            return False
            
        if name in self.known_faces:
            self.known_faces[name].append(face_encoding)
        else:
            self.known_faces[name] = [face_encoding]
        
        # Save the updated face database
        with open(self.face_db_path, 'wb') as f:
            pickle.dump(self.known_faces, f)
        
        logger.info(f"Learned face for {name}")
        return True

    def start_learning_mode(self, name):
        """Start the process of learning a new face"""
        if not self.face_recognition_available:
            self._unavailable()
            return False
            
        self.learning_mode = True
        self.new_face_name = name
        self.speak(f"Looking for a face to remember as {name}. Please face the camera.")
        return True
    
    def detect_emotion(self, face_image):
        """Detect emotion from a face image"""
        if not self.emotion_model_loaded:
            # Placeholder - in a real implementation, you would use a trained model
            return "neutral"
        
        # Preprocess the face image for the emotion model
        resized_face = cv2.resize(face_image, (48, 48))
        normalized_face = resized_face / 255.0
        
        # Make prediction
        # emotion_prediction = self.emotion_model.predict(normalized_face)
        # emotion_label = self.emotion_labels[np.argmax(emotion_prediction)]
        
        # Placeholder
        emotion_label = "neutral"
        
        return emotion_label
    
    def save_metadata(self):
        """Save person metadata to file"""
        if not self.face_recognition_available:
            return
        with open(self.metadata_path, 'w') as f:
            json.dump(self.face_metadata, f, indent=2)

    def add_note_to_person(self, name, note):
        """Add a note about a person to their metadata"""
        if not self.face_recognition_available:
            self._unavailable()
            return False

        if name in self.face_metadata:
            if "notes" not in self.face_metadata[name]:
                self.face_metadata[name]["notes"] = ""
            
            self.face_metadata[name]["notes"] += f"\n{datetime.now().isoformat()}: {note}"
            self.save_metadata()
            self.speak(f"Added note to {name}'s profile")
            return True
        else:
            self.speak(f"I don't know anyone named {name}")
            return False
    
    def get_person_info(self, name):
        """Get information about a known person"""
        if not self.face_recognition_available:
            self._unavailable()
            return None

        if name in self.face_metadata:
            info = self.face_metadata[name]
            
            # Calculate days since first and last seen
            first_seen = datetime.fromisoformat(info["first_seen"])
            last_seen = datetime.fromisoformat(info["last_seen"])
            days_known = (datetime.now() - first_seen).days
            days_since_last = (datetime.now() - last_seen).days
            
            message = f"{name}: "
            message += f"Known for {days_known} days. "
            message += f"Seen {info['encounters']} times. "
            message += f"Last seen {days_since_last} days ago. "
            
            if "estimated_age" in info and info["estimated_age"] != "unknown age":
                message += f"Estimated age: {info['estimated_age']}. "
            
            if "estimated_gender" in info and info["estimated_gender"] != "unknown gender":
                message += f"Estimated gender: {info['estimated_gender']}. "
            
            if "notes" in info and info["notes"]:
                message += f"Notes: {info['notes']}"
            
            self.speak(message)
            return info
        else:
            self.speak(f"I don't know anyone named {name}")
            return None
    
    def delete_person(self, name):
        """Delete a person from the face database and metadata"""
        if not self.face_recognition_available:
            self._unavailable()
            return False
            
        # Check if the person exists
        if name in self.known_faces:
            # Remove from face encodings database
            del self.known_faces[name]
            # Save the updated database
            with open(self.face_db_path, 'wb') as f:
                pickle.dump(self.known_faces, f)
                
            # Remove from metadata if exists
            if name in self.face_metadata:
                del self.face_metadata[name]
                self.save_metadata()
                
            self.speak(f"Deleted {name} from the recognition system")
            logger.info(f"Deleted {name} from the face database")
            return True
        else:
            self.speak(f"I don't know anyone named {name}")
            return False

    def list_known_people(self):
        """List all known people in the database"""
        if not self.face_recognition_available:
            self._unavailable()
            return []

        if not self.known_faces:
            self.speak("No faces in the database")
            logger.info("No faces in the database")
            return []

        known_people = list(self.known_faces.keys())
        self.speak(f"I know {len(known_people)} people: {', '.join(known_people)}")
        logger.info("Known people in database:")
        for person in known_people:
            encounters = self.face_metadata.get(person, {}).get("encounters", 0)
            logger.info(f"- {person} (seen {encounters} times)")
        return known_people

    def run_face_recognition_loop(self):
        """Main face recognition loop"""
        if not self.face_recognition_available:
            logger.error("Cannot start the face recognition loop: the face_recognition and dlib "
                         "packages are not installed (pip install -e '.[face]')")
            self.speak(UNAVAILABLE_MESSAGE)
            return

        try:
            # Display available commands
            logger.info("Face Recognition Keyboard Commands: "
                        "r - Remember new face | d - Delete a person | l - List known people | "
                        "i - Get info about a person | n - Add a note | q - Quit")

            self.speak("Face recognition active. Press 'r' to remember a new face.")
            
            # State for keyboard input
            input_mode = None
            current_frame = None
            
            while True:
                # Capture frame
                frame = self.capture_frame()
                current_frame = frame.copy()  # Store a copy for learning faces
                
                # Process for face recognition
                processed_frame = self.recognize_faces(frame)
                
                # Add instruction on the frame
                if input_mode == "remember":
                    instruction = "Enter name in terminal to remember this face"
                elif input_mode == "delete":
                    instruction = "Enter name in terminal to delete a person"
                elif input_mode == "info":
                    instruction = "Enter name in terminal to get info"
                elif input_mode == "note":
                    instruction = "Enter name in terminal to add a note"
                else:
                    # Show controls reminder
                    instruction = "r: Remember | d: Delete | l: List | i: Info | n: Note | q: Quit"
                
                cv2.putText(processed_frame, instruction, (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Display the frame
                cv2.imshow("Face Recognition", processed_frame)
                
                # Check for keyboard input
                key = cv2.waitKey(1) & 0xFF
                
                # Exit on 'q' key
                if key == ord('q'):
                    break
                    
                # Remember new face on 'r' key
                elif key == ord('r') and input_mode is None:
                    input_mode = "remember"
                    self.speak("Enter a name for this face")
                    print("\n📝 Enter name for this face: ", end='', flush=True)
                    name = input().strip()
                    
                    if name:
                        self.speak(f"Looking for a face to remember as {name}")
                        
                        if len(face_recognition.face_locations(cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB))) > 0:
                            # Face detected in the current frame
                            self.start_learning_mode(name)
                            # Use the current frame to learn the face immediately
                            rgb_frame = cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB)
                            face_locations = face_recognition.face_locations(rgb_frame)
                            if face_locations:
                                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                                if face_encodings:
                                    self.learn_face(name, face_encodings[0])
                                    self.speak(f"I've learned to recognize {name}")
                        else:
                            self.speak("No face detected in the current frame")
                    else:
                        self.speak("Name cannot be empty")
                    
                    input_mode = None
                
                # Delete a person on 'd' key
                elif key == ord('d') and input_mode is None:
                    input_mode = "delete"
                    # List known people first
                    known_people = self.list_known_people()
                    if known_people:
                        self.speak("Enter the name of the person to delete")
                        print("\n📝 Enter name to delete: ", end='', flush=True)
                        name = input().strip()
                        
                        if name:
                            # Ask for confirmation
                            print(f"⚠️ Are you sure you want to delete {name}? (y/n): ", end='', flush=True)
                            confirm = input().strip().lower()
                            if confirm == 'y' or confirm == 'yes':
                                self.delete_person(name)
                            else:
                                self.speak("Deletion cancelled")
                        else:
                            self.speak("Name cannot be empty")
                    
                    input_mode = None
                
                # List known people on 'l' key
                elif key == ord('l') and input_mode is None:
                    self.list_known_people()
                    # Pause for a moment to allow reading the list
                    time.sleep(2)
                    
                # Get info about a person on 'i' key
                elif key == ord('i') and input_mode is None:
                    input_mode = "info"
                    self.speak("Enter the name of the person")
                    print("\n📝 Enter name to get info: ", end='', flush=True)
                    name = input().strip()
                    
                    if name:
                        self.get_person_info(name)
                    else:
                        self.speak("Name cannot be empty")
                    
                    input_mode = None
                    
                # Add note about a person on 'n' key
                elif key == ord('n') and input_mode is None:
                    input_mode = "note"
                    self.speak("Enter the name of the person to add a note")
                    print("\n📝 Enter name to add a note: ", end='', flush=True)
                    name = input().strip()
                    
                    if name:
                        if name in self.face_metadata:
                            self.speak(f"Enter a note for {name}")
                            print(f"📝 Enter note for {name}: ", end='', flush=True)
                            note = input().strip()
                            
                            if note:
                                self.add_note_to_person(name, note)
                            else:
                                self.speak("Note cannot be empty")
                        else:
                            self.speak(f"I don't know anyone named {name}")
                    else:
                        self.speak("Name cannot be empty")
                    
                    input_mode = None
                    
        except KeyboardInterrupt:
            logger.info("Face recognition stopped by user")
        finally:
            cv2.destroyAllWindows() 