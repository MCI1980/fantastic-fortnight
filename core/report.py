from io import BytesIO

def render_pdf(session: dict) -> bytes:
    buf = BytesIO()
    club = session.get("club", "Unknown")
    m = session.get("metrics", {})
    lines = [
        "Golf Coach Report",
        f"Club: {club}",
        f"Video: {session.get('video_name','')}",
        f"Tempo: {m.get('tempo_ratio')}",
        f"Head sway: {m.get('head_sway_cm')} cm",
        "",
        "Pointers:",
    ] + [f"- {p}" for p in session.get("pointers", [])]
    buf.write(("\n".join(lines)).encode("utf-8"))
    return buf.getvalue()