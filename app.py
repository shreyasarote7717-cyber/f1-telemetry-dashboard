import os
from datetime import datetime
import streamlit as st
import fastf1
from fastf1.ergast import Ergast
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# 1. Setup Local Cache
CACHE_DIR = 'f1_cache'
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
fastf1.Cache.enable_cache(CACHE_DIR)

st.set_page_config(page_title="FORMULA 1 TELEMETRY & PERFORMANCE HUB", layout="wide")

# 2. Formula 1 Typography & Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Titillium+Web:ital,wght@0,300;0,400;0,600;0,700;0,900;1,700&display=swap');
    
    * {
        font-family: 'Titillium Web', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    .f1-title {
        font-size: 2.2rem;
        font-weight: 900;
        font-style: italic;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: #FFFFFF;
        border-bottom: 3px solid #E10600;
        padding-bottom: 8px;
        margin-bottom: 20px;
    }
    
    .f1-card {
        background-color: #15151E;
        border-radius: 4px;
        padding: 10px 14px;
        margin-bottom: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .f1-pos {
        font-size: 1.3rem;
        font-weight: 900;
        font-style: italic;
        width: 38px;
        color: #FFFFFF;
    }
    
    .f1-driver-name {
        font-size: 1.05rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #FFFFFF;
        margin: 0;
    }
    
    .f1-team-sub {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .f1-points {
        font-size: 1.25rem;
        font-weight: 900;
        font-style: italic;
        color: #FFF200;
        text-align: right;
    }
    
    .f1-pts-label {
        font-size: 0.7rem;
        font-weight: 700;
        color: #949498;
        text-transform: uppercase;
    }
    
    .driver-img {
        border-radius: 50%;
        width: 52px;
        height: 52px;
        object-fit: cover;
        border: 2px solid #38383F;
    }
</style>
""", unsafe_allow_html=True)

# Official Team Hex Mappings
TEAM_COLORS = {
    'Red Bull Racing': '#3671C6', 'Ferrari': '#E80020', 'Mercedes': '#27F4D2',
    'McLaren': '#FF8000', 'Aston Martin': '#229971', 'Alpine': '#0093CC',
    'Williams': '#64C4FF', 'AlphaTauri': '#5E8FAA', 'RB': '#6692FF',
    'Sauber': '#52E252', 'Kick Sauber': '#52E252', 'Alfa Romeo': '#C92D4B', 'Haas F1 Team': '#B6BABD'
}

COMPOUND_COLORS = {
    'SOFT': '#FF3333', 'MEDIUM': '#FFF200', 'HARD': '#FFFFFF',
    'INTERMEDIATE': '#39B54A', 'WET': '#00AEEF', 'UNKNOWN': '#888888'
}

# Driver Profile Modal Popup
@st.dialog("DRIVER PROFILE & SEASON METRICS", width="medium")
def show_driver_popup(driver_info, season_year, podium_count):
    dob_str = driver_info.get('dateOfBirth', '')
    age_str = "N/A"
    if dob_str:
        try:
            birth_year = datetime.strptime(dob_str, "%Y-%m-%d").year
            age_str = f"{int(season_year) - birth_year} YRS (IN {season_year})"
        except Exception:
            pass

    full_name = f"{driver_info.get('givenName', '')} {driver_info.get('familyName', '')}".upper()
    team_name = driver_info.get('constructorNames', ['N/A'])[0] if isinstance(driver_info.get('constructorNames'), list) else driver_info.get('constructorNames', 'N/A')
    team_color = TEAM_COLORS.get(team_name, "#E10600")

    col_img, col_bio = st.columns([1, 2])
    with col_img:
        st.image(
            driver_info.get('headshot_url') or f"https://ui-avatars.com/api/?name={full_name}&background=15151E&color=fff&size=200",
            width=120
        )
    with col_bio:
        st.markdown(f"<h2 style='margin:0; font-weight:900; font-style:italic;'>{full_name}</h2>", unsafe_allow_html=True)
        st.markdown(f"<span style='color:{team_color}; font-size:1rem; font-weight:700; text-transform:uppercase;'>#{driver_info.get('permanentNumber', '-')} | {team_name}</span>", unsafe_allow_html=True)
        st.markdown(f"**NATIONALITY:** {str(driver_info.get('nationality', 'N/A')).upper()}")
        st.markdown(f"**AGE:** {age_str} (DOB: {dob_str})")

    st.markdown("---")
    st.markdown(f"<h4 style='font-weight:800; text-transform:uppercase;'>{season_year} CAMPAIGN RECORD</h4>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("POSITION", f"P{driver_info.get('position', '-')}")
    m2.metric("POINTS", f"{driver_info.get('points', 0)} PTS")
    m3.metric("VICTORIES", f"{driver_info.get('wins', 0)}")
    m4.metric("PODIUMS", f"{podium_count}")

    if driver_info.get('url'):
        st.markdown(f"[OFFICIAL BIOGRAPHY & ARCHIVE]({driver_info.get('url')})")

# 3. Sidebar Controls
st.sidebar.markdown("<h3 style='font-weight:900; font-style:italic; letter-spacing:1px;'>SESSION CONTROL</h3>", unsafe_allow_html=True)
selected_year = st.sidebar.selectbox("SEASON", list(range(2026, 2017, -1)), index=0)

@st.cache_data(show_spinner="Loading Event Calendar...")
def get_season_schedule(yr):
    schedule = fastf1.get_event_schedule(yr, include_testing=False)
    return schedule[['RoundNumber', 'EventName']].dropna()

schedule_df = get_season_schedule(selected_year)
race_options = dict(zip(schedule_df['EventName'], schedule_df['RoundNumber']))

if not race_options:
    st.sidebar.warning(f"No scheduled Grand Prix rounds found for {selected_year}.")
    st.stop()

selected_event_name = st.sidebar.selectbox("GRAND PRIX", list(race_options.keys()), index=0)
selected_round = race_options[selected_event_name]
session_choice = st.sidebar.selectbox("SESSION", ["Race (R)", "Qualifying (Q)", "Sprint (S)", "FP1", "FP2", "FP3"], index=0)
st_code = session_choice.split("(")[-1].replace(")", "").strip()

# 4. Data Extraction for Entire Season (Podiums & Points Progression)
@st.cache_data(show_spinner=f"Analyzing {selected_year} Season Results & Podiums...")
def get_season_progression_and_podiums(yr):
    erg = Ergast()
    races_resp = erg.get_race_schedule(yr)
    if races_resp.empty:
        return pd.DataFrame(), {}
    
    all_results = []
    podium_totals = {}
    
    for rnd_idx, row in races_resp.iterrows():
        rnd_num = rnd_idx + 1
        r_name = row.get('raceName', f"Round {rnd_num}")
        try:
            res_obj = erg.get_race_results(season=yr, round=rnd_num)
            if res_obj.content:
                df_rnd = res_obj.content[0].copy()
                df_rnd['Round'] = rnd_num
                df_rnd['RaceName'] = r_name
                
                # Check for podiums (Top 3)
                for _, d_row in df_rnd.iterrows():
                    d_code = d_row.get('driverCode', d_row.get('driverId', ''))
                    pos = pd.to_numeric(d_row.get('position', 99), errors='coerce')
                    if pos in [1, 2, 3]:
                        podium_totals[d_code] = podium_totals.get(d_code, 0) + 1
                        
                all_results.append(df_rnd[['Round', 'RaceName', 'driverCode', 'points', 'position']])
        except Exception:
            continue
            
    if all_results:
        full_df = pd.concat(all_results, ignore_index=True)
        full_df['points'] = pd.to_numeric(full_df['points'], errors='coerce').fillna(0)
        return full_df, podium_totals
    return pd.DataFrame(), podium_totals

season_race_results, season_podiums = get_season_progression_and_podiums(selected_year)

# 5. Session Loading
# Replace the session loading section in app.py with this:

session = None
available_drivers = []

try:
    with st.spinner(f"Loading session data for {selected_year} {selected_event_name}..."):
        session = fastf1.get_session(selected_year, selected_round, st_code)
        session.load(telemetry=True, laps=True, weather=False)
        
        if hasattr(session, 'laps') and not session.laps.empty:
            available_drivers = sorted(session.laps['Driver'].dropna().unique().tolist())
        else:
            st.info(f"No lap timing data is available yet for this session ({selected_year} {selected_event_name}).")
except Exception as e:
    st.info(f"Session data not available for {selected_year} {selected_event_name} ({st_code}): {e}")

# Application Main Title
st.markdown(f"<div class='f1-title'>FIA FORMULA 1 WORLD CHAMPIONSHIP - {selected_year} {selected_event_name.upper()}</div>", unsafe_allow_html=True)

# Navigation Tabs
tab_standings, tab_points_prog, tab_telemetry, tab_elevation, tab_speedtrap, tab_strategy, tab_pace = st.tabs([
    "STANDINGS & PROFILES",
    "POINTS PROGRESSION & RACES",
    "LAP TELEMETRY", 
    "3D TOPOGRAPHY",
    "SPEED TRAP RANKINGS",
    "TYRE STRATEGY", 
    "RACE PACE ANALYSIS"
])

# =========================================================
# TAB 1: STANDINGS & DRIVER CARDS (WITH ACCURATE PODIUMS)
# =========================================================
with tab_standings:
    col_d, col_c = st.columns([3, 2])
    ergast = Ergast()
    
    with col_d:
        st.markdown("<h4 style='font-weight:900; font-style:italic; text-transform:uppercase;'>DRIVERS CHAMPIONSHIP STANDINGS</h4>", unsafe_allow_html=True)
        try:
            d_resp = ergast.get_driver_standings(season=selected_year, round='last')
            d_standings = d_resp.content[0]
            
            headshots = {}
            try:
                openf1_resp = requests.get("https://api.openf1.org/v1/drivers?meeting_key=latest", timeout=3).json()
                for d in openf1_resp:
                    headshots[d.get('name_acronym', '')] = d.get('headshot_url')
            except Exception:
                pass

            for idx, row in d_standings.head(22).iterrows():
                pos = row.get('position', '-')
                driver_code = row.get('driverCode', '')
                given_name = row.get('givenName', '')
                family_name = row.get('familyName', '')
                full_name = f"{given_name} {family_name}"
                points = row.get('points', 0)
                d_number = row.get('permanentNumber', '#')
                team_name = row.get('constructorNames', [''])[0] if isinstance(row.get('constructorNames'), list) else row.get('constructorNames', '')
                img_url = headshots.get(driver_code) or f"https://ui-avatars.com/api/?name={given_name}+{family_name}&background=15151E&color=fff"
                team_color = TEAM_COLORS.get(team_name, "#E10600")
                podiums = season_podiums.get(driver_code, 0)

                c_left, c_right = st.columns([5, 1])
                with c_left:
                    st.markdown(f"""
                    <div class="f1-card" style="border-left: 6px solid {team_color};">
                        <div style="display: flex; align-items: center; gap: 14px;">
                            <span class="f1-pos">P{pos}</span>
                            <img src="{img_url}" class="driver-img" onerror="this.src='https://ui-avatars.com/api/?name={driver_code}&background=15151E&color=fff'"/>
                            <div>
                                <p class="f1-driver-name">#{d_number} {full_name} <span style="color:#949498;">({driver_code})</span></p>
                                <span class="f1-team-sub" style="color: {team_color};">{team_name} | {podiums} PODIUMS</span>
                            </div>
                        </div>
                        <div>
                            <div class="f1-points">{points}</div>
                            <div class="f1-pts-label">PTS</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with c_right:
                    st.write("")
                    if st.button("PROFILE", key=f"btn_{driver_code}_{idx}", use_container_width=True):
                        d_dict = row.to_dict()
                        d_dict['headshot_url'] = img_url
                        show_driver_popup(d_dict, selected_year, podiums)
        except Exception as e:
            st.info(f"Driver standings unavailable for {selected_year}: {e}")

    with col_c:
        st.markdown("<h4 style='font-weight:900; font-style:italic; text-transform:uppercase;'>CONSTRUCTORS CHAMPIONSHIP</h4>", unsafe_allow_html=True)
        try:
            c_resp = ergast.get_constructor_standings(season=selected_year, round='last')
            c_standings = c_resp.content[0]

            for _, row in c_standings.iterrows():
                pos = row.get('position', '-')
                team_name = row.get('constructorName', '')
                points = row.get('points', 0)
                team_color = TEAM_COLORS.get(team_name, "#555555")

                st.markdown(f"""
                <div class="f1-card" style="border-left: 6px solid {team_color};">
                    <div style="display: flex; align-items: center; gap: 14px;">
                        <span class="f1-pos">P{pos}</span>
                        <div class="f1-driver-name" style="color: {team_color};">{team_name}</div>
                    </div>
                    <div>
                        <div class="f1-points">{points}</div>
                        <div class="f1-pts-label">PTS</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            fig_teams = px.pie(
                c_standings, values='points', names='constructorName',
                title=f"{selected_year} CONSTRUCTOR POINTS SHARE",
                template="plotly_dark", color='constructorName', color_discrete_map=TEAM_COLORS
            )
            fig_teams.update_traces(textposition='inside', textinfo='percent+label')
            fig_teams.update_layout(height=360, showlegend=False, font=dict(family="Titillium Web"))
            st.plotly_chart(fig_teams, use_container_width=True)
        except Exception as e:
            st.info(f"Constructor standings unavailable: {e}")

# =========================================================
# TAB 2: POINTS PROGRESSION & RACE-BY-RACE BREAKDOWN
# =========================================================
with tab_points_prog:
    st.markdown("<h4 style='font-weight:900; text-transform:uppercase;'>SEASON POINTS PROGRESSION & RACE ACQUISITION</h4>", unsafe_allow_html=True)
    
    if not season_race_results.empty:
        all_res_drivers = sorted(season_race_results['driverCode'].dropna().unique().tolist())
        
        # Filters Row
        flt_col1, flt_col2 = st.columns([1, 2])
        with flt_col1:
            view_mode = st.radio(
                "SELECT POINTS VIEW MODE",
                ["CUMULATIVE CHAMPIONSHIP POINTS", "POINTS SCORED PER RACE"],
                index=0
            )
        with flt_col2:
            selected_prog_drivers = st.multiselect(
                "FILTER DRIVERS TO DISPLAY",
                all_res_drivers,
                default=all_res_drivers[:6]
            )

        if selected_prog_drivers:
            filt_df = season_race_results[season_race_results['driverCode'].isin(selected_prog_drivers)].copy()
            
            # Pivot table to organize by race round
            pivot_pts = filt_df.pivot_table(index='RaceName', columns='driverCode', values='points', aggfunc='sum', sort=False).fillna(0)
            
            if view_mode == "CUMULATIVE CHAMPIONSHIP POINTS":
                plot_data = pivot_pts.cumsum().reset_index()
                y_label = "TOTAL CHAMPIONSHIP POINTS"
                chart_title = f"{selected_year} CUMULATIVE POINTS TRAJECTORY"
            else:
                plot_data = pivot_pts.reset_index()
                y_label = "POINTS SCORED IN ROUND"
                chart_title = f"{selected_year} POINTS SCORED PER INDIVIDUAL ROUND"

            fig_pts = px.line(
                plot_data,
                x='RaceName',
                y=selected_prog_drivers,
                markers=True,
                template="plotly_dark",
                labels={'value': y_label, 'RaceName': 'GRAND PRIX ROUND', 'variable': 'DRIVER'},
                title=chart_title
            )
            fig_pts.update_layout(
                height=520, 
                hovermode="x unified",
                font=dict(family="Titillium Web"),
                xaxis=dict(tickangle=-45)
            )
            st.plotly_chart(fig_pts, use_container_width=True)

            # Tabular breakdown
            st.markdown("<h5 style='font-weight:800; text-transform:uppercase;'>ROUND-BY-ROUND POINTS MATRIX</h5>", unsafe_allow_html=True)
            st.dataframe(pivot_pts.T, use_container_width=True)
        else:
            st.warning("Please select at least one driver from the filter above.")
    else:
        st.info(f"No completed race results available yet for {selected_year}.")

# =========================================================
# TAB 3: TELEMETRY & ACCELERATION
# =========================================================
with tab_telemetry:
    if available_drivers:
        st.markdown("<h4 style='font-weight:900; text-transform:uppercase;'>FASTEST LAP TELEMETRY TRACE</h4>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            d1 = st.selectbox("DRIVER 1", available_drivers, index=0)
        with c2:
            d2 = st.selectbox("DRIVER 2 (COMPARISON)", available_drivers, index=1 if len(available_drivers) > 1 else 0)

        lap1 = session.laps.pick_driver(d1).pick_fastest()
        lap2 = session.laps.pick_driver(d2).pick_fastest()

        if lap1 is not None and lap2 is not None:
            def process_tel(lap):
                tel = lap.get_telemetry().add_distance()
                speed_ms = tel['Speed'] / 3.6
                time_s = tel['Time'].dt.total_seconds()
                tel['Longitudinal_G'] = np.gradient(speed_ms, time_s) / 9.81
                return tel

            tel1 = process_tel(lap1)
            tel2 = process_tel(lap2)

            fig_tel = make_subplots(
                rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                subplot_titles=("SPEED (KM/H)", "LONGITUDINAL ACCELERATION (G-FORCE)", "THROTTLE INPUT (%)", "BRAKE APPLICATION")
            )

            fig_tel.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Speed'], name=f"{d1} Speed", line=dict(color='#E10600', width=1.8)), row=1, col=1)
            fig_tel.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Speed'], name=f"{d2} Speed", line=dict(color='#00D2BE', width=1.8)), row=1, col=1)

            fig_tel.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Longitudinal_G'], name=f"{d1} G", line=dict(color='#E10600', width=1.8)), row=2, col=1)
            fig_tel.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Longitudinal_G'], name=f"{d2} G", line=dict(color='#00D2BE', width=1.8)), row=2, col=1)

            fig_tel.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Throttle'], name=f"{d1} Throttle", line=dict(color='#E10600', width=1.8)), row=3, col=1)
            fig_tel.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Throttle'], name=f"{d2} Throttle", line=dict(color='#00D2BE', width=1.8)), row=3, col=1)

            fig_tel.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Brake'].astype(int), name=f"{d1} Brake", line=dict(color='#E10600', width=1.8)), row=4, col=1)
            fig_tel.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Brake'].astype(int), name=f"{d2} Brake", line=dict(color='#00D2BE', width=1.8)), row=4, col=1)

            fig_tel.update_layout(
                height=720, template="plotly_dark", hovermode="x unified",
                font=dict(family="Titillium Web"), margin=dict(l=10, r=10, t=30, b=10)
            )
            st.plotly_chart(fig_tel, use_container_width=True)

            st.markdown(f"<h4 style='font-weight:900; text-transform:uppercase;'>CIRCUIT ACCELERATION & BRAKING PROFILE ({d1})</h4>", unsafe_allow_html=True)
            fig_track = go.Figure(data=go.Scatter(
                x=tel1['X'], y=tel1['Y'], mode='markers',
                marker=dict(size=3.5, color=tel1['Longitudinal_G'], colorscale='RdBu', cmin=-4, cmax=2, colorbar=dict(title="LONGITUDINAL G")),
                hovertext=tel1['Speed'].apply(lambda s: f"{s:.1f} KM/H")
            ))
            fig_track.update_layout(template="plotly_dark", xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), height=480)
            st.plotly_chart(fig_track, use_container_width=True)
    else:
        st.info("No session loaded to display telemetry traces.")

# =========================================================
# TAB 4: 3D TRACK TOPOGRAPHY
# =========================================================
with tab_elevation:
    if available_drivers:
        st.markdown("<h4 style='font-weight:900; text-transform:uppercase;'>3D CIRCUIT TOPOGRAPHY & ELEVATION</h4>", unsafe_allow_html=True)
        elev_driver = st.selectbox("SELECT DRIVER PATH", available_drivers, index=0, key="elev_driver")
        ref_lap = session.laps.pick_driver(elev_driver).pick_fastest()
        
        if ref_lap is not None:
            tel_3d = ref_lap.get_telemetry()
            x_m = tel_3d['X'] / 10
            y_m = tel_3d['Y'] / 10
            z_m = tel_3d['Z'] / 10
            
            c_e1, c_e2, c_e3 = st.columns(3)
            c_e1.metric("HIGHEST ELEVATION", f"{z_m.max():.1f} M")
            c_e2.metric("LOWEST ELEVATION", f"{z_m.min():.1f} M")
            c_e3.metric("VERTICAL DELTA", f"{z_m.max() - z_m.min():.1f} M")

            fig_3d = go.Figure(data=[go.Scatter3d(
                x=x_m, y=y_m, z=z_m, mode='lines',
                line=dict(color=tel_3d['Speed'], colorscale='Turbo', width=6, colorbar=dict(title="SPEED (KM/H)")),
                hovertext=tel_3d.apply(lambda r: f"Speed: {r['Speed']:.1f} km/h | Elev: {r['Z']/10:.1f}m", axis=1)
            )])

            fig_3d.update_layout(
                template="plotly_dark",
                scene=dict(xaxis=dict(title="X (M)"), yaxis=dict(title="Y (M)"), zaxis=dict(title="ELEVATION (M)"), aspectmode='data'),
                font=dict(family="Titillium Web"), height=600, margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_3d, use_container_width=True)
    else:
        st.info("No session loaded for 3D elevation.")

# =========================================================
# TAB 5: SPEED TRAP
# =========================================================
with tab_speedtrap:
    if available_drivers:
        st.markdown("<h4 style='font-weight:900; text-transform:uppercase;'>SPEED TRAP & PEAK VELOCITY RANKINGS</h4>", unsafe_allow_html=True)
        speed_records = []
        for drv in available_drivers:
            drv_laps = session.laps.pick_driver(drv)
            if not drv_laps.empty:
                st_speed = drv_laps['SpeedST'].max() if 'SpeedST' in drv_laps else np.nan
                try:
                    fastest_tel = drv_laps.pick_fastest().get_telemetry()
                    peak_speed = fastest_tel['Speed'].max()
                except Exception:
                    peak_speed = np.nan
                
                speed_records.append({
                    'DRIVER': drv,
                    'RADAR SPEED TRAP (KM/H)': st_speed,
                    'PEAK TELEMETRY SPEED (KM/H)': peak_speed
                })

        speed_df = pd.DataFrame(speed_records).sort_values(by='PEAK TELEMETRY SPEED (KM/H)', ascending=False).reset_index(drop=True)
        speed_df.index += 1

        c_s1, c_s2 = st.columns([3, 2])
        with c_s1:
            fig_speed = px.bar(
                speed_df.sort_values(by='PEAK TELEMETRY SPEED (KM/H)', ascending=True),
                x='PEAK TELEMETRY SPEED (KM/H)', y='DRIVER', orientation='h',
                text='PEAK TELEMETRY SPEED (KM/H)', color='PEAK TELEMETRY SPEED (KM/H)',
                color_continuous_scale='Magma', template="plotly_dark",
                title="PEAK VELOCITY RECORDED (KM/H)"
            )
            fig_speed.update_traces(texttemplate='%{text:.1f} KM/H', textposition='inside')
            fig_speed.update_layout(height=550, showlegend=False, font=dict(family="Titillium Web"))
            st.plotly_chart(fig_speed, use_container_width=True)
            
        with c_s2:
            st.markdown("<h5 style='font-weight:800; text-transform:uppercase;'>OFFICIAL SPEED TRAP TIMING</h5>", unsafe_allow_html=True)
            st.dataframe(speed_df, use_container_width=True, height=500)
    else:
        st.info("No speed trap data available.")

# =========================================================
# TAB 6: TYRE STRATEGY
# =========================================================
with tab_strategy:
    if available_drivers:
        st.markdown("<h4 style='font-weight:900; text-transform:uppercase;'>TYRE COMPOUND STINT TIMELINES</h4>", unsafe_allow_html=True)
        stints = session.laps[['Driver', 'Stint', 'Compound', 'LapNumber']].groupby(['Driver', 'Stint', 'Compound']).agg(
            StartLap=('LapNumber', 'min'),
            EndLap=('LapNumber', 'max'),
            TotalLaps=('LapNumber', 'count')
        ).reset_index()

        if not stints.empty:
            fig_stints = go.Figure()
            for _, row in stints.iterrows():
                comp = str(row['Compound']).upper()
                c_color = COMPOUND_COLORS.get(comp, '#888888')
                fig_stints.add_trace(go.Bar(
                    x=[row['TotalLaps']], y=[row['Driver']],
                    base=row['StartLap'] - 1, orientation='h',
                    marker=dict(color=c_color, line=dict(color='#111', width=1)),
                    name=comp,
                    hovertext=f"{row['Driver']} - Stint {row['Stint']}: {comp} ({row['TotalLaps']} laps)",
                    hoverinfo="text", showlegend=False
                ))

            fig_stints.update_layout(
                template="plotly_dark", barmode='stack', 
                xaxis=dict(title="LAP NUMBER"), yaxis=dict(title="DRIVER", autorange="reversed"), 
                font=dict(family="Titillium Web"), height=550
            )
            st.plotly_chart(fig_stints, use_container_width=True)
    else:
        st.info("No tyre data available.")

# =========================================================
# TAB 7: RACE PACE
# =========================================================
with tab_pace:
    if available_drivers:
        st.markdown("<h4 style='font-weight:900; text-transform:uppercase;'>LAP TIME CONSISTENCY & SPREAD</h4>", unsafe_allow_html=True)
        valid_laps = session.laps.pick_quicklaps().copy()
        
        if not valid_laps.empty:
            valid_laps['LapTime_Seconds'] = valid_laps['LapTime'].dt.total_seconds()
            fig_pace = px.box(
                valid_laps, x='Driver', y='LapTime_Seconds', color='Driver', 
                template="plotly_dark", title="REPRESENTATIVE CLEAN LAP TIMES (SECONDS)"
            )
            fig_pace.update_layout(showlegend=False, height=500, font=dict(family="Titillium Web"))
            st.plotly_chart(fig_pace, use_container_width=True)
        else:
            st.info("No clean quick laps recorded for pace distribution.")
    else:
        st.info("No race pace data available.")