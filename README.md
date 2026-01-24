# Golf Swing Coach — Streamlit App

A mobile-first golf swing coaching application built with Streamlit. Upload or capture swing videos, get real-time analysis, personalized coaching pointers, and drill recommendations.

## Features

- **Live Capture**: WebRTC-based camera streaming with framing guides
- **Video Analysis**: Pose-based swing metrics (tempo, rotation, sway)
- **Club-Aware Coaching**: Goals adjust based on club selection (Driver → Wedge)
- **Drill Recommendations**: 15+ drills mapped to swing issues
- **Progress Tracking**: Session history and trend visualization (coming soon)

## Project Structure

```
golf-swing-coach/
├── streamlit_app.py          # Main entry point (Streamlit app)
├── requirements.txt          # Python dependencies
├── main.py                   # FastAPI health endpoint (optional)
├── README.md
│
├── coaching/                 # Coaching logic package
│   ├── __init__.py
│   ├── goals.py              # Club-specific goal thresholds
│   ├── drills.py             # Drill tag mapping and loading
│   └── rules.py              # Metrics → pointers rules engine
│
├── video_analysis/           # Video processing package
│   ├── __init__.py
│   └── (pose analysis - Task 2)
│
├── capture/                  # Video capture package
│   ├── __init__.py
│   ├── guide.py              # Framing recommendations
│   └── live.py               # WebRTC video processors
│
├── data/                     # Static data files
│   ├── __init__.py
│   └── drills.yaml           # Drill definitions
│
└── core/                     # Core utilities
    ├── __init__.py
    └── report.py             # PDF report generation
```

## Local Development

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd golf-swing-coach

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run streamlit_app.py
```

The app will open at `http://localhost:8501`.

### Testing Locally

1. **Capture Tab**: Test camera permissions (requires HTTPS or localhost)
2. **Analyze Tab**: Upload a golf swing video (mp4/mov/avi)
3. **Verify**: Check that metrics, pointers, and drills display correctly

## Deployment on Streamlit Cloud

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Set:
   - Main file: `streamlit_app.py`
   - Python version: `3.10`
5. Deploy

### Notes for Streamlit Cloud

- No system packages required (pure Python dependencies)
- WebRTC camera access requires HTTPS (automatic on Streamlit Cloud)
- File storage is ephemeral (progress data resets on redeploy)

## Architecture

### Coaching Module (`coaching/`)

- **goals.py**: Defines `CLUB_GOALS` with thresholds for tempo, sway, rotation per club
- **drills.py**: Maps analyzer tags to drill tags, loads `drills.yaml`
- **rules.py**: `analyze_with_goals()` compares metrics to goals, returns pointers/tags

### Capture Module (`capture/`)

- **guide.py**: Face-On (FO) and Down-the-Line (DTL) framing recommendations
- **live.py**: `GuideProcessor` for real-time framing feedback via WebRTC

### Data Files (`data/`)

- **drills.yaml**: 15+ drills with tags, steps, equipment, difficulty levels

## Adding New Drills

Edit `data/drills.yaml`:

```yaml
- name: "Your Drill Name"
  tags: ["tempo", "balance"]  # Match tags from rules.py
  difficulty: "beginner"
  equipment: ["alignment stick"]
  steps:
    - "Step 1 description"
    - "Step 2 description"
  why: "Explanation of why this drill helps"
```

## Troubleshooting

### Camera Not Working

1. Ensure you're on HTTPS (or localhost)
2. Check browser permissions (address bar lock icon)
3. Try switching from "environment" to "user" camera
4. On iOS Safari, refresh the page after granting permission

### Video Not Playing

- Supported formats: MP4, MOV, AVI
- Max recommended length: 20 seconds
- Ensure video has standard codec (H.264)

## License

MIT License
