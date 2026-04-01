# Best Choice Engine 🏆

A Flask web app that cuts choice overload — shows only the **TOP 3–5** nearby places instead of an endless list.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
python app.py

# 3. Open in browser
http://localhost:5000
```

## How to Use

1. Enter your **Google Places API key** (get one at console.cloud.google.com → Maps → Places API)
2. Allow location access when prompted
3. Select a **category** (Restaurant / Hotel / Hostel / Tiffin Center)
4. Choose a **sort mode** (Best Overall / Budget First / Closest)
5. Click **Find Best Options** → get 3–5 curated picks

## Ranking Algorithm

```
Score = (rating_norm × 0.4)
      + (review_norm × 0.2)
      + (distance_score × 0.2)
      + (price_score × 0.1)
      + (activity_score × 0.1)
```

- **rating_norm**: rating / 5
- **review_norm**: log(reviews+1) / log(10001) — capped at 10k reviews
- **distance_score**: 1 − (dist_m / 3000) — closer = higher
- **price_score**: moderate pricing (level 2) scores 1.0; extreme prices penalised
- **activity_score**: log-normalised review count proxy for recent popularity

## File Structure

```
best-choice-engine/
├── app.py              # Flask backend + ranking logic
├── requirements.txt
├── templates/
│   └── index.html      # Single-page HTML shell
└── static/
    ├── css/style.css   # Dark editorial design
    └── js/app.js       # Frontend logic
```

## API Key Setup (Google Cloud)

1. Go to https://console.cloud.google.com
2. Create a new project
3. Enable **Places API (New)** or **Places API**
4. Create an API key under Credentials
5. (Recommended) Restrict key to your domain / IP
