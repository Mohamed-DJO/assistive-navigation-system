def estimate_distance(real_width, focal_length, pixel_width):
    if pixel_width <= 0:
        return 0.0
    return (real_width * focal_length) / pixel_width


def get_object_position(x_center, frame_width):
    if x_center < frame_width / 3:
        return "on the left"
    elif x_center > 2 * frame_width / 3:
        return "on the right"
    else:
        return "in front"