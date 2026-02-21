"""
Face verification utility module.

Uses DeepFace library for face detection, embedding generation,
and face verification. Supports multiple models (Facenet512, ArcFace, etc.)
and detectors (retinaface, yolov8n, mtcnn, etc.).
"""

import os
import io
import numpy as np
from PIL import Image

# ── Configuration ────────────────────────────────────────────────────

# Model for face recognition (Facenet512 is one of the best performers)
RECOGNITION_MODEL = "Facenet512"

# Detector backend for face detection
DETECTOR_BACKEND = "yolov8n"

# Distance metric for comparison
DISTANCE_METRIC = "cosine"

# Verification threshold (80%)
VERIFICATION_THRESHOLD = 30.0


# ── Core functions ───────────────────────────────────────────────────

def detect_face(image_path_or_pil, is_aadhaar=False):
    """
    Detect the largest face in an image using DeepFace.

    Args:
        image_path_or_pil: File path (str) or PIL Image
        is_aadhaar: Kept for API compatibility

    Returns:
        PIL Image of the cropped face

    Raises:
        ValueError: If no face is detected
    """
    from deepface import DeepFace

    # If PIL Image, save temporarily
    temp_path = None
    if isinstance(image_path_or_pil, Image.Image):
        temp_path = os.path.join(os.path.dirname(__file__), '_temp_detect.jpg')
        image_path_or_pil.convert('RGB').save(temp_path)
        img_path = temp_path
    else:
        img_path = image_path_or_pil

    try:
        face_objs = DeepFace.extract_faces(
            img_path=img_path,
            detector_backend=DETECTOR_BACKEND,
            align=True,
            enforce_detection=True,
        )

        if not face_objs:
            raise ValueError("No face detected in the image.")

        # Get the largest face (highest confidence or largest area)
        best_face = max(face_objs, key=lambda f: f.get("confidence", 0))
        face_array = best_face["face"]  # numpy array (0-1 float)

        # Convert to PIL Image
        face_array = (face_array * 255).astype(np.uint8)
        face_crop = Image.fromarray(face_array)

        return face_crop

    except ValueError:
        raise ValueError("No face detected in the image. Please upload a clearer image.")
    except Exception as e:
        raise ValueError(f"Face detection failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def detect_face_with_coords(img_path: str):
    """
    Detect face and return both the PIL image and its coordinates (x, y, w, h).
    """
    from deepface import DeepFace
    import numpy as np
    from PIL import Image

    face_objs = DeepFace.extract_faces(
        img_path=img_path,
        detector_backend=DETECTOR_BACKEND,
        align=True,
        enforce_detection=True,
    )

    if not face_objs:
        raise ValueError("No face detected.")

    best_face = max(face_objs, key=lambda f: f.get("confidence", 0))
    # Extract the face array
    face_array = best_face["face"]
    # DeepFace returns it as float [0, 1], convert to [0, 255]
    face_array = (face_array * 255).astype(np.uint8)
    face_image = Image.fromarray(face_array)
    
    # facial_area is {'x': 113, 'y': 224, 'w': 286, 'h': 286}
    coords = best_face.get("facial_area", {})
    
    return face_image, coords


def get_face_embedding(face_image: Image.Image) -> np.ndarray:
    """
    Generate a face embedding using DeepFace.

    Args:
        face_image: PIL Image of a face (or full image — DeepFace detects internally)

    Returns:
        numpy array embedding vector
    """
    from deepface import DeepFace

    # Save PIL image to temp file (DeepFace works with file paths)
    temp_path = os.path.join(os.path.dirname(__file__), '_temp_embed.jpg')
    try:
        face_image.convert('RGB').save(temp_path)

        embeddings = DeepFace.represent(
            img_path=temp_path,
            model_name=RECOGNITION_MODEL,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=True,
        )

        if not embeddings:
            raise ValueError("Could not generate face embedding.")

        return np.array(embeddings[0]["embedding"])

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def compute_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Compute cosine similarity between two face embeddings.

    Uses L2-normalized embeddings and direct cosine mapping.

    Args:
        embedding1, embedding2: numpy embedding arrays

    Returns:
        Similarity as a percentage (0-100)
    """
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    emb1_normed = embedding1 / norm1
    emb2_normed = embedding2 / norm2

    cosine_sim = np.dot(emb1_normed, emb2_normed)

    # Clamp to [0, 1] — negative = completely different
    similarity_pct = max(0.0, cosine_sim) * 100

    return round(similarity_pct, 2)


def check_liveness(img_path: str) -> dict:
    """
    Check if a face in an image is real (live person) or fake (photo/screen).
    Uses DeepFace's built-in anti-spoofing model.

    Args:
        img_path: Path to the image to check

    Returns:
        dict with 'is_real', 'antispoof_score', 'message'
    """
    from deepface import DeepFace

    try:
        face_objs = DeepFace.extract_faces(
            img_path=img_path,
            detector_backend=DETECTOR_BACKEND,
            anti_spoofing=True,
            enforce_detection=True,
        )

        if not face_objs:
            return {
                "is_real": False,
                "antispoof_score": 0.0,
                "message": "No face detected in the image."
            }

        # Check the best face
        best_face = max(face_objs, key=lambda f: f.get("confidence", 0))
        is_real = best_face.get("is_real", False)
        antispoof_score = best_face.get("antispoof_score", 0.0)

        return {
            "is_real": bool(is_real),
            "antispoof_score": float(antispoof_score),
            "message": "Live face detected." if is_real else "Spoofing detected! Please use a live face, not a photo or screen."
        }

    except Exception as e:
        # If anti-spoofing fails, log but don't block
        print(f"Warning: Liveness check error: {e}")
        return {
            "is_real": True,  # fail-open to avoid blocking legitimate users
            "antispoof_score": 0.0,
            "message": f"Liveness check unavailable: {str(e)}"
        }


def verify_faces_directly(img1_path: str, img2_path: str) -> dict:
    """
    Use DeepFace.verify() for direct face comparison with liveness check.
    First checks if the webcam image is a live face (not a photo/screen),
    then compares both faces.

    Args:
        img1_path: Path to first image (e.g. Aadhaar face crop)
        img2_path: Path to second image (e.g. webcam capture)

    Returns:
        dict with 'verified', 'similarity', 'distance', 'threshold', 'is_real', 'antispoof_score'
    """
    from deepface import DeepFace

    try:
        # Step 1: Liveness check on webcam image
        liveness = check_liveness(img2_path)
        if not liveness["is_real"]:
            return {
                "verified": False,
                "similarity": 0.0,
                "distance": 1.0,
                "model_threshold": 0.0,
                "model": RECOGNITION_MODEL,
                "is_real": False,
                "antispoof_score": liveness["antispoof_score"],
                "message": liveness["message"],
            }

        # Step 2: Face verification
        result = DeepFace.verify(
            img1_path=img1_path,
            img2_path=img2_path,
            model_name=RECOGNITION_MODEL,
            detector_backend=DETECTOR_BACKEND,
            distance_metric=DISTANCE_METRIC,
            enforce_detection=True,
        )

        # Convert distance to similarity percentage
        distance = result["distance"]
        threshold = result["threshold"]
        similarity = max(0.0, (1 - distance)) * 100

        return {
            "verified": similarity >= VERIFICATION_THRESHOLD,
            "similarity": round(similarity, 2),
            "distance": round(distance, 4),
            "model_threshold": round(threshold, 4),
            "model": result.get("model", RECOGNITION_MODEL),
            "is_real": True,
            "antispoof_score": liveness["antispoof_score"],
        }

    except Exception as e:
        raise ValueError(f"Face verification failed: {str(e)}")


def serialize_embedding(embedding: np.ndarray) -> bytes:
    """Serialize a numpy embedding to bytes for database storage."""
    buffer = io.BytesIO()
    np.save(buffer, embedding)
    return buffer.getvalue()


def deserialize_embedding(data: bytes) -> np.ndarray:
    """Deserialize bytes back to a numpy embedding."""
    buffer = io.BytesIO(data)
    return np.load(buffer)


def verify_face(reference_embedding_bytes: bytes, live_image_path: str, threshold: float = 80.0):
    """
    Full verification pipeline: detect face in live image, embed it,
    and compare with stored reference embedding.

    Args:
        reference_embedding_bytes: Serialized reference embedding from DB
        live_image_path: Path to the live webcam capture image
        threshold: Minimum similarity % to pass (default: 80%)

    Returns:
        tuple: (is_verified: bool, similarity: float)
    """
    ref_embedding = deserialize_embedding(reference_embedding_bytes)

    live_face = detect_face(live_image_path, is_aadhaar=False)
    live_embedding = get_face_embedding(live_face)

    similarity = compute_similarity(ref_embedding, live_embedding)
    is_verified = similarity >= threshold

    return is_verified, similarity
# Cache the OCR reader globally
_ocr_reader = None

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        print("Initializing EasyOCR reader (this may take a moment)...")
        _ocr_reader = easyocr.Reader(['en'], gpu=False)
    return _ocr_reader

def mask_aadhaar_text(image_path: str, face_coords: dict = None) -> Image.Image:
    """
    Detect text on an Aadhaar card using EasyOCR and mask/black it out.
    """
    import cv2
    from PIL import Image
    import numpy as np
    import traceback

    try:
        # Load image using OpenCV
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")
        
        # Get OCR reader
        reader = get_ocr_reader()
        
        # 🟢 FIX: Convert to grayscale for EasyOCR to avoid 'too many values to unpack'
        # Some versions of EasyOCR fail on recognition if passed a 3-channel image directly on some systems
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect text
        print(f"DEBUG: Running OCR on {image_path} (grayscale)...")
        results = reader.readtext(img_gray)
        print(f"DEBUG: OCR found {len(results)} text regions.")
        
        # Apply masking to the COLOR image
        mask_count = 0
        h, w = img.shape[:2]
        
        for res in results:
            try:
                # EasyOCR result format: (bbox, text, confidence)
                if len(res) == 3:
                    bbox, text, prob = res
                elif len(res) == 2:
                    bbox, text = res
                    prob = 1.0
                else:
                    continue

                # bbox is list of 4 corners: [[x,y], [x,y], [x,y], [x,y]]
                # Ensure it's a list/tuple and has 4 points
                if not isinstance(bbox, (list, tuple, np.ndarray)) or len(bbox) != 4:
                    continue
                    
                # Safe unpacking of coordinates
                pts = np.array(bbox).astype(int)
                x_min = int(max(0, np.min(pts[:, 0])))
                y_min = int(max(0, np.min(pts[:, 1])))
                x_max = int(min(w, np.max(pts[:, 0])))
                y_max = int(min(h, np.max(pts[:, 1])))
                
                # Check if this text box overlaps with the face region
                should_mask = True
                if face_coords:
                    fx, fy, fw, fh = face_coords['x'], face_coords['y'], face_coords['w'], face_coords['h']
                    
                    overlap_x = max(0, min(x_max, fx + fw) - max(x_min, fx))
                    overlap_y = max(0, min(y_max, fy + fh) - max(y_min, fy))
                    overlap_area = overlap_x * overlap_y
                    text_area = (x_max - x_min + 1) * (y_max - y_min + 1)
                    
                    if text_area > 0 and (overlap_area / text_area) > 0.3:
                        should_mask = False
                
                if should_mask and x_max > x_min and y_max > y_min:
                    # White out the region on original color image
                    cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (255, 255, 255), -1)
                    mask_count += 1
            except Exception as e:
                print(f"DEBUG: Error processing individual text region: {e}")
                continue

        print(f"DEBUG: Applied {mask_count} masks to Aadhaar card.")

        # Convert back to PIL Image
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)
        
    except Exception as e:
        print(f"DEBUG: mask_aadhaar_text critical failure: {e}")
        print(traceback.format_exc())
        raise e
