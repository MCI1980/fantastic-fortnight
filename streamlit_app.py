
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
    uploaded = st.session_state.get("uploaded_video")
    if uploaded:
        st.info("Video detected from Capture tab. In the next step, we'll run analysis on it.")
        st.video(uploaded)
    # ... your existing analysis/demo metrics UI below ...