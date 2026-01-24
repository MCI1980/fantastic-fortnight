# Golf Swing Coach — Streamlit App

A mobile-first golf swing coaching application built with Streamlit. Upload or capture swing videos, get AI-powered pose analysis, personalized coaching pointers, and drill recommendations.

## Features

- **Live Capture**: WebRTC camera streaming with real-time framing guides
- **AI Video Analysis**: MediaPipe Pose detection for swing metrics
- **Club-Aware Coaching**: Goals adjust by club (Driver → Wedge)
- **Smart Drill Recommendations**: 15+ drills mapped to specific issues
- **Progress Tracking**: Session history with trend charts
- **Pro Integrations**: Architecture ready for TrackMan, Bushnell (coming soon)

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd golf-swing-coach
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run locally
streamlit run streamlit_app.py
```

Open `http://localhost:8501` in your browser.

## Project Structure

```
golf-swing-coach/
├── streamlit_app.py          # Main Streamlit application
├── requirements.txt          # Python dependencies
├── README.md
│
├── coaching/                 # Coaching logic
│   ├── goals.py              # Club-specific thresholds
│   ├── drills.py             # Drill loading and matching
│   └── rules.py              # Metrics → pointers engine
│
├── video_analysis/           # AI pose analysis
│   ├── pose.py               # MediaPipe wrapper
│   ├── metrics.py            # Swing phase detection
│   └── analyzer.py           # Main analysis pipeline
│
├── capture/                  # Video capture
│   ├── guide.py              # Framing recommendations
│   └── live.py               # WebRTC processors
│
├── data/                     # Data storage
│   ├── drills.yaml           # Drill definitions
│   └── sessions.py           # Session storage
│
├── integrations/             # Pro features (placeholder)
│   ├── base.py               # Data contracts
│   ├── trackman.py           # TrackMan connector
│   └── bushnell.py           # Bushnell connector
│
├── core/                     # Utilities
│   └── report.py             # PDF report generation
│
└── tests/                    # Test suite
    ├── test_coaching.py      # Coaching rules tests
    └── sample_metrics.json   # Test data
```

## Local Development

### Prerequisites

- Python 3.10+
- pip or pipenv
- Webcam (optional, for live capture)

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run streamlit_app.py
```

### Running Tests

```bash
# Install test dependencies
pip install pytest

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_coaching.py -v
```

### Testing Locally

1. **Capture Tab**:
   - Select club and camera angle (FO/DTL)
   - Test live preview (requires localhost for camera)
   - Or upload an existing video

2. **Analyze Tab**:
   - Upload golf swing video (MP4/MOV/AVI, max 20s)
   - Click "Analyze Video"
   - Review metrics, pointers, and drills
   - Save session to track progress

3. **Progress Tab**:
   - View saved sessions
   - Filter by club/angle
   - Check trend charts

## Deployment on Streamlit Cloud

### Steps

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Configure:
   - **Main file**: `streamlit_app.py`
   - **Python version**: `3.10`
5. Click Deploy

### Streamlit Cloud Notes

- ✅ Pure Python dependencies (no system packages needed)
- ✅ WebRTC works (HTTPS automatic)
- ⚠️ File storage is ephemeral (sessions reset on redeploy)
- ⚠️ Use "Export Sessions" to backup progress data

### Environment Variables (Optional)

For pro integrations (when available):
```
TRACKMAN_CLIENT_ID=xxx
TRACKMAN_CLIENT_SECRET=xxx
BUSHNELL_API_KEY=xxx
```

## Video Analysis

### Supported Formats

- MP4, MOV, AVI
- H.264 codec recommended
- Maximum duration: 20 seconds
- Target: 60 FPS (30+ recommended)

### Metrics Computed

| Metric | Description | Good Range |
|--------|-------------|------------|
| Tempo Ratio | Backswing:Downswing frames | 2.5-3.5 |
| Head Sway | Horizontal head movement | <4cm (Driver) |
| Hip Rotation | Hip line angle at top | >40° (Driver) |
| Shoulder Rotation | Shoulder line angle at top | >85° (Driver) |
| Lead Wrist Set | Wrist hinge at top | 50-90° |
| Pelvis Slide | Hip center lateral movement | <5cm |

### Confidence Levels

- 🟢 **High**: Clear pose detection, reliable metrics
- 🟡 **Medium**: Some frames unclear, metrics approximate
- 🔴 **Low**: Poor detection, use results with caution

## Troubleshooting

### Camera Not Working

**iOS Safari:**
1. Tap "Aa" in address bar → Website Settings → Allow Camera
2. Refresh the page after granting permission
3. Must be on HTTPS (automatic on Streamlit Cloud)

**Android Chrome:**
1. Tap lock icon → Permissions → Camera → Allow
2. Try switching between "Back camera" and "Front camera"

**Desktop:**
1. Click camera icon in address bar
2. Select "Allow" and refresh if needed

### Video Analysis Fails

- Ensure full body is visible (head to feet)
- Use good lighting (avoid strong backlight)
- Keep camera steady (tripod recommended)
- Include complete swing (address → finish)
- Avoid very baggy clothing
- Keep video under 20 seconds

### Session Data Lost

Streamlit Cloud has ephemeral storage. To preserve data:
1. Go to Progress tab
2. Click "Export Sessions (JSON)"
3. Save the file locally

## Adding New Drills

Edit `data/drills.yaml`:

```yaml
- name: "Your Drill Name"
  tags: ["tempo", "balance"]
  difficulty: "beginner"
  equipment: ["alignment stick"]
  steps:
    - "Step 1 description"
    - "Step 2 description"
  why: "Why this drill helps"
```

Available tags: `tempo`, `sway`, `balance`, `hips`, `shoulders`, `rotation`, `contact`, `impact`

## Performance Limits

| Limit | Value | Reason |
|-------|-------|--------|
| Max video duration | 20 seconds | Memory & processing time |
| Target analysis FPS | 15 | Balance speed vs accuracy |
| Session history | 100 recent | Storage efficiency |
| Drills per pointer | 3 | UI clarity |

## API / Integration Notes

The `integrations/` package provides placeholder connectors for:

- **TrackMan**: Launch monitor data (club speed, ball speed, spin)
- **Bushnell Launch Pro**: Portable launch monitor integration
- **FlightScope**: Mevo and X3 radar units
- **Arccos/Garmin**: Round tracking and stats

These are **not yet functional** but define the data contracts and architecture for future implementation.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## License

MIT License

## Acknowledgments

- [MediaPipe](https://mediapipe.dev/) for pose detection
- [Streamlit](https://streamlit.io/) for the web framework
- [streamlit-webrtc](https://github.com/whitphx/streamlit-webrtc) for camera access
