import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import re, time, json

START_DATE = "2025-12-01"
END_DATE   = "2026-01-03"

base_url = "https://www.teamrankings.com/ncb/schedules/?date="

games = []

start = datetime.strptime(START_DATE, "%Y-%m-%d")
end   = datetime.strptime(END_DATE, "%Y-%m-%d")
current = start

while current <= end:
    date_str = current.strftime("%Y-%m-%d")
    url = base_url + date_str

    html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).text
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        current += timedelta(days=1)
        continue

    headers = [th.text.strip() for th in table.find_all("th")]
    col_map = {h: i for i, h in enumerate(headers)}

    rows = table.find_all("tr")[1:]

    for row in rows:
        cols = row.find_all("td")
        if not cols:
            continue

        matchup_cell = cols[col_map["Matchup"]]
        matchup_text = matchup_cell.text.strip()

        # Extract game URL
        link = matchup_cell.find("a")
        game_url = "https://www.teamrankings.com" + link["href"] if link else None

        games.append({
            "date": date_str,
            "rank": cols[col_map["Rank"]].text.strip(),
            "hotness": cols[col_map["Hotness Score"]].text.strip(),
            "matchup": matchup_text,
            "time": cols[col_map["Time"]].text.strip(),
            "location": cols[col_map["Location"]].text.strip(),
            "game_url": game_url
        })

    current += timedelta(days=1)

schedule_df = pd.DataFrame(games)
schedule_df = schedule_df.dropna(subset=['game_url'])
schedule_df.to_csv("teamrankings_schedule_with_links.csv", index=False)
print("✅ Stage 1 complete")


def extract_tables_from_soup(soup):
    tables = {}

    for idx, table in enumerate(soup.find_all("table")):
        rows = []
        header_cells = table.find_all("th")
        headers = [h.get_text(strip=True) for h in header_cells]

        for row in table.find_all("tr"):
            cells = row.find_all(["td"])
            if not cells:
                continue
            values = [c.get_text(strip=True) for c in cells]
            row_dict = {headers[i] if i < len(headers) else f"col{i}": v for i, v in enumerate(values)}
            rows.append(row_dict)

        tables[f"table_{idx}"] = rows

    return tables

#### PART 2 ###

# Load your schedule with URLs from Part 1
schedule_df = pd.read_csv("teamrankings_schedule_with_links.csv")

all_game_data = []
for idx, row in schedule_df.iterrows():
    url = row["game_url"]
    if not url:
        continue

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(response.text, "html.parser")


    game_dict = {
        "date": row["date"],
        "matchup": row["matchup"],
        "rank": row["rank"],
        "hotness": row["hotness"],
        "time": row["time"],
        "location": row["location"],
        "game_url": url
    }
    
    # ================== TABLE EXTRACTION (CRITICAL PART YOU’RE MISSING) ==================
    tables_data = extract_tables_from_soup(soup)   # <---- THIS IS MISSING
    game_dict["all_tables"] = tables_data

    # ================== MATCHUP PARSING =========================
    matchup = row["matchup"]

    # Default values
    awayRank = homeRank = None
    awayTeam = homeTeam = None
    site_type = None
    
    if isinstance(matchup, str) and (" at " in matchup or " vs. " in matchup):
        if " at " in matchup:
            parts = matchup.split(" at ")
            site_type = "True Road"
        else:
            parts = matchup.split(" vs. ")
            site_type = "Neutral"
    
        away_str, home_str = parts[0].strip(), parts[1].strip()
    
        def safe_parse(block):
            """Returns (rank, team) for strings like '#3 Kentucky' or 'Kentucky'"""
            if not isinstance(block, str):
                return None, None
            m = re.match(r"#?(\d+)?\s*(.*)", block)
            if not m:
                return None, block.strip()
            rank = m.group(1)
            team = m.group(2).strip()
            return rank, team
    
        awayRank, awayTeam = safe_parse(away_str)
        homeRank, homeTeam = safe_parse(home_str)
    
    # Store parsed matchup
    game_dict["away_rank"] = awayRank
    game_dict["away_team"] = awayTeam
    game_dict["home_rank"] = homeRank
    game_dict["home_team"] = homeTeam
    game_dict["site_type"] = site_type      # "True Road" or "Neutral" or None

    
    # ================== SPREAD FROM TABLES ====================
    spread_value = None
    
    try:
        all_tables = game_dict.get("all_tables", {})
    
        for name, rows in all_tables.items():
            if not rows:
                continue
    
            # get column names
            cols = list(rows[0].keys())
    
            # find the ATS Pick column (case-insensitive)
            ats_col = None
            for c in cols:
                if "ats pick" in str(c).lower():
                    ats_col = c
                    break
    
            # if this table has ATS Pick, extract the value
            if ats_col:
                # take the FIRST row's ATS Pick cell
                spread_value = rows[0][ats_col]
                break
    
    except Exception as e:
        print("Spread parse error:", e)
    
    # ================== SPLIT SPREAD INTO PARTS ====================
    fav_abbrev = None
    spread_num = None
    
    val = str(spread_value).strip() if spread_value else ""
    
    if val:
        # Cases like "KENT -2.5"
        m = re.match(r"([A-Za-z]+)\s*([+-]?\d*\.?\d+)", val)
        if m:
            fav_abbrev = m.group(1).upper()
            spread_num = float(m.group(2))
    
        # Case: "KENT PK" or "KENT EVEN"
        elif "PK" in val.upper() or "EVEN" in val.upper():
            parts = val.split()
            if len(parts) >= 1:
                fav_abbrev = parts[0].upper()
                spread_num = 0.0
    
    game_dict["spread_team_abbrev"] = fav_abbrev
    game_dict["spread_points"] = spread_num

    # ================== SCORE FROM TABLE_5 ====================
    away_points = None
    home_points = None
    
    try:
        for name, rows in game_dict["all_tables"].items():
            if len(rows) != 2:
                continue
    
            # Convert dict row → list
            r0 = list(rows[0].values())
            r1 = list(rows[1].values())
    
            # Score should be numeric or numeric-like
            if len(r0) >= 4 and len(r1) >= 4:
                # Column 3 (index 3) is points
                if str(r0[3]).isdigit() or str(r1[3]).isdigit():
                    away_points = r0[3]
                    home_points = r1[3]
                    break
    
    except:
        pass
    
    game_dict["away_points"] = away_points
    game_dict["home_points"] = home_points
    
    all_game_data.append(game_dict) 
    # Be polite to the server 
    time.sleep(1) 
all_data = pd.DataFrame(all_game_data)
all_data = all_data.drop(columns=(['rank', 'hotness', 'all_tables']))
all_data.to_csv("collegebasketballcatchup4.csv", mode = 'a', index=False, header=False)

