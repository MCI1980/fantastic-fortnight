
import streamlit as st
from core.rules import analyze_with_goals, DEFAULT_GOALS
from core.report import render_pdf
from capture_guide import get_recs, draw_overlay_grid
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from live_capture import GuideProcessor

tab_capture, tab_analyze, tab_progress = st.tabs(["Capture", "Analyze", "Progress"])

with tab_capture:
    st.subheader("Capture your swing")

    # --- Club selection (applies to both capture paths) ---
    clubs = ["Driver","3W","Hybrid","Long Iron","Mid Iron","Short Iron","Wedge"]
    club = st.selectbox("Club", clubs, index=0)
    st.session_state["club"] = club

    # --- 1) Live Guided Capture (primary) ---
    st.markdown("### Live Guided Capture (beta)")
    st.caption("Live preview with framing guides. When the banner is green, record your swing.")

    # requires: streamlit-webrtc, av; and live_capture.GuideProcessor in your repo
    from streamlit_webrtc import webrtc_streamer, WebRtcMode
    from live_capture import GuideProcessor
    ctx = webrtc_streamer(
        key="live-guide",
        mode=WebRtcMode.SENDRECV,
        video_processor_factory=GuideProcessor,
        media_stream_constraints={"video": True, "audio": False},
    )
    st.info("Tip: If live preview isn’t permitted by your mobile browser, use Quick Upload below or the Photo Framing fallback.")

    st.divider()

    # --- 2) Quick Upload (secondary) ---
    st.markdown("### Quick Upload (existing video)")
    up = st.file_uploader("Upload a swing video", type=["mp4","mov","avi"], key="quick_upload")
    if up:
        st.session_state["uploaded_video"] = up
        st.video(up)
        st.success("Uploaded. Go to the Analyze tab to process it.")

    st.divider()

    # --- 3) Photo Framing (fallback) ---
    with st.expander("Photo Framing fallback (if live preview is blocked)"):
        st.caption("Use a photo to check framing, then record with your camera app and upload above.")
        angle = st.radio("Angle", ["FO (Face-On)","DTL (Down-the-Line)"], horizontal=True, key="fallback_angle")
        from capture_guide import get_recs, draw_overlay_grid
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
            from core.rules import CLUB_GOALS, DEFAULT_GOALS, analyze_with_goals
            goals = DEFAULT_GOALS.copy()
            goals.update(CLUB_GOALS.get(club, {}))
        except Exception:
            from core.rules import DEFAULT_GOALS, analyze_with_goals
            goals = DEFAULT_GOALS

        # Metrics display
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tempo (B:D)", metrics.get("tempo_ratio"))
        c2.metric("Head sway (cm)", metrics.get("head_sway_cm"))
        c3.metric("Hip rot @Top (°)", metrics.get("hip_rotation_deg_top"))
        c4.metric("Shoulder rot @Top (°)", metrics.get("shoulder_rotation_deg_top"))

        # Pointers
        pointers, tags = analyze_with_goals(metrics, goals)
        st.subheader("Pointers")
        for p in pointers:
            st.write("• " + p)

        # Drills (if drills.yaml exists)
        try:
            import yaml
            from pathlib import Path
            drills = yaml.safe_load((Path(__file__).parent / "drills.yaml").read_text())
            def tag_to_drills(tags, drills):
                tagset = set(tags or [])
                return [d for d in drills if tagset & set(d.get("tags", []))]
            st.subheader("Suggested drills")
            for d in tag_to_drills(tags, drills):
                with st.expander(d["name"]):
                    for i, step in enumerate(d["steps"], start=1):
                        st.write(f"{i}. {step}")
        except Exception as e:
            st.warning(f"Drills unavailable: {e}")

        # Coach Report (includes club)
        from core.report import render_pdf
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