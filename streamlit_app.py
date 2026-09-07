# streamlit_app.py
# Golf Coach - TrackMan-driven practice planning for the 80s golfer.
#
# Run on the simulator PC:  streamlit run streamlit_app.py
# Then open the printed Network URL on your phone (same Wi-Fi).

from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from analysis import (
    aggregate_rounds,
    bag_gaps,
    benchmark_for,
    club_summary,
    club_tendencies,
    filter_valid,
    impact_summary,
    load_games,
    miss_pattern,
    prepare_shots,
    recent_shots,
    score_game,
    stats_shots,
    strike_quality,
    strokes_lost,
    tagged_game_results,
    yardage_card,
)
from analysis.games import game_applies_to_club
from analysis.scoring import CATEGORY_LABELS, rounds_frame
from coaching import (
    build_weekly_plan,
    evaluate_check,
    evaluate_rounds,
    evaluate_shots,
    get_pointer_drills,
    load_drills,
    top_priorities,
)
from core.report import render_yardage_card
from data import HoleResult, Round, RoundStore, Settings, SettingsStore, ShotStore
from data.plans import PlanStore
from integrations import parse_rounds_csv
from integrations.trackman import club_sort_key

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Golf Coach", page_icon="⛳", layout="wide", initial_sidebar_state="expanded")

settings_store = SettingsStore()
settings: Settings = settings_store.load()
shot_store = ShotStore()
round_store = RoundStore()
plan_store = PlanStore()
DRILLS = load_drills()
GAMES = load_games()

PRIORITY_ICON = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}
CONF_ICON = {"high": "●●●", "medium": "●●○", "low": "●○○"}


# ---------------------------------------------------------------------------
# Sidebar: settings + folder scan
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")
    with st.form("settings_form"):
        export_folder = st.text_input(
            "TrackMan export folder",
            value=settings.export_folder,
            help="Folder where you save 'Trackman CSV' exports from TPS. New files are imported automatically.",
            placeholder=r"C:\Users\you\Documents\TrackMan Exports",
        )
        handedness = st.radio("Handedness", ["right", "left"], index=0 if settings.handedness == "right" else 1, horizontal=True)
        target_score = st.number_input("Target score (18 holes)", min_value=70, max_value=110, value=int(settings.target_score), step=1)
        recent_days = st.select_slider("Use shots from the last", options=[14, 30, 45, 60, 90, 180, 365], value=int(settings.recent_days), format_func=lambda d: f"{d} days")
        min_shots = st.number_input("Min shots per club for the card", min_value=1, max_value=30, value=int(settings.min_shots_per_club))
        auto_scan = st.checkbox("Auto-import new exports on load", value=bool(settings.auto_scan))
        flip_side = st.checkbox("Flip left/right sign", value=bool(settings.flip_side_sign), help="Tick if the Miss direction on your card looks backwards.")
        saved = st.form_submit_button("Save settings")
    if saved:
        settings = Settings(
            export_folder=export_folder.strip(),
            handedness=handedness,
            target_score=int(target_score),
            recent_days=int(recent_days),
            min_shots_per_club=int(min_shots),
            auto_scan=bool(auto_scan),
            flip_side_sign=bool(flip_side),
            player_name=settings.player_name,
        )
        settings_store.save(settings)
        st.success("Saved.")
        st.rerun()

    st.divider()
    scan_clicked = st.button("Scan export folder now")
    st.caption(f"Data folder: `{shot_store.data_dir}`")


def run_scan(folder: str, announce: bool = True):
    if not folder:
        if announce:
            st.sidebar.warning("Set the export folder first.")
        return
    results = shot_store.scan_folder(folder)
    st.session_state["last_scan"] = {
        "at": datetime.now(),
        "results": [(r.source, r.status, r.added, r.warnings) for r in results],
    }
    added = sum(r.added for r in results if r.ok)
    errors = [r for r in results if r.status == "error"]
    if announce:
        if errors:
            st.sidebar.error(errors[0].warnings[0] if errors[0].warnings else "Scan failed.")
        elif added:
            st.sidebar.success(f"Imported {added} new shots from {sum(1 for r in results if r.ok)} file(s).")
        elif results:
            st.sidebar.info("Files found but no new shots.")
        else:
            st.sidebar.info("No new export files.")


