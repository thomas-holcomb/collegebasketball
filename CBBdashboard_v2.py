#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan  3 16:18:15 2026

@author: tholcomb
"""

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

# ------------------------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------------------------

engine = create_engine(
    "postgresql+psycopg2://postgres@localhost:5432/cbb"
)

# ------------------------------------------------------------------------------
# DATA LOADING
# ------------------------------------------------------------------------------
@st.cache_data
def load_base_games():
    return pd.read_sql("""SELECT
        g.*,

        ht.conference  AS home_conference,

        at.conference  AS away_conference

    FROM v_games_rank_groups g
    JOIN teams_master ht ON g.home_team_id = ht.team_id
    JOIN teams_master at ON g.away_team_id = at.team_id;
""", engine)

games_df = load_base_games()
# --- FORCE DATE TYPES ---
games_df["date"] = pd.to_datetime(
    games_df["date"],
    errors="coerce"
)

# Optional: drop rows with invalid dates (should be very few)
games_df = games_df.dropna(subset=["date"])

# ------------------------------------------------------------------------------
# STREAMLIT PAGE SETUP
# ------------------------------------------------------------------------------

st.set_page_config(
    page_title="College Basketball Betting Dashboard",
    layout="wide"
)

st.title("🏀 College Basketball Dashboard")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
# ------------------------------------------------------------------------------
# GLOBAL FILTERS (OPTIONAL – YOU CAN EXPAND LATER)
# ------------------------------------------------------------------------------

with st.container():
    c1, c2 = st.columns(2)

    with c1:
        site_filter = st.radio(
            "Game Location",
            ["All", "True Road", "Neutral"],
            horizontal=True
        )

    with c2:
        ranked_only = st.checkbox("Ranked Teams Only", value=True)

# Apply global filters
filtered_games = games_df.copy()

if site_filter != "All":
    filtered_games = filtered_games[
        filtered_games["site_type"] == site_filter
    ]

if ranked_only:
    filtered_games = filtered_games[
        (filtered_games["home_rank"].between(1, 25)) |
        (filtered_games["away_rank"].between(1, 25))
    ]

# ------------------------------------------------------------------------------
# MAIN LAYOUT
# ------------------------------------------------------------------------------

home_col, away_col = st.columns(2)

# ==============================================================================
# HOME TEAM SECTION
# ==============================================================================

with home_col:
    st.subheader("🏠 Home Team Analysis")

    # -------------------------
    # FILTERS
    # -------------------------
    home_conf = st.selectbox(
        "Home Conference",
        sorted(filtered_games["home_conference"].dropna().unique()),
        key="home_conf"
    )

    home_team = st.selectbox(
        "Home Team",
        sorted(
            filtered_games[
                filtered_games["home_conference"] == home_conf
            ]["home_team"].unique()
        ),
        key="home_team"
    )

    home_rank_group = st.selectbox(
        "Home Rank Group",
        [ "Top 5", "Top 10", "Top 25", "Unranked"],
        key="home_rank_group"
    )

    # -------------------------
    # DATA FILTERING
    # -------------------------
    home_df = filtered_games[
        (filtered_games["home_conference"] == home_conf) &
        (filtered_games["home_team"] == home_team)
    ]

    if home_rank_group != "All":
        home_df = home_df[
            home_df["home_rank_group"] == home_rank_group
    ]


    # -------------------------
    # KPI CALCULATIONS
    # -------------------------
    home_games = len(home_df)
    home_wins = home_df["home_win"].sum()
    home_losses = home_games - home_wins
    home_win_pct = round(home_wins / home_games, 3) if home_games > 0 else 0

    # -------------------------
    # KPI DISPLAY
    # -------------------------
    k1, k2, k3 = st.columns(3)
    k1.metric("Win %", f"{home_win_pct:.3f}")
    k2.metric("Record", f"{home_wins}-{home_losses}")
    k3.metric("Games", home_games)

    # -------------------------
    # OPTIONAL CHART (ADD LATER)
    # -------------------------
    # st.bar_chart(...)

# ==============================================================================
# AWAY TEAM SECTION
# ==============================================================================

with away_col:
    st.subheader("✈️ Away Team Analysis")

    # -------------------------
    # FILTERS
    # -------------------------
    away_conf = st.selectbox(
        "Away Conference",
        sorted(filtered_games["away_conference"].dropna().unique()),
        key="away_conf"
    )

    away_team = st.selectbox(
        "Away Team",
        sorted(
            filtered_games[
                filtered_games["away_conference"] == away_conf
            ]["away_team"].unique()
        ),
        key="away_team"
    )

    away_rank_group = st.selectbox(
        "Away Rank Group",
        ["Top 5", "Top 10", "Top 25", "Unranked"],
        key="away_rank_group"
    )

    # -------------------------
    # DATA FILTERING
    # -------------------------
    away_df = filtered_games[
        (filtered_games["away_conference"] == away_conf) &
        (filtered_games["away_team"] == away_team)
    ]

    if away_rank_group != "All":
        away_df = away_df[
        away_df["away_rank_group"] == away_rank_group
    ]



    # ------------------------------------------------------------------------------
    # GAME-LEVEL FILTERED DATA
    # ------------------------------------------------------------------------------
    
    game_table_df = filtered_games.copy()
    
    # Filter by home selection if chosen
    if "home_team" in st.session_state:
        game_table_df = game_table_df[
            game_table_df["home_team"] == st.session_state["home_team"]
        ]
    
    # Filter by away selection if chosen
    if "away_team" in st.session_state:
        game_table_df = game_table_df[
            game_table_df["away_team"] == st.session_state["away_team"]
        ]


    # -------------------------
    # KPI CALCULATIONS
    # -------------------------
    away_games = len(away_df)
    away_wins = away_df["away_win"].sum()
    away_losses = away_games - away_wins
    away_win_pct = round(away_wins / away_games, 3) if away_games > 0 else 0

    # -------------------------
    # KPI DISPLAY
    # -------------------------
    k1, k2, k3 = st.columns(3)
    k1.metric("Win %", f"{away_win_pct:.3f}")
    k2.metric("Record", f"{away_wins}-{away_losses}")
    k3.metric("Games", away_games)

# ------------------------------------------------------------------------------
# RANKED VS RANKED (OPTIONAL SECTION)
# ------------------------------------------------------------------------------

st.divider()
st.subheader("🔥 Ranked vs Ranked Matchups")

ranked_vs_ranked = filtered_games[
    (filtered_games["home_rank_group"] != "Unranked") &
    (filtered_games["away_rank_group"] != "Unranked")
]


rv_games = len(ranked_vs_ranked)
rv_away_win_pct = (
    ranked_vs_ranked["away_win"].mean()
    if rv_games else 0
)

st.metric(
    "Away Win % (Ranked vs Ranked)",
    f"{rv_away_win_pct:.3f}"
)


rv_by_away_group = (
    ranked_vs_ranked
    .groupby(["away_rank_group", "site_type"])
    .agg(
        games=("away_win", "count"),
        away_wins=("away_win", "sum"),
        away_win_pct=("away_win", "mean")
    )
    .reset_index()
)

rv_by_away_group["away_win_pct"] = rv_by_away_group["away_win_pct"].round(3)

# ------------------------------------------------------------------------------
# RANKED TEAMS ON THE ROAD
# ------------------------------------------------------------------------------
st.subheader("📊 Ranked vs Ranked — Away Team Performance")
st.dataframe(rv_by_away_group, use_container_width=True)

st.divider()
st.subheader("🧾 Game-Level Results")


st.divider()
st.subheader("🚗 Ranked Away Teams vs Unranked Home Teams")

road_vs_unranked = filtered_games[
    (filtered_games["site_type"] == "True Road") &
    (filtered_games["away_rank_group"] != "Unranked") &
    (filtered_games["home_rank_group"] == "Unranked")
]

road_vs_unranked_summary = (
    road_vs_unranked
    .groupby("away_rank_group")
    .agg(
        games=("away_win", "count"),
        away_wins=("away_win", "sum"),
        win_pct=("away_win", "mean")
    )
    .reset_index()
)

road_vs_unranked_summary["win_pct"] = road_vs_unranked_summary["win_pct"].round(3)

st.dataframe(
    road_vs_unranked_summary.sort_values("away_rank_group"),
    use_container_width=True
)

# ------------------------------------------------------------------------------
# GAME-LEVEL MATCHUP DATA
# ------------------------------------------------------------------------------

game_level_df = filtered_games.copy()

# Filter to games involving selected home team
if home_team:
    game_level_df = game_level_df[
        (game_level_df["home_team"] == home_team) |
        (game_level_df["away_team"] == home_team)
    ]

# Further filter to games involving selected away team
if away_team:
    game_level_df = game_level_df[
        (game_level_df["home_team"] == away_team) |
        (game_level_df["away_team"] == away_team)
    ]

# ------------------------------------------------------------------------------
# MATCHUP EXPANDER
# ------------------------------------------------------------------------------

with st.expander("📋 Head-to-Head Matchup History"):
    matchup_df = filtered_games[
        (
            (filtered_games["home_team"] == home_team) &
            (filtered_games["away_team"] == away_team)
        ) |
        (
            (filtered_games["home_team"] == away_team) &
            (filtered_games["away_team"] == home_team)
        )
    ].sort_values("date", ascending=False)

    if matchup_df.empty:
        st.info("No historical matchups between these teams.")
    else:
        st.dataframe(
            matchup_df[[
                "date",
                "home_team",
                "away_team",
                "home_points",
                "away_points",
                "site_type",
                "home_rank",
                "away_rank"
            ]],
            use_container_width=True,
            hide_index=True
        )

st.divider()
st.subheader("🕔 Last 5 Games")

def last_n_games(team_name, df, n=5):
    team_games = df[
        (df["home_team"] == team_name) |
        (df["away_team"] == team_name)
    ].sort_values("date", ascending=False)

    return team_games.head(n)

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"**{home_team} — Last 5 Games**")
    home_last5 = last_n_games(home_team, filtered_games)
    st.dataframe(
        home_last5[[
            "date",
            "home_team",
            "away_team",
            "home_points",
            "away_points",
            "site_type",
            "home_rank",
            "away_rank"
        ]],
        use_container_width=True,
        hide_index=True
    )

with col2:
    st.markdown(f"**{away_team} — Last 5 Games**")
    away_last5 = last_n_games(away_team, filtered_games)
    st.dataframe(
        away_last5[[
            "date",
            "home_team",
            "away_team",
            "home_points",
            "away_points",
            "site_type",
            "home_rank",
            "away_rank"
        ]],
        use_container_width=True,
        hide_index=True
    )




st.caption(f"Games after filters: {len(filtered_games)}")

