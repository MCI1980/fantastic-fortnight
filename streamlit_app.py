
import streamlit as st
from core.rules import analyze_with_goals, DEFAULT_GOALS
from core.report import render_pdf
from capture_guide import get_recs, draw_overlay_grid

tab_capture, tab_analyze, tab_progress = st.tabs(["Capture", "Analyze", "Progress"])

with tab_capture:
    st.subheader("Get your swing video")

    # Two options: Quick Upload vs Guided Capture
    c1, c2 = st.columns(2)

    # --------- Quick Upload ----------
    with c1:
        st.markdown("### Quick Upload")
        up = st.file_uploader("Upload a swing video", type=["mp4","mov","avi"], key="quick_upload")
        if up:
            st.success("Video uploaded. Go to the Analyze tab to process it.")
            st.session_state["uploaded_video"] = up  # save for Analyze tab
            st.video(up)

    # --------- Guided Capture ----------
    with c2:
        st.markdown("### Guided Capture")
        st.caption("Use your phone to align the frame first, then record with your camera app and upload that video here.")
        angle = st.radio("Choose angle", ["FO (Face-On)", "DTL (Down-the-Line)"], horizontal=True)
        angle_key = "FO" if angle.startswith("FO") else "DTL"
        recs = get_recs(angle_key)

        st.markdown("**Recommended setup**")
        st.write(f"- Camera height: **{recs['height_ft'][0]}–{recs['height_ft'][1]} ft** (≈ hand height)")
        st.write(f"- Distance to player: **{recs['distance_ft'][0]}–{recs['distance_ft'][1]} ft**")
        for n in recs["notes"]:
            st.write("• " + n)

        st.divider()
        st.markdown("**Framing check (photo only)**")
        st.caption("Take a quick photo to align. Then use your phone's camera to record the actual swing video.")

        # Take a photo to check framing (works on mobile)
        photo = st.camera_input("Open camera to take a framing photo")
        if photo:
            from PIL import Image
            img = Image.open(photo)
            over = draw_overlay_grid(img)
            st.image(over, caption="Framing guide (grid + head box + feet margin)")
            st.info("If your head is inside the top box and feet above the bottom margin, framing is good. Keep the horizon level.")

        st.divider()
        guided = st.file_uploader("Upload the recorded swing video", type=["mp4","mov","avi"], key="guided_upload")
        if guided:
            st.success("Video uploaded. Go to the Analyze tab to process it.")
            st.session_state["uploaded_video"] = guided
            st.video(guided)
            
with tab_analyze:
    uploaded = st.session_state.get("uploaded_video")
    if uploaded:
        st.info("Video detected from Capture tab. In the next step, we'll run analysis on it.")
        st.video(uploaded)
    # ... your existing analysis/demo metrics UI below ...