if scan_clicked:
    run_scan(settings.export_folder, announce=True)
elif settings.auto_scan and settings.export_folder:
    last = st.session_state.get("last_scan", {}).get("at")
    if last is None or (datetime.now() - last).total_seconds() > 120:
        run_scan(settings.export_folder, announce=False)


# ---------------------------------------------------------------------------
# Load + prepare data (small enough to do on every run)
# ---------------------------------------------------------------------------

raw_shots = shot_store.load_shots()
all_shots = filter_valid(prepare_shots(raw_shots, settings.handedness, settings.flip_side_sign))
recent = recent_shots(all_shots, settings.recent_days)
stats = stats_shots(recent)                       # drill / warm-up balls excluded
summary = club_summary(stats, min_shots=settings.min_shots_per_club)
summary_any = club_summary(stats, min_shots=1)
rounds = round_store.load()
rounds_agg = aggregate_rounds(rounds)

shot_pointers = evaluate_shots(stats, settings.handedness, min_shots=max(8, settings.min_shots_per_club))
round_pointers = evaluate_rounds(rounds_agg, settings.target_score)
priorities = top_priorities(shot_pointers, round_pointers, k=3)

has_shots = not all_shots.empty
has_rounds = len(rounds) > 0

st.title("⛳ Golf Coach")
st.caption("TrackMan sessions + your rounds → what to practise this week.")

