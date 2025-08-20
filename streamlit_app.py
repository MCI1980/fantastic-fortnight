import streamlit as st
from pathlib import Path

# ---- App imports (top-level only) ----
from core.rules import analyze_with_goals, DEFAULT_GOALS
from core.report import render_pdf
from capture_guide import get_recs, draw_overlay_grid
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from live_capture import GuideProcessor

# ---- Drill tag mapping: analyzer tags -> drills.yaml tags (TOP-LEVEL) ----
DRILL_TAG_ALIASES = {
    # tempo
    "fast_tempo": "tempo",
    "slow_tempo": "tempo",

    # sway / balance
    "excess_sway": "sway",
    "sway": "sway",
    "loss_of_posture": "balance",

    # rotation / hips / shoulders
    "early_extension": "hips",
    "hip_slide": "hips",
    "flat_shoulder": "shoulders",
    "limited_turn": "rotation",

    # wrists / impact / contact
    "casting": "impact",
    "cupped_wrist": "contact",
    "open_face": "contact",
}

def map_tags_to_drill_tags(analyzer_tags):
    mapped = [DRILL_TAG_ALIASES.get(t, t) for t in (analyzer_tags or [])]
    # de-dupe while keeping order
    seen = set()
    return [x for x in mapped if not (x in seen or seen.add(x))]

def tag_to_drills(tags, drills):
    tagset = set(tags or [])
    return [d for d in drills if tagset & set(d.get("tags", []))]

# ---- Tabs ----
tab_capture, tab_analyze, tab_progress = st.tabs(["Capture", "Analyze", "Progress"])

# =========================
# Capture
# =========================
with tab_capture:
    st.subheader("Capture your swing")

    # Club selection applies to analysis goals
    clubs = ["Driver","3W","Hybrid","Long Iron","Mid Iron","Short Iron","Wedge"]
    club = st.selectbox("Club", clubs, index=0)
    st.session_state["club"] = club

st.markdown("### Live Guided Capture (beta)")

proc_choice = st.radio("Live preview mode", ["Echo test (debug)", "Guide with overlays"], horizontal=True)
proc = EchoTestProcessor if proc_choice.startswith("Echo") else GuideProcessor

rtc_config = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

ctx = webrtc_streamer(
    key="live-guide",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration=rtc_config,
    media_stream_constraints={
        "video": {
            "facingMode": {"ideal": "environment"},  # try "user" if you still see black
            # Optional stability caps:
            # "width": {"ideal": 1280}, "height": {"ideal": 720}, "frameRate": {"ideal": 30}
        },
        "audio": False,
    },
    video_processor_factory=proc,
    async_processing=True,
)

if ctx and ctx.state.playing:
    st.success("Camera streaming…")
else:
    st.info("Waiting for camera permission… tap the camera icon/address bar and Allow. If still blank, switch facingMode to 'user' or try another mobile browser.")
st.divider()

    # 2) Quick Upload (secondary)
    st.markdown("### Quick Upload (existing video)")
    up = st.file_uploader("Upload a swing video", type=["mp4","mov","avi"], key="quick_upload")
    if up:
        st.session_state["uploaded_video"] = up
        st.video(up)
        st.success("Uploaded. Go to the Analyze tab to process it.")

    st.divider()

    # 3) Photo Framing (fallback)
    with st.expander("Photo Framing fallback (if live preview is blocked)"):
        st.caption("Use a photo to check framing, then record with your camera app and upload above.")
        angle = st.radio("Angle", ["FO (Face-On)","DTL (Down-the-Line)"], horizontal=True, key="fallback_angle")
        recs = get_recs("FO" if angle.startswith("FO") else "DTL")
        st.write(f"- Height: **{recs['height_ft'][0]}–{recs['height_ft'][1]} ft**")
        st.write(f"- Distance: **{recs['distance_ft'][0]}–{recs['distance_ft'][1]} ft**")
        for n in recs["notes"]:
            st.write("• " + n)
        photo = st.camera_input("Take a framing photo")
        if photo:
            from PIL import Image
            img = Image.open(photo)
            st.image(draw_overlay_grid(img), caption="Framing guide")

# =========================
# Analyze
# =========================
with tab_analyze:
    club = st.session_state.get("club", "Driver")
    st.subheader("Analyze")
    st.caption(f"Analyzing as: **{club}** (goals adjust by club)")

    # video source (from Capture or upload here)
    video = st.session_state.get("uploaded_video")
    alt_upload = st.file_uploader("Or upload here", type=["mp4","mov","avi"], key="analyze_upload")
    if alt_upload:
        video = alt_upload
        st.session_state["uploaded_video"] = alt_upload

    if video:
        st.video(video)
    else:
        st.warning("No video detected. Use the Capture tab to record or upload a clip.")

    st.divider()
    analyze_now = st.button("Analyze Video", type="primary", use_container_width=True)

    # placeholder analysis until pipeline is wired
    metrics = None
    if analyze_now or (not video):
        metrics = {
            "tempo_ratio": 3.1,
            "head_sway_cm": 5.2,
            "hip_rotation_deg_top": 38,
            "shoulder_rotation_deg_top": 82,
            "lead_wrist_set_deg_top": 60,
            "pelvis_slide_cm": 4.5,
        }

    if metrics:
        # apply club-aware goals if present
        try:
            from core.rules import CLUB_GOALS
            goals = DEFAULT_GOALS.copy()
            goals.update(CLUB_GOALS.get(club, {}))
        except Exception:
            goals = DEFAULT_GOALS

        # Metrics deck
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tempo (B:D)", metrics.get("tempo_ratio"))
        c2.metric("Head sway (cm)", metrics.get("head_sway_cm"))
        c3.metric("Hip rot @Top (°)", metrics.get("hip_rotation_deg_top"))
        c4.metric("Shoulder rot @Top (°)", metrics.get("shoulder_rotation_deg_top"))

        # Pointers from rules
        pointers, tags = analyze_with_goals(metrics, goals)
        st.subheader("Pointers")
        for p in pointers:
            st.write("• " + p)

        # Drills
        try:
            import yaml
            drills = yaml.safe_load((Path(__file__).parent / "drills.yaml").read_text())
            drill_tags = map_tags_to_drill_tags(tags)   # <-- map analyzer tags to drill tags
            st.subheader("Suggested drills")
            suggestions = tag_to_drills(drill_tags, drills)
            if not suggestions:
                st.write("No drills matched. Try uploading a clearer angle or adjust goals.")
            for d in suggestions:
                with st.expander(d["name"]):
                    for i, step in enumerate(d["steps"], start=1):
                        st.write(f"{i}. {step}")
        except Exception as e:
            st.warning(f"Drills unavailable: {e}")

        # Coach Report (includes club)
        st.download_button(
            "Download Coach Report (PDF)",
            data=render_pdf({
                "club": club,
                "video_name": getattr(video, "name", "clip"),
                "metrics": metrics,
                "pointers": pointers
            }),
            file_name="coach_report.pdf",
            mime="application/pdf"
        )

# =========================
# Progress (placeholder)
# =========================
with tab_progress:
    st.info("Progress tracking will live here. For now, focus on Capture → Analyze.")