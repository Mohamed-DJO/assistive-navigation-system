# ---------------- FAVORITE PLACES ----------------
# Edit coordinates to match your real locations.
# Keys are what you say — fuzzy matching handles partial words.

FAVORITE_PLACES = {
    "home":          {"lat": , "lon": , "name": "Home"},
    "university":    {"lat": , "lon": , "name": "University"},
    "hospital":      {"lat": , "lon": , "name": "Hospital"},
    "coffee shop":   {"lat": , "lon": , "name": "Coffee Shop"},
    "restaurant":    {"lat": , "lon": , "name": "Restaurant"},
    "post office":   {"lat": , "lon": , "name": "Post Office"},
    "police station":{"lat": , "lon": , "name": "Police Station"},
    "courthouse":    {"lat": , "lon": , "name": "Courthouse"},
    "primary school":{"lat": , "lon": , "name": "Primary School"},
    "middle school":{"lat": , "lon": , "name": "Middle School"},
    "high school":   {"lat": , "lon": , "name": "High School"},
    "clinic":        {"lat": , "lon": , "name": "Clinic"},
    "airport":       {"lat": , "lon": , "name": "Airport"},
    "metro station":   {"lat": , "lon": , "name": "Metro Station"},
    "bus station":    {"lat": , "lon": , "name": "Bus Station"},
    "lounge station": {"lat": , "lon": , "name": "Lounge Station"},
    "pharmacy":      {"lat": , "lon": , "name": "Pharmacy"},
    "mall":            {"lat": , "lon": , "name": "Mall"},
    "store":           {"lat": , "lon": , "name": "Store"},
    "bakery":          {"lat": , "lon": , "name": "Bakery"},
    "gym":             {"lat": , "lon": , "name": "Gym"},
    "theater":         {"lat": , "lon": , "name": "Theater"},
    "museum":          {"lat": , "lon": , "name": "Museum"},
    "garden":          {"lat": , "lon": , "name": "Garden"},
    "mosque":           {"lat": , "lon": , "name": "Mosque"},
    "barber shop":       {"lat": , "lon": , "name": "Barber Shop"},
    "laundry":           {"lat": , "lon": , "name": "Laundry"},
    "port":              {"lat": , "lon": , "name": "Port"},
    "bank":              {"lat": , "lon": , "name": "Bank"},
    "kindergarten":       {"lat": , "lon": , "name": "Kindergarten"},
    "pastry shop":         {"lat": , "lon": , "name": "Pastry Shop"},
    "beach":              {"lat": , "lon": , "name": "Beach"},
    "vegetable market":     {"lat": , "lon": , "name": "Vegetable Market"},
    "supermarket":         {"lat": , "lon": , "name": "Supermarket"},
    "graveyard":            {"lat": , "lon": , "name": "Graveyard"},
    "fish market":            {"lat": , "lon": , "name": "Fish Market"},
    "chicken shop":            {"lat": , "lon": , "name": "Chicken Shop"},
    "night pharmacy":            {"lat": , "lon": , "name": "Night Pharmacy"},
    "butcher shop":            {"lat": , "lon": , "name": "Butcher Shop"},
    "town hall":            {"lat": , "lon": , "name": "Town Hall"},
    "treasury":            {"lat": , "lon": , "name": "Treasury"},
    "library":            {"lat": , "lon": , "name": "Library"},
    "fire station":            {"lat": , "lon": , "name": "Fire Station"},
    "workplace":            {"lat": , "lon": , "name": "Workplace"},
}


def find_place(command):
    """
    Returns (place_dict, place_key) if a known place is found in the command.
    Uses fuzzy prefix matching so 'hospitality' matches 'hospital',
    'universities' matches 'university', etc.
    Returns (None, None) if no match.
    """
    command = command.lower()

    # First try exact substring match
    for key, place in FAVORITE_PLACES.items():
        if key in command:
            return place, key

    # Then try prefix match (e.g. "hospitality" starts with "hospital")
    words = command.split()
    for word in words:
        for key, place in FAVORITE_PLACES.items():
            key_first_word = key.split()[0]  # e.g. "train" from "train station"
            if word.startswith(key_first_word) or key_first_word.startswith(word):
                return place, key

    return None, None