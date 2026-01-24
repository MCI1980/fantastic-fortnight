# streamlit_app.py
# Main entry point for the Golf Swing Coach application

import streamlit as st
from pathlib import Path

# ---- Package imports ----
from coaching import (
    analyze_with_goals,
    analyze_with_goals_detailed,
    get_pointer_drills,
    CLUB_GOALS,
    DEFAULT_GOALS,
    map_tags_to_drill_tags,
    tag_to_drills,
    load_drills,
    get_goals_for_club,
)
from capture import get_recs, draw_overlay_grid, GuideProcessor, EchoTestProcessor, create_guide_processor
from core.report import render_pdf

# Video analysis import (with graceful fallback)
try:
    from video_analysis import analyze_swing_video, AnalysisResult
    VIDEO_ANALYSIS_AVAILABLE = True
except ImportError:
    VIDEO_ANALYSIS_AVAILABLE = False
    AnalysisResult = None

# Session storage import
from data import Session, get_session_store

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

    # --- Setup section ---
    setup_col1, setup_col2 = st.columns(2)

    with setup_col1:
        # Club selection
        clubs = ["Driver", "3W", "Hybrid", "Long Iron", "Mid Iron", "Short Iron", "Wedge"]
        club = st.selectbox("Club", clubs, index=0)
        st.session_state["club"] = club

    with setup_col2:
        # Camera angle selection
        angle_choice = st.radio(
            "Camera angle",
            ["FO (Face-On)", "DTL (Down-the-Line)"],
            horizontal=True,
        )
        angle = "FO" if angle_choice.startswith("FO") else "DTL"
        st.session_state["angle"] = angle

    # --- Angle-specific setup guidance ---
    recs = get_recs(angle)
    with st.expander(f"Setup Guide for {angle_choice}", expanded=True):
        guide_col1, guide_col2 = st.columns(2)

        with guide_col1:
            st.markdown("**Camera Position:**")
            st.write(f"- Height: {recs['height_ft'][0]}–{recs['height_ft'][1]} ft")
            st.write(f"- Distance: {recs['distance_ft'][0]}–{recs['distance_ft'][1]} ft")

        with guide_col2:
            st.markdown("**Checklist:**")
            st.write("✓ Full body in frame (head to feet)")
            st.write("✓ Golfer centered in frame")
            st.write("✓ Good lighting (no backlight)")
            st.write("✓ Landscape orientation")
            st.write("✓ 60 FPS if possible")

        st.caption("**Tips:** " + " | ".join(recs["notes"][:2]))

    st.divider()

    # --- 1) Live Guided Capture ---
    st.markdown("### Live Guided Capture")
    st.caption("Real-time framing feedback. Green = ready, Orange = adjust position.")

    # Create angle-aware processor
    processor_factory = create_guide_processor(angle)

    rtc_config = RTCConfiguration({
        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    })

    # Camera preference
    camera_mode = st.radio(
        "Camera",
        ["Back camera", "Front camera"],
        horizontal=True,
        help="Back camera recommended. Use front if back doesn't work."
    )
    facing_mode = "environment" if camera_mode == "Back camera" else "user"

    ctx = webrtc_streamer(
        key=f"live-guide-{angle}-{facing_mode}",  # Key changes with angle/camera
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=rtc_config,
        media_stream_constraints={
            "video": {"facingMode": {"ideal": facing_mode}},
            "audio": False,
        },
        video_processor_factory=processor_factory,
        async_processing=True,
    )

    # Status feedback
    if ctx and ctx.state.playing:
        st.success("Camera streaming. Position yourself until the banner turns GREEN.")
    else:
        st.warning("Camera not streaming yet. See troubleshooting below if this persists.")

        # Troubleshooting expander
        with st.expander("Camera Troubleshooting"):
            st.markdown("""
            **Common Issues:**

            **iOS Safari:**
            1. Tap the "Aa" in address bar → Website Settings → Allow Camera
            2. Refresh the page after granting permission
            3. Only works over HTTPS (automatic on Streamlit Cloud)

            **Android Chrome:**
            1. Tap the lock icon in address bar → Permissions → Camera → Allow
            2. If "Back camera" doesn't work, try "Front camera"

            **Desktop:**
            1. Click the camera icon in the address bar
            2. Select "Allow" for camera access
            3. May need to refresh after granting permission

            **Still not working?**
            - Try a different browser (Chrome works best)
            - Use the Photo Fallback or Quick Upload below
            """)

    st.divider()

    # --- 2) Quick Upload ---
    st.markdown("### Quick Upload")
    st.caption("Already have a video? Upload it here.")

    up = st.file_uploader("Upload a swing video", type=["mp4", "mov", "avi"], key="quick_upload")
    if up:
        st.session_state["uploaded_video"] = up
        st.video(up)
        st.success("Uploaded. Go to the **Analyze** tab to process it.")

    st.divider()

    # --- 3) Photo Framing Fallback ---
    with st.expander("Photo Framing Fallback"):
        st.caption("If live preview doesn't work, check your framing with a photo, then record with your native camera app.")

        photo = st.camera_input("Take a test photo")
        if photo:
            from PIL import Image
            img = Image.open(photo)
            st.image(draw_overlay_grid(img), caption="Framing check - adjust until centered in guides")

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

        # Load drills for pointer-specific recommendations
        drills = load_drills()

        # Get detailed pointers from rules engine
        detailed_pointers = analyze_with_goals_detailed(metrics, goals, confidence)

        # Also get simple format for backward compatibility (report, etc.)
        pointers, tags = analyze_with_goals(metrics, goals, confidence)

        st.subheader("Coaching Pointers")

        if confidence == "low":
            st.caption("*Lower confidence detection - take these suggestions with a grain of salt.*")

        if not detailed_pointers:
            st.success("Swing fundamentals look solid. Keep practicing for consistency!")
        else:
            # Priority labels
            priority_icons = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}

            for pointer in detailed_pointers:
                icon = priority_icons.get(pointer.priority, "⚪")

                with st.expander(f"{icon} {pointer.message}", expanded=(pointer.priority <= 2)):
                    # Why it matters
                    st.markdown(f"**Why it matters:** {pointer.why}")

                    # Confidence label
                    if pointer.confidence == "low":
                        st.caption("⚠️ *Low confidence - verify with additional video*")

                    # Associated drills
                    pointer_drills = get_pointer_drills(pointer, drills) if drills else []
                    if pointer_drills:
                        st.markdown("**Recommended drills:**")
                        for d in pointer_drills[:3]:  # Show top 3 drills
                            st.markdown(f"- **{d['name']}** ({d.get('difficulty', 'all levels')})")
                            if d.get("why"):
                                st.caption(f"  {d['why']}")

        # Show all suggested drills section
        if drills:
            drill_tags = map_tags_to_drill_tags(tags)
            all_suggestions = tag_to_drills(drill_tags, drills)

            if all_suggestions:
                st.subheader("All Suggested Drills")
                st.caption("Drills to address the issues identified above")

                for d in all_suggestions:
                    with st.expander(f"🏌️ {d['name']} ({d.get('difficulty', 'all levels')})"):
                        if d.get("why"):
                            st.markdown(f"**Why:** {d['why']}")
                        if d.get("equipment"):
                            equip = d['equipment']
                            equip_str = ', '.join(equip) if equip else 'None needed'
                            st.write(f"**Equipment:** {equip_str}")
                        st.write("**Steps:**")
                        for i, step in enumerate(d.get("steps", []), start=1):
                            st.write(f"{i}. {step}")
        else:
            st.warning("Drills database not found.")

        # Save and Download section
        st.divider()

        save_col1, save_col2 = st.columns(2)

        with save_col1:
            # Save Session button
            if st.button("Save to Progress", type="secondary", use_container_width=True):
                store = get_session_store()
                session = Session.create(
                    club=club,
                    angle=angle,
                    metrics=metrics,
                    confidence=confidence,
                    pointers=pointers,
                    video_name=getattr(video, "name", "clip") if video else "",
                )
                if store.save_session(session):
                    st.success("Session saved! View in Progress tab.")
                    st.session_state["last_saved_session"] = session.id
                else:
                    st.error("Could not save session. Storage may be unavailable.")

        with save_col2:
            # Coach Report download
            st.download_button(
                "Download Report (PDF)",
                data=render_pdf({
                    "club": club,
                    "video_name": getattr(video, "name", "clip"),
                    "metrics": metrics,
                    "pointers": pointers,
                }),
                file_name="coach_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

# =========================
# Progress Tab
# =========================
with tab_progress:
    st.subheader("Progress Tracking")

    # Get session store
    store = get_session_store()

    # Ephemeral storage warning
    if store.is_ephemeral:
        st.warning(
            "Note: Session data is stored temporarily and may be lost when the app restarts. "
            "Use 'Export Sessions' below to save your data."
        )

    # Load sessions
    sessions = store.load_sessions(limit=100)

    if not sessions:
        st.info("No sessions recorded yet. Analyze a swing and click 'Save to Progress' to start tracking.")
    else:
        # Filters
        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:
            clubs = ["All"] + list(set(s.club for s in sessions))
            filter_club = st.selectbox("Filter by Club", clubs, key="filter_club")

        with filter_col2:
            angles = ["All"] + list(set(s.angle for s in sessions))
            filter_angle = st.selectbox("Filter by Angle", angles, key="filter_angle")

        # Apply filters
        filtered = sessions
        if filter_club != "All":
            filtered = [s for s in filtered if s.club == filter_club]
        if filter_angle != "All":
            filtered = [s for s in filtered if s.angle == filter_angle]

        st.caption(f"Showing {len(filtered)} of {len(sessions)} sessions")

        # Trend charts
        if len(filtered) >= 2:
            st.subheader("Trends")

            # Prepare data for charts
            import datetime

            chart_data = []
            for s in reversed(filtered):  # Oldest first for charts
                try:
                    dt = datetime.datetime.fromisoformat(s.timestamp)
                    date_str = dt.strftime("%m/%d")
                except Exception:
                    date_str = s.timestamp[:10]

                chart_data.append({
                    "date": date_str,
                    "tempo": s.metrics.get("tempo_ratio"),
                    "head_sway": s.metrics.get("head_sway_cm"),
                    "hip_rotation": s.metrics.get("hip_rotation_deg_top"),
                    "shoulder_rotation": s.metrics.get("shoulder_rotation_deg_top"),
                })

            # Tempo chart
            tempo_data = [(d["date"], d["tempo"]) for d in chart_data if d["tempo"] is not None]
            if len(tempo_data) >= 2:
                st.markdown("**Tempo Ratio Over Time**")
                st.caption("Target: 2.5-3.5 (varies by club)")
                chart_df = {"Date": [d[0] for d in tempo_data], "Tempo": [d[1] for d in tempo_data]}
                st.line_chart(chart_df, x="Date", y="Tempo")

            # Head sway chart
            sway_data = [(d["date"], d["head_sway"]) for d in chart_data if d["head_sway"] is not None]
            if len(sway_data) >= 2:
                st.markdown("**Head Sway Over Time (cm)**")
                st.caption("Lower is better. Target: <4cm for Driver")
                chart_df = {"Date": [d[0] for d in sway_data], "Head Sway (cm)": [d[1] for d in sway_data]}
                st.line_chart(chart_df, x="Date", y="Head Sway (cm)")

        # Session list
        st.subheader("Recent Sessions")

        for s in filtered[:20]:  # Show last 20
            try:
                dt = datetime.datetime.fromisoformat(s.timestamp)
                date_str = dt.strftime("%b %d, %Y %H:%M")
            except Exception:
                date_str = s.timestamp

            # Confidence badge
            conf_badge = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(s.confidence, "⚪")

            with st.expander(f"{conf_badge} {date_str} - {s.club} ({s.angle})"):
                # Metrics
                m = s.metrics
                met_col1, met_col2, met_col3, met_col4 = st.columns(4)
                met_col1.metric("Tempo", m.get("tempo_ratio", "N/A"))
                met_col2.metric("Head Sway", f"{m.get('head_sway_cm', 'N/A')} cm" if m.get('head_sway_cm') else "N/A")
                met_col3.metric("Hip Rot", f"{m.get('hip_rotation_deg_top', 'N/A')}°" if m.get('hip_rotation_deg_top') else "N/A")
                met_col4.metric("Shoulder Rot", f"{m.get('shoulder_rotation_deg_top', 'N/A')}°" if m.get('shoulder_rotation_deg_top') else "N/A")

                # Pointers summary
                if s.pointers_summary:
                    st.markdown("**Key feedback:**")
                    for p in s.pointers_summary[:3]:
                        st.write(f"• {p}")

        # Export section
        st.divider()
        st.subheader("Data Management")

        export_col1, export_col2 = st.columns(2)

        with export_col1:
            # Export sessions
            if sessions:
                export_data = store.export_sessions_json()
                st.download_button(
                    "Export Sessions (JSON)",
                    data=export_data,
                    file_name="golf_sessions_export.json",
                    mime="application/json",
                    use_container_width=True,
                )

        with export_col2:
            # Clear sessions (with confirmation)
            if st.button("Clear All Sessions", type="secondary", use_container_width=True):
                st.session_state["confirm_clear"] = True

            if st.session_state.get("confirm_clear"):
                st.warning("Are you sure? This cannot be undone.")
                confirm_col1, confirm_col2 = st.columns(2)
                with confirm_col1:
                    if st.button("Yes, clear all", type="primary"):
                        store.clear_sessions()
                        st.session_state["confirm_clear"] = False
                        st.rerun()
                with confirm_col2:
                    if st.button("Cancel"):
                        st.session_state["confirm_clear"] = False
                        st.rerun()
