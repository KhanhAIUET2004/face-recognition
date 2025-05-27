# app/face_utils.py
import face_recognition # The actual library
import numpy as np
from PIL import Image
import io
from typing import List, Tuple, Optional

# Default tolerance, can be adjusted
RECOGNITION_TOLERANCE = 0.5 # CLI uses 0.6, 0.5 is a bit stricter

def load_image_into_numpy_array(data: bytes) -> np.ndarray:
    """Loads an image file into a numpy array."""
    try:
        image = Image.open(io.BytesIO(data))
        # Convert to RGB if not already (e.g., PNGs with alpha, grayscale)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        # Optional: Resize like in the CLI script if images are very large
        # if max(image.size) > 1600:
        #     image.thumbnail((1600, 1600), Image.Resampling.LANCZOS) # Note: PIL.Image.LANCZOS for newer Pillow
        return np.array(image)
    except Exception as e:
        # Log the error e
        raise ValueError(f"Could not load image: {e}")


def get_face_encodings_from_image(image_np: np.ndarray) -> List[np.ndarray]:
    """
    Returns a list of 128-dimension face encodings from an image.
    Returns an empty list if no faces are found.
    """
    # model="cnn" is more accurate but slower. Default "hog" is faster.
    face_locations = face_recognition.face_locations(image_np) # You can specify model="cnn"
    if not face_locations:
        return []
    face_encodings = face_recognition.face_encodings(image_np, known_face_locations=face_locations)
    return face_encodings


def find_best_match(
    unknown_encoding: np.ndarray,
    known_encodings: List[np.ndarray],
    known_names: List[str],
    tolerance: float = RECOGNITION_TOLERANCE
) -> Tuple[Optional[str], Optional[float]]:
    """
    Finds the best match for an unknown encoding against a list of known encodings.

    Returns:
        A tuple (name, distance). (None, None) if no match found within tolerance.
        If multiple matches are within tolerance, returns the one with the smallest distance.
    """
    if not known_encodings:
        return None, None

    # Calculate distances from the unknown encoding to all known encodings
    distances = face_recognition.face_distance(known_encodings, unknown_encoding)

    best_match_name: Optional[str] = None
    min_distance: float = float('inf')

    for i, distance in enumerate(distances):
        if distance <= tolerance and distance < min_distance:
            min_distance = distance
            best_match_name = known_names[i]

    if best_match_name:
        return best_match_name, min_distance
    return None, None # No match found within tolerance