import numpy as np
from ultralytics import YOLO
import supervision as sv
from vision.vision_utils import estimate_distance, get_object_position

# ---------------- CONFIG ----------------
# best502n.pt
OBJ_WIDTHS = {
    "bicycle": 0.6,
    "bottle": 0.08,
    "bus": 2.5,
    "car": 1.8,
    "cat": 0.2,
    "cell_phone": 0.07,
    "chair": 0.5,
    "construction_barrier": 0.3,
    "crosswalk": 0.5,
    "dining_table": 0.8,
    "dog": 0.4,
    "door": 0.9,
    "hole": 0.5,
    "motorcycle": 0.7,
    "person": 0.5,
    "stairs": 1.0,
    "stop_sign": 0.5,
    "traffic_cone": 0.2,
    "traffic_light": 0.3,
    "train": 3.0,
    "tree": 1.0,
    "truck": 2.5,
    "window": 1.0,
}

USEFUL_CLASSES = list(OBJ_WIDTHS.keys())
CONFIDENCE_THRESHOLD = 0.6
FOCAL_LENGTH = 650

# ---------------- GLOBALS ----------------
_model = None
_box_annotator = None
_label_annotator = None


# ---------------- CORE ----------------
def init_model(model_path="models/best502n.pt"):
    global _model, _box_annotator, _label_annotator

    if _model is None:
        _model = YOLO(model_path)
        _box_annotator = sv.BoxAnnotator(thickness=2)
        _label_annotator = sv.LabelAnnotator(text_scale=0.5)


def analyze_frame(frame):
    """
    Detect objects in a frame and return annotated frame + object list.

    Returns:
        annotated_frame (np.ndarray): Frame with bounding boxes drawn.
        objects (list[dict]): List of detected objects with name, distance, position, confidence.
    """
    global _model, _box_annotator, _label_annotator

    if _model is None:
        init_model()

    result = _model(frame, imgsz=320, verbose=False)[0]

    try:
        detections = sv.Detections.from_ultralytics(result)
    except AttributeError:
        detections = sv.Detections.from_yolov8(result)

    frame_h, frame_w, _ = frame.shape
    objects = []
    filtered_xyxy = []
    filtered_conf = []
    filtered_class_id = []

    for i in range(len(detections.xyxy)):
        xyxy = detections.xyxy[i]
        conf = float(detections.confidence[i])
        class_id = int(detections.class_id[i])
        class_name = _model.model.names[class_id]

        if class_name not in USEFUL_CLASSES or conf < CONFIDENCE_THRESHOLD:
            continue

        x1, y1, x2, y2 = xyxy
        pixel_width = x2 - x1
        x_center = (x1 + x2) / 2

        if pixel_width <= 0:
            continue

        dist = estimate_distance(OBJ_WIDTHS[class_name], FOCAL_LENGTH, pixel_width)
        pos = get_object_position(x_center, frame_w)

        objects.append({
            "name": class_name,
            "distance": float(round(dist, 2)),
            "position": pos,
            "confidence": float(round(conf, 2)),
        })

        filtered_xyxy.append(xyxy)
        filtered_conf.append(conf)
        filtered_class_id.append(class_id)

    if not objects:
        return frame.copy(), objects

    new_detections = sv.Detections(
        xyxy=np.array(filtered_xyxy, dtype=np.float32),
        confidence=np.array(filtered_conf, dtype=np.float32),
        class_id=np.array(filtered_class_id, dtype=np.int32),
    )

    labels = [
        f"{obj['name']} {obj['distance']:.2f}m {obj['confidence']:.2f}"
        for obj in objects
    ]

    annotated_frame = frame.copy()
    annotated_frame = _box_annotator.annotate(
        scene=annotated_frame,
        detections=new_detections
    )
    annotated_frame = _label_annotator.annotate(
        scene=annotated_frame,
        detections=new_detections,
        labels=labels
    )

    return annotated_frame, objects
