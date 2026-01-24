# streamlit_app.py
# Main entry point for the Golf Swing Coach application

import streamlit as st
from pathlib import Path

# ---- Package imports ----
from coaching import (
    analyze_with_goals,
    CLUB_GOALS,
    DEFAULT_GOALS,
    map_tags_to_drill_tags,
    tag_to_drills,
    load_drills,
)
from coaching.goals import get_goals_for_club
from capture import get_recs, draw_overlay_grid, GuideProcessor, EchoTestProcessor
from core.report import render_pdf

# Video analysis import (with graceful fallback)
try:
    from video_analysis import analyze_swing_video, AnalysisResult
    VIDEO_ANALYSIS_AVAILABLE = True
except ImportError:
    VIDEO_ANALYSIS_AVAILABLE = False
    AnalysisResult = None

# WebRTC imports
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

# ---- Page Config ----
st.set_page_config(
    page_title="Golf Swing Coach",
    page_icon="⛳",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---- Tabs ----
tab_capture, tab_analyze, tab_progress = st.tabs(["Capture", "Analyze", "Progress"])

# =========================
# Capture Tab
# =========================
with tab_capture:
    st.subheader("Capture your swing")

    # --- Club selection ---
    clubs = ["Driver", "3W", "Hybrid", "Long Iron", "Mid Iron", "Short Iron", "Wedge"]
    club = st.selectbox("Club", clubs, index=0)
    st.session_state["club"] = club

    # --- Camera angle selection ---
    angle_choice = st.radio(
        "Camera angle",
        ["FO (Face-On)", "DTL (Down-the-Line)"],
        horizontal=True,
        help="Face-On: camera perpendicular to target line. Down-the-Line: camera behind on hand line."
    )
    st.session_state["angle"] = "FO" if angle_choice.startswith("FO") else "DTL"

    # --- 1) Live Guided Capture ---
    st.markdown("### Live Guided Capture (beta)")

    proc_choice = st.radio(
        "Live preview mode",
        ["Guide with overlays", "Echo test (debug)"],
        horizontal=True
    )
    proc = EchoTestProcessor if proc_choice.startswith("Echo") else GuideProcessor

    rtc_config = RTCConfiguration({
        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    })

    ctx = webrtc_streamer(
        key="live-guide",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=rtc_config,
        media_stream_constraints={
            "video": {"facingMode": {"ideal": "environment"}},  # back camera
            "audio": False,
        },
        video_processor_factory=proc,
        async_processing=True,
    )

    if ctx and ctx.state.playing:
        st.success("Camera streaming...")
    else:
        st.info(
            "Waiting for camera permission... tap the camera icon/address bar and Allow. "
            "If still blank, switch facingMode to 'user' or try another mobile browser."
        )

    st.divider()

    # --- 2) Quick Upload ---
    st.markdown("### Quick Upload (existing video)")
    up = st.file_uploader("Upload a swing video", type=["mp4", "mov", "avi"], key="quick_upload")
    if up:
        st.session_state["uploaded_video"] = up
        st.video(up)
        st.success("Uploaded. Go to the Analyze tab to process it.")

    st.divider()

    # --- 3) Photo Framing (fallback) ---
    with st.expander("Photo Framing fallback (if live preview is blocked)"):
        st.caption("Use a photo to check framing, then record with your camera app and upload above.")
        recs = get_recs(st.session_state.get("angle", "FO"))
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
# Analyze Tab
# =========================
with tab_analyze:
    club = st.session_state.get("club", "Driver")
    angle = st.session_state.get("angle", "FO")

    st.subheader("Analyze")

    # Summary card
    col1, col2 = st.columns(2)
    col1.markdown(f"**Club:** {club}")
    col2.markdown(f"**Angle:** {angle}")

    # Video source (from Capture or upload here)
    video = st.session_state.get("uploaded_video")
    alt_upload = st.file_uploader("Or upload here", type=["mp4", "mov", "avi"], key="analyze_upload")
    if alt_upload:
        video = alt_upload
        st.session_state["uploaded_video"] = alt_upload

    if video:
        st.video(video)
    else:
        st.warning("No video detected. Use the Capture tab to record or upload a clip.")

    st.divider()

    # Handedness selection
    hand_col1, hand_col2 = st.columns([3, 1])
    with hand_col2:
        handedness = st.selectbox("Handedness", ["Right", "Left"], index=0)
        st.session_state["handedness"] = handedness.lower()

    analyze_now = st.button("Analyze Video", type="primary", use_container_width=True)

    # Analysis state
    metrics = None
    keyframes = {}
    confidence = "low"
    analysis_error = None

    if analyze_now and video:
        if VIDEO_ANALYSIS_AVAILABLE:
            with st.spinner("Analyzing swing with AI pose detection..."):
                try:
                    # Reset video file position
                    video.seek(0)

                    # Run real video analysis
                    result = analyze_swing_video(
                        video_file=video,
                        angle=angle,
                        handedness=st.session_state.get("handedness", "right"),
                        target_fps=15.0
                    )

                    if result.success:
                        metrics = result.to_metrics_dict()
                        keyframes = result.keyframes
                        confidence = result.overall_confidence

                        # Store in session state
                        st.session_state["last_metrics"] = metrics
                        st.session_state["last_keyframes"] = keyframes
                        st.session_state["last_confidence"] = confidence
                        st.session_state["analysis_info"] = {
                            "frames_processed": result.frames_processed,
                            "frames_with_pose": result.frames_with_pose,
                            "duration_sec": result.duration_sec,
                            "fps": result.fps,
                        }
                    else:
                        analysis_error = result.error_message

                except Exception as e:
                    analysis_error = f"Analysis error: {str(e)}"
        else:
            # Fallback to placeholder metrics if video analysis not available
            st.warning("Video analysis module not available. Showing placeholder data.")
            metrics = {
                "tempo_ratio": 3.1,
                "head_sway_cm": 5.2,
                "hip_rotation_deg_top": 38,
                "shoulder_rotation_deg_top": 82,
                "lead_wrist_set_deg_top": 60,
                "pelvis_slide_cm": 4.5,
            }
            confidence = "low"
            st.session_state["last_metrics"] = metrics
            st.session_state["last_confidence"] = confidence

    # Show error if analysis failed
    if analysis_error:
        st.error(analysis_error)
        with st.expander("Tips for better analysis"):
            st.markdown("""
            - **Full body visible**: Ensure your entire body is in frame from head to feet
            - **Good lighting**: Avoid strong backlight; even indoor lighting works
            - **Steady camera**: Use a tripod or stable surface
            - **Complete swing**: Include address through finish in the video
            - **Appropriate clothing**: Avoid very baggy clothes that obscure body shape
            - **Video length**: Keep videos under 20 seconds
            """)

    # Show metrics if available (from current or previous analysis)
    if metrics is None and "last_metrics" in st.session_state:
        metrics = st.session_state.get("last_metrics")
        keyframes = st.session_state.get("last_keyframes", {})
        confidence = st.session_state.get("last_confidence", "low")

    if metrics:
        # Get club-specific goals
        goals = get_goals_for_club(club)

        # Confidence indicator
        confidence_colors = {"high": "🟢", "medium": "🟡", "low": "🔴"}
        st.caption(f"{confidence_colors.get(confidence, '⚪')} Detection confidence: **{confidence}**")

        if confidence == "low":
            st.warning("Low confidence detection. Results may be less accurate. See tips above.")

        # Keyframe images
        if keyframes:
            st.subheader("Key Positions")
            kf_cols = st.columns(len(keyframes))
            for i, (phase, img) in enumerate(keyframes.items()):
                with kf_cols[i]:
                    st.image(img, caption=phase.capitalize(), use_container_width=True)

        # Metrics display
        st.subheader("Metrics")

        # Show estimated label for metrics
        st.caption("*Metrics are estimated from video pose detection and may vary from professional launch monitors.*")

        c1, c2, c3, c4 = st.columns(4)

        tempo = metrics.get('tempo_ratio')
        c1.metric(
            "Tempo (B:D)",
            f"{tempo}" if tempo else "N/A",
            help="Backswing:Downswing frame ratio. Tour avg: 3.0"
        )

        sway = metrics.get('head_sway_cm')
        c2.metric(
            "Head sway",
            f"{sway} cm" if sway else "N/A",
            help="Horizontal head movement from address to top"
        )

        hip = metrics.get('hip_rotation_deg_top')
        c3.metric(
            "Hip rot @Top",
            f"{hip}°" if hip else "N/A",
            help="Hip line angle at top of backswing"
        )

        shoulder = metrics.get('shoulder_rotation_deg_top')
        c4.metric(
            "Shoulder rot @Top",
            f"{shoulder}°" if shoulder else "N/A",
            help="Shoulder line angle at top of backswing"
        )

        # Additional metrics row
        c5, c6, c7, c8 = st.columns(4)

        wrist = metrics.get('lead_wrist_set_deg_top')
        c5.metric(
            "Lead wrist",
            f"{wrist}°" if wrist else "N/A",
            help="Lead arm bend at top (wrist hinge estimate)"
        )

        pelvis = metrics.get('pelvis_slide_cm')
        c6.metric(
            "Pelvis slide",
            f"{pelvis} cm" if pelvis else "N/A",
            help="Hip center lateral movement"
        )

        # Analysis info
        if "analysis_info" in st.session_state:
            info = st.session_state["analysis_info"]
            c7.metric("Frames", f"{info.get('frames_with_pose', 0)}/{info.get('frames_processed', 0)}")
            c8.metric("Duration", f"{info.get('duration_sec', 0):.1f}s")

        # Pointers from rules engine
        pointers, tags = analyze_with_goals(metrics, goals)

        st.subheader("Coaching Pointers")

        if confidence == "low":
            st.caption("*Lower confidence - take these suggestions with a grain of salt.*")

        for p in pointers:
            st.write("• " + p)

        # Drills from YAML
        drills = load_drills()
        if drills:
            drill_tags = map_tags_to_drill_tags(tags)
            suggestions = tag_to_drills(drill_tags, drills)

            st.subheader("Suggested Drills")
            if not suggestions:
                st.info("No specific drills needed - your fundamentals look good!")
            for d in suggestions:
                with st.expander(f"🏌️ {d['name']} ({d.get('difficulty', 'all levels')})"):
                    if d.get("why"):
                        st.caption(f"**Why:** {d['why']}")
                    if d.get("equipment"):
                        equip = d['equipment']
                        equip_str = ', '.join(equip) if equip else 'None'
                        st.write(f"**Equipment:** {equip_str}")
                    st.write("**Steps:**")
                    for i, step in enumerate(d.get("steps", []), start=1):
                        st.write(f"{i}. {step}")
        else:
            st.warning("Drills database not found.")

        # Coach Report download
        st.divider()
        st.download_button(
            "Download Coach Report (PDF)",
            data=render_pdf({
                "club": club,
                "video_name": getattr(video, "name", "clip"),
                "metrics": metrics,
                "pointers": pointers,
            }),
            file_name="coach_report.pdf",
            mime="application/pdf",
        )

# =========================
# Progress Tab (placeholder - Task 5)
# =========================
with tab_progress:
    st.subheader("Progress Tracking")
    st.info(
        "Progress tracking will be implemented soon. "
        "For now, focus on Capture → Analyze to improve your swing."
    )
    st.caption("Coming: Session history, trend charts, and improvement tracking.")
