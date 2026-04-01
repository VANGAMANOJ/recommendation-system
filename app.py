"""
Best Choice Engine - Flask Backend
Fetches nearby places from Google Places API, scores them using a weighted
ranking algorithm, and returns only the TOP 3-5 best options.
"""

from flask import Flask, render_template, request, jsonify
import requests
import math
import os

app = Flask(__name__)

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
PLACES_API_BASE = "https://maps.googleapis.com/maps/api/place"

# Category → Google Places type mapping
CATEGORY_TYPES = {
    "hotel":        "lodging",
    "restaurant":   "restaurant",
    "hostel":       "lodging",          # refined by keyword
    "tiffin":       "restaurant",       # refined by keyword
}

CATEGORY_KEYWORDS = {
    "hotel":      "hotel",
    "restaurant": "restaurant",
    "hostel":     "hostel",
    "tiffin":     "tiffin center",
}

# Search radius in metres
SEARCH_RADIUS = 3000

# -------------------------------------------------------------------
# RANKING ALGORITHM
# -------------------------------------------------------------------
def distance_score(dist_m: float, max_dist: float = SEARCH_RADIUS) -> float:
    """Closer = higher score (0–1)."""
    return max(0.0, 1.0 - (dist_m / max_dist))


def price_score(price_level) -> float:
    """
    Moderate pricing preferred (price_level 2 = best).
    0 = free/unknown, 1 = cheap, 2 = moderate, 3 = expensive, 4 = very expensive
    """
    if price_level is None:
        return 0.5   # neutral when unknown
    mapping = {0: 0.6, 1: 0.8, 2: 1.0, 3: 0.6, 4: 0.3}
    return mapping.get(int(price_level), 0.5)


def activity_score(user_ratings_total: int) -> float:
    """
    Proxy for recent popularity: normalised log of review count.
    log(1001) ≈ 6.9  → treated as cap
    """
    return min(1.0, math.log(user_ratings_total + 1) / math.log(1001))


def rank_place(place: dict, user_lat: float, user_lng: float) -> float:
    """
    Score = (rating * 0.4)
           + (log(review_count+1) * 0.2)   ← normalised to 0–1
           + (distance_score * 0.2)
           + (price_score * 0.1)
           + (activity_score * 0.1)
    """
    rating        = place.get("rating", 0) / 5.0          # normalise to 0–1
    reviews       = place.get("user_ratings_total", 0)
    review_norm   = min(1.0, math.log(reviews + 1) / math.log(10001))  # cap 10k
    dist_m        = haversine(user_lat, user_lng,
                              place["geometry"]["location"]["lat"],
                              place["geometry"]["location"]["lng"])
    dist_s        = distance_score(dist_m)
    price_s       = price_score(place.get("price_level"))
    act_s         = activity_score(reviews)

    score = (rating * 0.4
             + review_norm * 0.2
             + dist_s * 0.2
             + price_s * 0.1
             + act_s * 0.1)

    # Store for later use
    place["_score"]   = round(score, 4)
    place["_dist_m"]  = round(dist_m)
    return score