tab_import, tab_numbers, tab_coach, tab_plan, tab_rounds, tab_progress = st.tabs(
    ["Import", "My Numbers", "Coach", "Plan", "Rounds", "Progress"]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt(v, digits=1, suffix=""):
    try:
        if v is None or pd.isna(v):
            return "-"
        return f"{float(v):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "-"


def pointer_card(p, show_drills=True, key_prefix="p"):
    icon = PRIORITY_ICON.get(p.priority, "⚪")
    with st.container(border=True):
        st.markdown(f"**{icon} {p.message}**")
        st.write(p.why)
        cols = st.columns(3)
        cols[0].markdown(f"**Measured:** {fmt(p.measured_value)}")
        cols[1].markdown(f"**Target:** {p.target_text or fmt(p.target_value)}")
        cols[2].markdown(f"**Confidence:** {CONF_ICON.get(p.confidence, '')} ({p.n} {'shots' if p.source == 'shots' else 'rounds'})")
        if p.success_criterion:
            st.markdown(f"✅ **You'll know it's fixed when:** {p.success_criterion}")
        if show_drills:
            drills = get_pointer_drills(p, DRILLS, limit=3)
            if drills:
                st.markdown("**Drills:**")
                for d in drills:
                    where = d.get("where", "sim")
                    with st.expander(f"{d['name']}  ·  {where}  ·  {d.get('difficulty', '')}"):
                        for i, step in enumerate(d.get("steps", []), start=1):
                            st.write(f"{i}. {step}")
                        if d.get("why"):
                            st.caption(f"Why: {d['why']}")
                        if d.get("trackman_watch"):
                            st.caption(f"Watch on TrackMan: {d['trackman_watch']}")


# ---------------------------------------------------------------------------
# Import tab
# ---------------------------------------------------------------------------

with tab_import:
    if not has_shots:
        st.info("**Start here.** Export a session from TrackMan Performance Studio and drop it below, or set the export folder in the sidebar so new exports import themselves.")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Upload TrackMan CSV exports")
        uploads = st.file_uploader("Drop one or more 'Trackman CSV' files", type=["csv", "txt"], accept_multiple_files=True)
        processed = st.session_state.setdefault("processed_uploads", set())
        messages = st.session_state.setdefault("upload_messages", [])
        new_uploads = [u for u in (uploads or []) if (u.name, u.size) not in processed]
        if new_uploads:
            for up in new_uploads:
                res = shot_store.ingest_bytes(up.getvalue(), up.name)
                processed.add((up.name, up.size))
                if res.ok:
                    messages.append(("success", f"{up.name}: imported {res.added} shots" + (f", {res.skipped_duplicates} duplicates skipped" if res.skipped_duplicates else "")))
                elif res.status == "duplicate_file":
                    messages.append(("info", f"{up.name}: already imported."))
                elif res.status == "no_new_shots":
                    messages.append(("info", f"{up.name}: all shots were already in the database."))
                else:
                    messages.append(("error", f"{up.name}: nothing imported. " + " ".join(res.warnings)))
                for w in res.warnings:
                    messages.append(("caption" if w.startswith("Ignored columns") else "warning", f"{up.name}: {w}"))
            st.rerun()  # reload so every tab sees the new shots
        for level, text in messages[-12:]:
            getattr(st, level)(text)
        if messages and st.button("Clear messages"):
            st.session_state["upload_messages"] = []
            st.rerun()

        last_scan = st.session_state.get("last_scan")
        if last_scan and last_scan.get("results"):
            st.subheader("Last folder scan")
            for src, status, added, warns in last_scan["results"]:
                if status == "added":
                    st.write(f"✅ {src}: {added} new shots")
                elif status == "error":
                    st.write(f"❌ {src}: {' '.join(warns)}")
                else:
                    st.write(f"• {src}: {status.replace('_', ' ')}")

    with right:
        st.subheader("How to export from TrackMan")
        st.markdown(
            """
1. In **TrackMan Performance Studio**, open **Shot Analysis** (the practice/range screen, not Virtual Golf).
2. Load the session (today's, or one from the **Shot Library**).
3. Click the **View Selector** at the top and choose **Table View**.
4. Open the **File Options** menu (top right of the table) and choose **Trackman CSV**.
5. Save it into the folder you set in the sidebar. Done: the app imports it on the next load.

*The export only exists in TPS on the simulator PC and needs an active TrackMan software subscription. Tag the club in TPS before each set so the file carries club names.*

**Tags that the app understands** (set with the **Tag** button before a set, clear it afterwards):

- `warmup` or `drill` — kept, but excluded from your yardage card and coaching numbers
- `game` — scores every game that fits the club; `game: fairway finder` scores that game only
            """
        )

    st.divider()
    st.subheader("Imported sessions")
    sessions = shot_store.sessions()
    if sessions.empty:
        st.caption("No sessions yet.")
    else:
        show = sessions.copy()
        show["date"] = pd.to_datetime(show["date"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(show[["date", "source_file", "shots", "clubs"]], hide_index=True)
        c1, c2 = st.columns([3, 1])
        choice = c1.selectbox("Remove a session", options=["-"] + [f"{r.date} · {r.source_file} ({r.session_id})" for r in show.itertuples()], key="del_session")
        if c2.button("Delete", disabled=(choice == "-")):
            sid = choice.rsplit("(", 1)[-1].rstrip(")")
            removed = shot_store.delete_session(sid)
            st.success(f"Removed {removed} shots.")
            st.rerun()


# ---------------------------------------------------------------------------
# My Numbers tab
# ---------------------------------------------------------------------------

with tab_numbers:
    if summary.empty:
        st.info(f"Need at least {settings.min_shots_per_club} shots per club in the last {settings.recent_days} days. Import a session or lower the minimum in the sidebar.")
    else:
        st.subheader("Yardage card")
        excluded = int(recent.shape[0] - stats.shape[0])
        st.caption(
            f"Last {settings.recent_days} days · {int(stats.shape[0])} shots"
            + (f" ({excluded} drill/warm-up balls excluded)" if excluded else "")
            + " · Safe = 20th percentile carry, Plan = median, Max = 80th percentile, ± = one-sigma side spread"
        )
        card = yardage_card(summary, settings.handedness)
        st.dataframe(card, hide_index=True)
        png = render_yardage_card(card, title="My Numbers", subtitle=f"Last {settings.recent_days} days · {date.today().isoformat()}", handedness=settings.handedness)
        st.download_button("Download yardage card (PNG for your phone)", data=png, file_name="yardage_card.png", mime="image/png")

        gaps = bag_gaps(summary)
        if not gaps.empty:
            st.subheader("Bag gapping")
            problems = gaps[gaps["status"] != "ok"]
            if problems.empty:
                st.success("Carry gaps between clubs look sensible (6-18 yards).")
            else:
                for r in problems.itertuples():
                    if r.status == "overlap":
                        st.warning(f"**{r.from_club} → {r.to_club}: only {r.gap_yds:.0f} yds apart.** One of these clubs is redundant or being struck poorly. Check smash factor and consider a loft adjustment.")
                    else:
                        st.warning(f"**{r.from_club} → {r.to_club}: {r.gap_yds:.0f} yd hole in the bag.** Learn a three-quarter {r.from_club} or add a club in between.")
            with st.expander("All gaps"):
                st.dataframe(gaps, hide_index=True)

        st.subheader("Club detail")
        clubs = sorted(summary_any.index.tolist(), key=club_sort_key)
        club = st.selectbox("Club", clubs, key="numbers_club")
        sub = stats[stats["club"] == club]
        row = summary_any.loc[club]
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Shots", int(row["shots"]))
        m2.metric("Carry (median)", fmt(row.get("carry_med"), 0, " yds"))
        m3.metric("Carry spread ±", fmt(row.get("carry_std"), 0, " yds"))
        m4.metric("Side spread ±", fmt(row.get("side_std"), 0, " yds"))
        m5.metric("Smash", fmt(row.get("smash_mean"), 2))
        m6.metric("Consistency", fmt(row.get("consistency"), 0, "/100"))
        d1, d2, d3, d4, d5, d6 = st.columns(6)
        d1.metric("Club speed", fmt(row.get("club_speed_mean"), 0, " mph"))
        d2.metric("Ball speed", fmt(row.get("ball_speed_mean"), 0, " mph"))
        d3.metric("Launch", fmt(row.get("launch_mean"), 1, "°"))
        d4.metric("Spin", fmt(row.get("spin_mean"), 0, " rpm"))
        d5.metric("Attack", fmt(row.get("attack_mean"), 1, "°"))
        d6.metric("Face to path", fmt(row.get("ftp_mean"), 1, "°"))

        c1, c2 = st.columns([3, 2])
        with c1:
            if {"side_yds", "carry_yds"} <= set(sub.columns) and sub["side_yds"].notna().any():
                st.markdown("**Dispersion** (x = offline yards, + is your fade side; y = carry)")
                plot = sub[["side_yds", "carry_yds"]].dropna().rename(columns={"side_yds": "Offline (yds)", "carry_yds": "Carry (yds)"})
                st.scatter_chart(plot, x="Offline (yds)", y="Carry (yds)")
            else:
                st.caption("No offline data in this export for a dispersion plot.")
        with c2:
            pattern = miss_pattern(sub)
            if not pattern.empty:
                st.markdown("**Shot shapes**")
                st.bar_chart(pattern.set_index("label")["pct"])
            sq = strike_quality(sub, club)
            if sq.get("n"):
                st.caption(f"Solid strikes: {sq['pct_solid']:.0f}% of shots at or near smash {sq['expected']:.2f}")

        imp = impact_summary(sub, club)
        if imp.get("n"):
            st.markdown(f"**Strike location on the face** — average **{imp['label']}** ({imp['n']} shots with impact data)")
            st.caption("Each dot is one strike, in millimetres from face centre. Left = heel, right = toe; down = low, up = high.")
            pts = imp["points"]
            st.scatter_chart(pts, x=pts.columns[0], y=pts.columns[1])


# ---------------------------------------------------------------------------
# Coach tab
# ---------------------------------------------------------------------------

with tab_coach:
    if not has_shots and not has_rounds:
        st.info("Import a TrackMan session (Import tab) and log a round or two (Rounds tab) to get coaching.")
    else:
        st.subheader("This week's priorities")
        if not priorities:
            st.success("Nothing outside the target windows with enough data. Keep building the sample: 8+ shots per club and 2+ rounds.")
        for i, p in enumerate(priorities):
            pointer_card(p, key_prefix=f"top{i}")

        if has_rounds and rounds_agg.get("n_rounds"):
            st.subheader(f"Where strokes go vs an {settings.target_score}-shooter")
            sl = strokes_lost(rounds_agg, settings.target_score)
            if not sl.empty:
                show = sl.copy()
                show["you"] = show["you"].map(lambda v: f"{v:.1f}")
                show["benchmark"] = show["benchmark"].map(lambda v: f"{v:.1f}")
                show = show.rename(columns={"category": "Category", "you": "You", "benchmark": "Benchmark", "est_strokes": "Est. strokes / round", "note": "Note"})
                st.dataframe(show, hide_index=True)
                st.caption(f"Based on your last {rounds_agg['n_rounds']} rounds. Benchmarks are approximate amateur averages; the ranking matters more than the decimals.")

        if shot_pointers:
            st.subheader("All findings by club")
            by_club = {}
            for p in shot_pointers:
                by_club.setdefault(p.club, []).append(p)
            for club in sorted(by_club, key=club_sort_key):
                ps = by_club[club]
                worst = min(p.priority for p in ps)
                with st.expander(f"{PRIORITY_ICON.get(worst, '⚪')} {club} · {len(ps)} finding(s)"):
                    for j, p in enumerate(ps):
                        pointer_card(p, key_prefix=f"{club}{j}")
        elif has_shots:
            st.caption("No per-club findings yet: clubs need 8+ shots in the window to be evaluated.")

        if has_shots and GAMES:
            st.subheader("Scored games")
            tagged = tagged_game_results(all_shots, GAMES)
            if tagged:
                st.markdown("**Sets you tagged `game` in TPS** — scored automatically")
                rows = [{
                    "Date": r["date"].strftime("%Y-%m-%d") if r.get("date") is not None and not pd.isna(r["date"]) else "",
                    "Club": r["club"],
                    "Game": r["game"] + ("" if r.get("named") else " (auto)"),
                    "Score": f"{r['points']} / {r['max_points']}",
                    "Shots": r["shots_used"],
                } for r in tagged[:30]]
                st.dataframe(pd.DataFrame(rows), hide_index=True)
                st.caption("Tag a set 'game: fairway finder' to score one game, or just 'game' to score every game that fits the club.")
            st.caption("Manual check: scores from the last 10 shots of the chosen club in your most recent session that used it.")
            gcol1, gcol2 = st.columns(2)
            game_names = [g["name"] for g in GAMES]
            game_name = gcol1.selectbox("Game", game_names, key="game_pick")
            game = next(g for g in GAMES if g["name"] == game_name)
            eligible = [c for c in sorted(all_shots["club"].unique().tolist(), key=club_sort_key) if game_applies_to_club(game, c)]
            if eligible:
                gclub = gcol2.selectbox("Club", eligible, key="game_club")
                latest_session = all_shots[all_shots["club"] == gclub].sort_values("date")["session_id"].iloc[-1]
                sess_shots = all_shots[all_shots["session_id"] == latest_session]
                res = score_game(game, sess_shots, gclub)
                st.markdown(f"**{game['name']} with {gclub}: {res['points']} / {res['max_points']}**" + ("" if res["ready"] else f"  (only {res['shots_used']} shots in that session)"))
                st.caption(game.get("description", ""))
                if not res["detail"].empty:
                    st.dataframe(res["detail"], hide_index=True)
            else:
                st.caption("No shots with a club this game applies to.")


# ---------------------------------------------------------------------------
# Plan tab
# ---------------------------------------------------------------------------

with tab_plan:
    st.subheader("Weekly practice plan")
    latest_plan = plan_store.latest()
    c1, c2 = st.columns([1, 3])
    if c1.button("Generate this week's plan", type="primary", disabled=not (has_shots or has_rounds)):
        plan = build_weekly_plan(priorities, summary, DRILLS, GAMES, settings.handedness)
        plan_store.save(plan)
        st.rerun()
    if latest_plan is None:
        c2.info("No plan yet. Import at least one session, then generate a plan.")
    else:
        c2.caption(f"Week of {latest_plan.week_of} · generated {latest_plan.created_at[:16].replace('T', ' ')}")
        st.markdown("**Focus:** " + " · ".join(latest_plan.focus))
        st.markdown(f"**On the course this week:** {latest_plan.on_course_rule}")
        for s in latest_plan.sessions:
            with st.container(border=True):
                st.markdown(f"### {s.title}  ·  ~{s.minutes} min")
                st.caption(f"Focus: {s.focus}")
                for b in s.blocks:
                    kind_icon = {"warmup": "🔥", "drill": "🎯", "game": "🎮", "gapping": "📏", "home": "🏠", "course": "⛳"}.get(b.kind, "•")
                    with st.expander(f"{kind_icon} {b.name}  ·  {b.minutes} min  ·  {b.reps}", expanded=(b.kind in ("drill", "game"))):
                        for i, step in enumerate(b.instructions, start=1):
                            st.write(f"{i}. {step}")
                        if b.success_metric:
                            st.markdown(f"✅ **Pass mark:** {b.success_metric}")
                        if b.trackman_watch:
                            st.caption(f"Watch on TrackMan: {b.trackman_watch}")
        if latest_plan.checks:
            st.subheader("Plan checks (live)")
            for chk in latest_plan.checks:
                r = evaluate_check(chk, summary_any, rounds_agg)
                status = "✅" if r["ok"] else ("❌" if r["ok"] is False else "⏳")
                val = fmt(r["value"], 2 if r["metric"] in ("smash_mean", "smash_std", "carry_cv") else 1)
                st.write(f"{status} {r['label']} — now {val}, target {r['op']} {r['target']:.2f}" if r["metric"] in ("smash_mean", "smash_std", "carry_cv") else f"{status} {r['label']} — now {val}, target {r['op']} {r['target']:.1f}")


# ---------------------------------------------------------------------------
# Rounds tab
# ---------------------------------------------------------------------------

with tab_rounds:
    st.subheader("Log a round")
    st.caption("Two minutes after the round. Fairway: leave blank on par 3s. Up&down: only fill when you missed the green.")
    with st.form("round_form"):
        r1, r2, r3, r4 = st.columns([1, 2, 1, 1])
        r_date = r1.date_input("Date", value=date.today())
        r_course = r2.text_input("Course", value="")
        r_tees = r3.text_input("Tees", value="")
        r_holes = r4.selectbox("Holes", [18, 9], index=0)
        default = pd.DataFrame({
            "Hole": list(range(1, r_holes + 1)),
            "Par": [4] * r_holes,
            "Score": [4] * r_holes,
            "Putts": [2] * r_holes,
            "Fairway": ["-"] * r_holes,
            "GIR": ["-"] * r_holes,
            "Penalties": [0] * r_holes,
            "Up&Down": ["-"] * r_holes,
        })
        edited = st.data_editor(
            default,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Hole": st.column_config.NumberColumn(disabled=True),
                "Par": st.column_config.NumberColumn(min_value=3, max_value=6, step=1),
                "Score": st.column_config.NumberColumn(min_value=1, max_value=15, step=1),
                "Putts": st.column_config.NumberColumn(min_value=0, max_value=8, step=1),
                "Fairway": st.column_config.SelectboxColumn(options=["-", "Yes", "No"], required=True),
                "GIR": st.column_config.SelectboxColumn(options=["-", "Yes", "No"], required=True),
                "Penalties": st.column_config.NumberColumn(min_value=0, max_value=5, step=1),
                "Up&Down": st.column_config.SelectboxColumn(options=["-", "Yes", "No"], required=True),
            },
            key="round_editor",
        )
        submitted = st.form_submit_button("Save round", type="primary")
    if submitted:
        def yn(v):
            return True if v == "Yes" else (False if v == "No" else None)
        holes = []
        for _, r in edited.iterrows():
            holes.append(HoleResult(
                hole=int(r["Hole"]), par=int(r["Par"]), score=int(r["Score"]),
                putts=None if pd.isna(r["Putts"]) else int(r["Putts"]),
                fir=yn(r["Fairway"]), gir=yn(r["GIR"]),
                penalties=0 if pd.isna(r["Penalties"]) else int(r["Penalties"]),
                up_and_down=yn(r["Up&Down"]),
            ))
        rnd = Round.create(date=r_date.isoformat(), course=r_course.strip() or "Unknown course", tees=r_tees.strip(), holes=holes)
        if round_store.save(rnd):
            st.success(f"Saved: {rnd.total} ({rnd.to_par:+d}) with {rnd.putts} putts, {rnd.penalties} penalties.")
            st.rerun()
        else:
            st.error("Could not save the round.")

    with st.expander("Import rounds from a CSV (Golfity, Golf Pad, or your own spreadsheet)"):
        st.caption("One row per hole with columns like date, course, hole, par, score, putts, fairway, gir, penalties.")
        rup = st.file_uploader("Rounds CSV", type=["csv"], key="rounds_upload")
        if rup:
            imported, warns = parse_rounds_csv(rup.getvalue(), rup.name)
            for w in warns:
                st.warning(w)
            if imported:
                added = round_store.save_many(imported)
                st.success(f"Imported {len(imported)} round(s), {added} new.")
                st.rerun()

    st.divider()
    st.subheader("Your rounds")
    if not rounds:
        st.caption("No rounds logged yet.")
    else:
        rf = rounds_frame(rounds).sort_values("date", ascending=False)
        show = pd.DataFrame({
            "Date": rf["date"].dt.strftime("%Y-%m-%d"),
            "Course": rf["course"],
            "Score": rf["score"],
            "To par": rf["to_par"].map(lambda v: f"{int(v):+d}"),
            "Putts": rf["putts"],
            "3-putts": rf["three_putts"],
            "Penalties": rf["penalties"].round(0),
            "FIR %": rf["fir_pct"].round(0),
            "GIR %": rf["gir_pct"].round(0),
            "Dbl+": rf["doubles_plus"].round(0),
        })
        st.dataframe(show, hide_index=True)
        bench = benchmark_for(settings.target_score)
        a = rounds_agg
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Avg score", fmt(a.get("score"), 1), help=f"Target {settings.target_score}")
        k2.metric("Putts", fmt(a.get("putts"), 1), delta=None if a.get("putts") is None else f"{a['putts'] - bench['putts']:+.1f} vs target", delta_color="inverse")
        k3.metric("3-putts", fmt(a.get("three_putts"), 1), delta=None if a.get("three_putts") is None else f"{a['three_putts'] - bench['three_putts']:+.1f}", delta_color="inverse")
        k4.metric("Penalties", fmt(a.get("penalties"), 1), delta=None if a.get("penalties") is None else f"{a['penalties'] - bench['penalties']:+.1f}", delta_color="inverse")
        k5.metric("GIR %", fmt(a.get("gir_pct"), 0), delta=None if a.get("gir_pct") is None else f"{a['gir_pct'] - bench['gir_pct']:+.0f}")
        k6.metric("FIR %", fmt(a.get("fir_pct"), 0), delta=None if a.get("fir_pct") is None else f"{a['fir_pct'] - bench['fir_pct']:+.0f}")
        c1, c2 = st.columns([3, 1])
        pick = c1.selectbox("Remove a round", ["-"] + [f"{r.date} · {r.course} · {r.total} ({r.id})" for r in rounds], key="del_round")
        if c2.button("Delete round", disabled=(pick == "-")):
            rid = pick.rsplit("(", 1)[-1].rstrip(")")
            round_store.delete(rid)
            st.rerun()


# ---------------------------------------------------------------------------
# Progress tab
# ---------------------------------------------------------------------------

with tab_progress:
    st.subheader("Progress")
    if not has_shots and not has_rounds:
        st.caption("Nothing to chart yet.")
    if has_shots:
        st.markdown("**Club trends by session**")
        clubs = sorted(all_shots["club"].unique().tolist(), key=club_sort_key)
        pc1, pc2 = st.columns(2)
        tclub = pc1.selectbox("Club", clubs, key="trend_club")
        metric_options = {
            "Carry (median)": ("carry_yds", "median"),
            "Carry spread ± (std)": ("carry_yds", "std"),
            "Side spread ± (std)": ("side_yds", "std"),
            "Face to path (mean)": ("face_to_path_deg", "mean"),
            "Club path (mean)": ("club_path_deg", "mean"),
            "Attack angle (mean)": ("attack_angle_deg", "mean"),
            "Smash factor (mean)": ("smash_factor", "mean"),
            "Ball speed (mean)": ("ball_speed_mph", "mean"),
            "Spin (mean)": ("spin_rate_rpm", "mean"),
        }
        tmetric = pc2.selectbox("Metric", list(metric_options), key="trend_metric")
        col, agg = metric_options[tmetric]
        sub = all_shots[all_shots["club"] == tclub]
        if col in sub.columns and sub[col].notna().any():
            g = sub.groupby("session_id").agg(date=("date", "min"), value=(col, agg), shots=(col, "count")).sort_values("date")
            g = g[g["shots"] >= 3]
            if len(g) >= 2:
                chart = g.set_index(g["date"].dt.strftime("%m-%d"))[["value"]].rename(columns={"value": tmetric})
                st.line_chart(chart)
            else:
                st.caption("Need at least two sessions with 3+ shots of this club to draw a trend.")
        else:
            st.caption("That metric is not in your exports.")

    if has_rounds:
        st.markdown("**Scoring trends**")
        rf = rounds_frame(rounds)
        if len(rf) >= 2:
            chart = rf.set_index(rf["date"].dt.strftime("%m-%d"))[["score18", "putts18", "penalties"]].rename(columns={"score18": "Score", "putts18": "Putts", "penalties": "Penalties"})
            st.line_chart(chart)
        else:
            st.caption("Log a second round to see a scoring trend.")

    plans = plan_store.load()
    if plans:
        st.markdown("**Plan checks**")
        for plan in plans[:4]:
            with st.expander(f"Week of {plan.week_of} · {' · '.join(plan.focus)}"):
                if not plan.checks:
                    st.caption("No measurable checks in this plan.")
                for chk in plan.checks:
                    r = evaluate_check(chk, summary_any, rounds_agg)
                    status = "✅" if r["ok"] else ("❌" if r["ok"] is False else "⏳")
                    st.write(f"{status} {r['label']} — now {fmt(r['value'], 2)} (target {r['op']} {r['target']:.2f})")

    st.divider()
    st.subheader("Data")
    e1, e2, e3 = st.columns(3)
    if has_shots:
        e1.download_button("Export all shots (CSV)", data=shot_store.export_csv(), file_name="golf_shots.csv", mime="text/csv")
    if has_rounds:
        e2.download_button("Export rounds (JSON)", data=round_store.export_json(), file_name="golf_rounds.json", mime="application/json")
    if e3.button("Clear ALL data"):
        st.session_state["confirm_clear"] = True
    if st.session_state.get("confirm_clear"):
        st.warning("This deletes every imported shot, round and plan. Are you sure?")
        y, n = st.columns(2)
        if y.button("Yes, delete everything", type="primary"):
            shot_store.clear()
            round_store.clear()
            plan_store.clear()
            st.session_state["confirm_clear"] = False
            st.rerun()
        if n.button("Cancel"):
            st.session_state["confirm_clear"] = False
            st.rerun()
