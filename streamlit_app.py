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

    # --- 1) Live Guided Capture ---
    st.markdown("### Live Guided Capture (beta)")

    proc_choice = st.radio(
        "Live preview mode",
        ["Echo test (debug)", "Guide with overlays"],
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
        angle = st.radio(
            "Angle",
            ["FO (Face-On)", "DTL (Down-the-Line)"],
            horizontal=True,
            key="fallback_angle"
        )
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
# Analyze Tab
# =========================
with tab_analyze:
    club = st.session_state.get("club", "Driver")
    st.subheader("Analyze")
    st.caption(f"Analyzing as: **{club}** (goals adjust by club)")

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
    analyze_now = st.button("Analyze Video", type="primary", use_container_width=True)

    # Placeholder analysis until video_analysis pipeline is wired (Task 2)
    metrics = None
    if analyze_now and video:
        with st.spinner("Analyzing swing..."):
            # TODO: Replace with real analysis from video_analysis module
            metrics = {
                "tempo_ratio": 3.1,
                "head_sway_cm": 5.2,
                "hip_rotation_deg_top": 38,
                "shoulder_rotation_deg_top": 82,
                "lead_wrist_set_deg_top": 60,
                "pelvis_slide_cm": 4.5,
            }
            st.session_state["last_metrics"] = metrics

    # Show metrics if available (from current or previous analysis)
    if metrics is None and "last_metrics" in st.session_state:
        metrics = st.session_state["last_metrics"]

    if metrics:
        # Get club-specific goals
        goals = get_goals_for_club(club)

        # Metrics display
        st.subheader("Metrics")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tempo (B:D)", f"{metrics.get('tempo_ratio', 'N/A')}")
        c2.metric("Head sway", f"{metrics.get('head_sway_cm', 'N/A')} cm")
        c3.metric("Hip rot @Top", f"{metrics.get('hip_rotation_deg_top', 'N/A')}°")
        c4.metric("Shoulder rot @Top", f"{metrics.get('shoulder_rotation_deg_top', 'N/A')}°")

        # Additional metrics row
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Lead wrist", f"{metrics.get('lead_wrist_set_deg_top', 'N/A')}°")
        c6.metric("Pelvis slide", f"{metrics.get('pelvis_slide_cm', 'N/A')} cm")
        c7.write("")  # placeholder
        c8.write("")  # placeholder

        # Pointers from rules engine
        pointers, tags = analyze_with_goals(metrics, goals)

        st.subheader("Coaching Pointers")
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
                        st.write(f"**Equipment:** {', '.join(d['equipment']) or 'None'}")
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