def haversine(lat1, lng1, lat2, lng2) -> float:
    """Return distance in metres between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlam       = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# -------------------------------------------------------------------
# EXPLANATION TAGS
# -------------------------------------------------------------------
def explain(place: dict, ranked: list) -> str:
    """Assign a human-readable reason tag to a top-ranked place."""
    rating  = place.get("rating", 0)
    reviews = place.get("user_ratings_total", 0)
    dist    = place["_dist_m"]
    price   = place.get("price_level")

    # Best overall = highest score in list
    if place is ranked[0]:
        return "⭐ Best Overall"

    # Best budget = lowest price level and still good
    cheapest = min((p for p in ranked if p.get("price_level") is not None),
                   key=lambda p: p.get("price_level", 99), default=None)
    if cheapest and place is cheapest and (price or 99) <= 1:
        return "💰 Best Budget Option"

    # Most reviewed
    most_reviewed = max(ranked, key=lambda p: p.get("user_ratings_total", 0))
    if place is most_reviewed and reviews > 100:
        return "🔥 Most Popular"

    # Closest
    closest = min(ranked, key=lambda p: p["_dist_m"])
    if place is closest and dist < 800:
        return "📍 Closest Good Option"

    # Highly rated
    if rating >= 4.5:
        return "🏆 Top Rated"

    if dist <= 500:
        return "📍 Closest Good Option"

    if (price or 99) <= 1:
        return "💰 Budget-Friendly"

    return "✅ Highly Recommended"


# -------------------------------------------------------------------
# PLACES API HELPERS
# -------------------------------------------------------------------
def fetch_nearby(api_key: str, lat: float, lng: float,
                 category: str) -> list:
    """Call Google Places Nearby Search and return raw results."""
    place_type = CATEGORY_TYPES.get(category, "establishment")
    keyword    = CATEGORY_KEYWORDS.get(category, category)

    params = {
        "location": f"{lat},{lng}",
        "radius":   SEARCH_RADIUS,
        "type":     place_type,
        "keyword":  keyword,
        "key":      api_key,
    }
    resp = requests.get(f"{PLACES_API_BASE}/nearbysearch/json",
                        params=params, timeout=8)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        raise ValueError(f"Places API error: {data.get('status')} – "
                         f"{data.get('error_message', '')}")

    return data.get("results", [])


def build_maps_url(place_id: str) -> str:
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


def format_distance(dist_m: int) -> str:
    if dist_m < 1000:
        return f"{dist_m} m"
    return f"{dist_m/1000:.1f} km"


# -------------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    body = request.get_json(force=True)
    api_key  = body.get("api_key", "").strip()
    lat      = body.get("lat")
    lng      = body.get("lng")
    category = body.get("category", "restaurant").lower()
    filter_  = body.get("filter", "best")   # best | budget | closest

    # Validate inputs
    if not api_key:
        return jsonify({"error": "Google API key is required."}), 400
    if lat is None or lng is None:
        return jsonify({"error": "Location is required."}), 400

    try:
        raw = fetch_nearby(api_key, lat, lng, category)
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {str(e)}"}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not raw:
        return jsonify({"results": [], "message": "No places found nearby."}), 200

    # Filter out low-quality results
    qualified = [p for p in raw if p.get("rating", 0) >= 3.5
                 and not p.get("permanently_closed")]

    if not qualified:
        return jsonify({"results": [],
                        "message": "No highly-rated places found. Try a wider area."}), 200

    # Score every place
    for p in qualified:
        rank_place(p, lat, lng)

    # Apply user filter
    if filter_ == "budget":
        qualified.sort(key=lambda p: (p.get("price_level") or 99,
                                      -p["_score"]))
    elif filter_ == "closest":
        qualified.sort(key=lambda p: p["_dist_m"])
    else:  # best (default)
        qualified.sort(key=lambda p: -p["_score"])

    top = qualified[:5]   # keep TOP 5

    # Assign explanation tags (pass sorted top list)
    for p in top:
        p["_tag"] = explain(p, top)

    # Serialize response
    results = []
    for p in top:
        results.append({
            "place_id":   p.get("place_id"),
            "name":       p.get("name"),
            "rating":     p.get("rating"),
            "reviews":    p.get("user_ratings_total", 0),
            "distance":   format_distance(p["_dist_m"]),
            "price_level": p.get("price_level"),
            "tag":        p["_tag"],
            "address":    p.get("vicinity", ""),
            "open_now":   p.get("opening_hours", {}).get("open_now"),
            "maps_url":   build_maps_url(p["place_id"]),
            "score":      p["_score"],
            "photo_ref":  (p.get("photos") or [{}])[0].get("photo_reference"),
        })

    return jsonify({"results": results, "total_found": len(qualified)})


@app.route("/api/photo")
def photo_proxy():
    """Proxy Google Places photo to avoid CORS issues."""
    ref = request.args.get("ref")
    api_key = request.args.get("key")
    if not ref or not api_key:
        return "", 400
    url = (f"{PLACES_API_BASE}/photo"
           f"?maxwidth=400&photo_reference={ref}&key={api_key}")
    resp = requests.get(url, timeout=8, allow_redirects=True)
    return resp.content, resp.status_code, {
        "Content-Type": resp.headers.get("Content-Type", "image/jpeg")
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000)
