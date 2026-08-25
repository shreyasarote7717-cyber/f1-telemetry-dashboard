import os
import tempfile
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

# 1. Cloud-Safe Cache Directory
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'f1_fastf1_cache')
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

st.set_page_config(page_title="FORMULA 1 TELEMETRY & PERFORMANCE HUB", layout="wide")

# 2. Formula 1 Broadcast Typography & Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Titillium+Web:ital,wght@0,300;0,400;0,600;0,700;0,900;1,700&display=swap');
    * { font-family: 'Titillium Web', -apple-system, BlinkMacSystemFont, sans-serif !important; }
    .f1-title {
        font-size: 2.1rem; font-weight: 900; font-style: italic;
        text-transform: uppercase; letter-spacing: 1.5px; color: #FFFFFF;
        border-bottom: 3px solid #E10600; padding-bottom: 8px; margin-bottom: 20px;
    }
    .f1-card {
        background-color: #15151E; border-radius: 4px; padding: 10px 14px;
        margin-bottom: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.5);
        display: flex; align-items: center; justify-content: space-between;
    }
    .f1-pos { font-size: 1.3rem; font-weight: 900; font-style: italic; width: 38px; color: #FFFFFF; }
    .f1-driver-name { font-size: 1.05rem; font-weight: 700; text-transform: uppercase; color: #FFFFFF; margin: 0; }
    .f1-team-sub { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
    .f1-points { font-size: 1.25rem; font-weight: 900; font-style: italic; color: #FFF200; text-align: right; }
    .f1-pts-label { font-size: 0.7rem; font-weight: 700; color: #949498; text-transform: uppercase; }
    .driver-img { border-radius: 50%; width: 52px; height: 52px; object-fit: cover; border: 2px solid #38383F; }
</style>
""", unsafe_allow_html=True)

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

# Modal Popup for Driver Biography & Year Statistics
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
        st.image(driver_info.get('headshot_url') or f"https://ui-avatars.com/api/?name={full_name}&background=15151E&color=fff&size=200", width=120)
    with col_bio:
        st.markdown(f"<h2 style='margin:0; font-weight:900; font-style:italic;'>{full_name}</h2>", unsafe_allow_html=True)
        st.markdown(f"<span style='color:{team_color}; font-size:1rem; font-weight:700;'>#{driver_info.get('permanentNumber', '-')} | {team_name}</span>", unsafe_allow_html=True)
        st.markdown(f"**NATIONALITY:** {str(driver_info.get('nationality', 'N/A')).upper()}")
        st.markdown(f"**AGE:** {age_str} (DOB: {dob_str})")

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("CHAMPIONSHIP POS", f"P{driver_info.get('position', '-')}")
    m2.metric("TOTAL POINTS", f"{driver_info.get('points', 0)} PTS")
    m3.metric("VICTORIES", f"{driver_info.get('wins', 0)}")
    m4.metric("PODIUMS", f"{podium_count}")

# 3. Sidebar Selection
st.sidebar.markdown("<h3 style='font-weight:900; font-style:italic;'>SESSION CONTROL</h3>", unsafe_allow_html=True)
year_list = list(range(2026, 2017, -1))
# Defaults to 2024 (index 2) so telemetry is fully populated on startup
selected_year = st.sidebar.selectbox("SEASON", year_list, index=2)

@st.cache_data(show_spinner=False)
def get_season_schedule(yr):
    try:
        schedule = fastf1.get_event_schedule(yr, include_testing=False)
        return schedule[['RoundNumber', 'EventName']].dropna()
    except Exception:
        return pd.DataFrame(columns=['RoundNumber', 'EventName'])

schedule_df = get_season_schedule(selected_year)
race_options = dict(zip(schedule_df['EventName'], schedule_df['RoundNumber']))

if not race_options:
    st.sidebar.warning(f"No event schedule found for {selected_year}.")
    st.stop()

# Default to Silverstone / completed round
default_round_idx = min(11, len(race_options) - 1)
selected_event_name = st.sidebar.selectbox("GRAND PRIX", list(race_options.keys()), index=default_round_idx)
selected_round = race_options[selected_event_name]
session_choice = st.sidebar.selectbox("SESSION", ["Race (R)", "Qualifying (Q)", "Sprint (S)", "FP1", "FP2", "FP3"], index=0)
st_code = session_choice.split("(")[-1].replace(")", "").strip()

# 4. Accurate Podiums & Points Calculation
@st.cache_data(show_spinner=False)
def get_season_progression_and_podiums(yr):
    erg = Ergast()
    try:
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
    except Exception:
        pass
    return pd.DataFrame(), {}

season_race_results, season_podiums = get_season_progression_and_podiums(selected_year)

# 5. Session Loading with Resource Caching (Prevents Cloud Memory Crashes)
@st.cache_resource(show_spinner=False)
def get_loaded_f1_session(season_yr, event_str, session_type_code):
    try:
        sess = fastf1.get_session(int(season_yr), str(event_str), str(session_type_code))
        sess.load(telemetry=True, laps=True, weather=False)
        return sess
    except Exception:
        return None

session = None
available_drivers = []

with st.spinner(f"Loading Telemetry for {selected_year} {selected_event_name} ({st_code})..."):
    session = get_loaded_f1_session(selected_year, selected_event_name, st_code)
    if session is not None and hasattr(session, 'laps') and not session.laps.empty:
        valid_laps_df = session.laps.dropna(subset=['LapTime', 'LapNumber'])
        if not valid_laps_df.empty:
            for d_code in sorted(valid_laps_df['Driver'].unique().tolist()):
                try:
                    drv_fastest = valid_laps_df.pick_driver(d_code).pick_fastest()
                    if drv_fastest is not None:
                        _ = drv_fastest.get_telemetry()
                        available_drivers.append(d_code)
                except Exception:
                    continue

st.markdown(f"<div class='f1-title'>FIA FORMULA 1 WORLD CHAMPIONSHIP - {selected_year} {selected_event_name.upper()}</div>", unsafe_allow_html=True)

tab_standings, tab_points_prog, tab_telemetry, tab_elevation, tab_speedtrap, tab_strategy, tab_pace = st.tabs([
    "STANDINGS & PROFILES",
    "POINTS PROGRESSION",
    "LAP TELEMETRY", 
    "3D TOPOGRAPHY",
    "SPEED TRAP RANKINGS",
    "TYRE STRATEGY", 
    "RACE PACE ANALYSIS"
])

# =========================================================
# TAB 1: STANDINGS & PROFILES
# =========================================================
with tab_standings:
    col_d, col_c = st.columns([3, 2])
    ergast = Ergast()
    with col_d:
        st.markdown("<h4 style='font-weight:900; font-style:italic;'>DRIVERS CHAMPIONSHIP</h4>", unsafe_allow_html=True)
        try:
            d_resp = ergast.get_driver_standings(season=selected_year, round='last')
            d_standings = d_resp.content[0]
            headshots = {}
            try:
                openf1_resp = requests.get("https://api.openf1.org/v1/drivers?meeting_key=latest", timeout=2).json()
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
                        <div><div class="f1-points">{points}</div><div class="f1-pts-label">PTS</div></div>
                    </div>
                    """, unsafe_allow_html=True)
                with c_right:
                    st.write("")
                    if st.button("PROFILE", key=f"btn_{driver_code}_{idx}", use_container_width=True):
                        d_dict = row.to_dict()
                        d_dict['headshot_url'] = img_url
                        show_driver_popup(d_dict, selected_year, podiums)
        except Exception as e:
            st.info(f"Driver standings currently unavailable for {selected_year}: {e}")

    with col_c:
        st.markdown("<h4 style='font-weight:900; font-style:italic;'>CONSTRUCTORS CHAMPIONSHIP</h4>", unsafe_allow_html=True)
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
                    <div><div class="f1-points">{points}</div><div class="f1-pts-label">PTS</div></div>
                </div>
                """, unsafe_allow_html=True)
            fig_teams = px.pie(
                c_standings, values='points', names='constructorName',
                title=f"{selected_year} POINTS SHARE", template="plotly_dark",
                color='constructorName', color_discrete_map=TEAM_COLORS
            )
            fig_teams.update_traces(textposition='inside', textinfo='percent+label')
            fig_teams.update_layout(height=360, showlegend=False, font=dict(family="Titillium Web"))
            st.plotly_chart(fig_teams, use_container_width=True)
        except Exception as e:
            st.info(f"Constructor standings currently unavailable: {e}")

# =========================================================
# TAB 2: POINTS PROGRESSION & RACE ACQUISITION
# =========================================================
with tab_points_prog:
    if not season_race_results.empty:
        all_res_drivers = sorted(season_race_results['driverCode'].dropna().unique().tolist())
        flt_col1, flt_col2 = st.columns([1, 2])
        with flt_col1:
            view_mode = st.radio("SELECT POINTS MODE", ["CUMULATIVE CHAMPIONSHIP POINTS", "POINTS SCORED PER RACE"])
        with flt_col2:
            selected_prog_drivers = st.multiselect("FILTER DRIVERS", all_res_drivers, default=all_res_drivers[:6])

        if selected_prog_drivers:
            filt_df = season_race_results[season_race_results['driverCode'].isin(selected_prog_drivers)].copy()
            pivot_pts = filt_df.pivot_table(index='RaceName', columns='driverCode', values='points', aggfunc='sum', sort=False).fillna(0)
            plot_data = pivot_pts.cumsum().reset_index() if view_mode == "CUMULATIVE CHAMPIONSHIP POINTS" else pivot_pts.reset_index()
            y_axis_label = "TOTAL CHAMPIONSHIP POINTS" if view_mode == "CUMULATIVE CHAMPIONSHIP POINTS" else "ROUND POINTS SCORED"
            fig_pts = px.line(
                plot_data, x='RaceName', y=selected_prog_drivers, markers=True, template="plotly_dark",
                labels={'value': y_axis_label, 'RaceName': 'GRAND PRIX ROUND', 'variable': 'DRIVER'}
            )
            fig_pts.update_layout(height=520, hovermode="x unified", font=dict(family="Titillium Web"), xaxis=dict(tickangle=-45))
            st.plotly_chart(fig_pts, use_container_width=True)
            st.markdown("<h5 style='font-weight:800; text-transform:uppercase;'>ROUND-BY-ROUND POINTS MATRIX</h5>", unsafe_allow_html=True)
            st.dataframe(pivot_pts.T, use_container_width=True)
    else:
        st.info(f"No completed race progression data found for {selected_year}.")

# =========================================================
# TAB 3: LAP TELEMETRY & ACCELERATION
# =========================================================
with tab_telemetry:
    if available_drivers and session is not None:
        st.markdown("<h4 style='font-weight:900; text-transform:uppercase;'>HEAD-TO-HEAD LAP TELEMETRY TRACE</h4>", unsafe_allow_html=True)
        
        d1_idx = available_drivers.index('HAM') if 'HAM' in available_drivers else 0
        d2_idx = available_drivers.index('VER') if 'VER' in available_drivers else (1 if len(available_drivers) > 1 else 0)
        
        col_drv1, col_drv2 = st.columns(2)
        with col_drv1:
            driver1 = st.selectbox("DRIVER 1 (BASE)", available_drivers, index=d1_idx, key="sel_drv1")
        with col_drv2:
            driver2 = st.selectbox("DRIVER 2 (COMPARISON)", available_drivers, index=d2_idx, key="sel_drv2")

        try:
            lap1 = session.laps.pick_driver(driver1).pick_fastest()
            lap2 = session.laps.pick_driver(driver2).pick_fastest()

            if lap1 is None or lap2 is None:
                st.warning("Selected driver does not have a completed flying lap.")
            else:
                t1 = lap1.get_telemetry().add_distance()
                t2 = lap2.get_telemetry().add_distance()

                t1['Time_Sec'] = t1['Time'].dt.total_seconds()
                t2['Time_Sec'] = t2['Time'].dt.total_seconds()
                
                t1['Longitudinal_G'] = np.gradient(t1['Speed'] / 3.6, t1['Time_Sec']) / 9.81
                t2['Longitudinal_G'] = np.gradient(t2['Speed'] / 3.6, t2['Time_Sec']) / 9.81

                fig_tel = make_subplots(
                    rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                    subplot_titles=("SPEED (KM/H)", "LONGITUDINAL ACCEL (G-FORCE)", "THROTTLE INPUT (%)", "BRAKE INPUT")
                )

                fig_tel.add_trace(go.Scatter(x=t1['Distance'], y=t1['Speed'], name=f"{driver1} Speed", line=dict(color='#E10600', width=1.8)), row=1, col=1)
                fig_tel.add_trace(go.Scatter(x=t2['Distance'], y=t2['Speed'], name=f"{driver2} Speed", line=dict(color='#00D2BE', width=1.8)), row=1, col=1)

                fig_tel.add_trace(go.Scatter(x=t1['Distance'], y=t1['Longitudinal_G'], name=f"{driver1} G", line=dict(color='#E10600', width=1.8)), row=2, col=1)
                fig_tel.add_trace(go.Scatter(x=t2['Distance'], y=t2['Longitudinal_G'], name=f"{driver2} G", line=dict(color='#00D2BE', width=1.8)), row=2, col=1)

                fig_tel.add_trace(go.Scatter(x=t1['Distance'], y=t1['Throttle'], name=f"{driver1} Throttle", line=dict(color='#E10600', width=1.8)), row=3, col=1)
                fig_tel.add_trace(go.Scatter(x=t2['Distance'], y=t2['Throttle'], name=f"{driver2} Throttle", line=dict(color='#00D2BE', width=1.8)), row=3, col=1)

                fig_tel.add_trace(go.Scatter(x=t1['Distance'], y=t1['Brake'].astype(int), name=f"{driver1} Brake", line=dict(color='#E10600', width=1.8)), row=4, col=1)
                fig_tel.add_trace(go.Scatter(x=t2['Distance'], y=t2['Brake'].astype(int), name=f"{driver2} Brake", line=dict(color='#00D2BE', width=1.8)), row=4, col=1)

                fig_tel.update_layout(
                    height=700, template="plotly_dark", hovermode="x unified",
                    font=dict(family="Titillium Web"), margin=dict(l=10, r=10, t=30, b=10)
                )
                st.plotly_chart(fig_tel, use_container_width=True)

                st.markdown(f"<h4 style='font-weight:900; text-transform:uppercase;'>CIRCUIT ACCELERATION & BRAKING PROFILE ({driver1})</h4>", unsafe_allow_html=True)
                fig_map = go.Figure(data=go.Scatter(
                    x=t1['X'], y=t1['Y'], mode='markers',
                    marker=dict(size=3, color=t1['Longitudinal_G'], colorscale='RdBu', cmin=-4, cmax=2, colorbar=dict(title="G")),
                    hovertext=t1['Speed'].apply(lambda s: f"{s:.1f} KM/H")
                ))
                fig_map.update_layout(
                    template="plotly_dark", 
                    xaxis=dict(visible=False), 
                    yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), 
                    height=450
                )
                st.plotly_chart(fig_map, use_container_width=True)

        except Exception as e:
            st.error(f"Telemetry extraction error: {e}")
    else:
        st.warning(f"No car telemetry stream available for {selected_year} {selected_event_name}. For full telemetry data, select a completed race round (such as 2024 British GP / Silverstone).")

# =========================================================
# TAB 4: 3D TRACK TOPOGRAPHY
# =========================================================
with tab_elevation:
    if available_drivers and session is not None:
        elev_driver = st.selectbox("SELECT DRIVER PATH", available_drivers, index=0, key="elev_driver")
        try:
            ref_lap = session.laps.pick_driver(elev_driver).pick_fastest()
            if ref_lap is not None:
                tel_3d = ref_lap.get_telemetry()
                x_m, y_m, z_m = tel_3d['X']/10, tel_3d['Y']/10, tel_3d['Z']/10
                c_e1, c_e2, c_e3 = st.columns(3)
                c_e1.metric("HIGHEST ELEVATION", f"{z_m.max():.1f} M")
                c_e2.metric("LOWEST ELEVATION", f"{z_m.min():.1f} M")
                c_e3.metric("VERTICAL DELTA", f"{z_m.max() - z_m.min():.1f} M")

                fig_3d = go.Figure(data=[go.Scatter3d(
                    x=x_m, y=y_m, z=z_m, mode='lines',
                    line=dict(color=tel_3d['Speed'], colorscale='Turbo', width=6, colorbar=dict(title="SPEED (KM/H)")),
                    hovertext=tel_3d.apply(lambda r: f"Speed: {r['Speed']:.1f} km/h | Elev: {r['Z']/10:.1f}m", axis=1)
                )])
                fig_3d.update_layout(template="plotly_dark", scene=dict(xaxis=dict(title="X"), yaxis=dict(title="Y"), zaxis=dict(title="ELEVATION"), aspectmode='data'), font=dict(family="Titillium Web"), height=600)
                st.plotly_chart(fig_3d, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not construct 3D coordinates: {e}")
    else:
        st.warning("No session data available for 3D Topography.")

# =========================================================
# TAB 5: SPEED TRAP RANKINGS
# =========================================================
with tab_speedtrap:
    if available_drivers and session is not None:
        speed_records = []
        for drv in available_drivers:
            drv_laps = session.laps.pick_driver(drv)
            if not drv_laps.empty:
                st_speed = drv_laps['SpeedST'].max() if 'SpeedST' in drv_laps else np.nan
                try:
                    peak_speed = drv_laps.pick_fastest().get_telemetry()['Speed'].max()
                except Exception:
                    peak_speed = np.nan
                speed_records.append({'DRIVER': drv, 'RADAR SPEED TRAP (KM/H)': st_speed, 'PEAK TELEMETRY SPEED (KM/H)': peak_speed})

        speed_df = pd.DataFrame(speed_records).sort_values(by='PEAK TELEMETRY SPEED (KM/H)', ascending=False).reset_index(drop=True)
        speed_df.index += 1
        c_s1, c_s2 = st.columns([3, 2])
        with c_s1:
            fig_speed = px.bar(
                speed_df.sort_values(by='PEAK TELEMETRY SPEED (KM/H)', ascending=True),
                x='PEAK TELEMETRY SPEED (KM/H)', y='DRIVER', orientation='h',
                text='PEAK TELEMETRY SPEED (KM/H)', color='PEAK TELEMETRY SPEED (KM/H)',
                color_continuous_scale='Magma', template="plotly_dark"
            )
            fig_speed.update_traces(texttemplate='%{text:.1f} KM/H', textposition='inside')
            fig_speed.update_layout(height=550, showlegend=False, font=dict(family="Titillium Web"))
            st.plotly_chart(fig_speed, use_container_width=True)
        with c_s2:
            st.dataframe(speed_df, use_container_width=True, height=500)
    else:
        st.warning("No session data available for Speed Trap rankings.")

# =========================================================
# TAB 6: TYRE STRATEGY GANTT
# =========================================================
with tab_strategy:
    if available_drivers and session is not None:
        try:
            stints = session.laps[['Driver', 'Stint', 'Compound', 'LapNumber']].groupby(['Driver', 'Stint', 'Compound']).agg(
                StartLap=('LapNumber', 'min'), EndLap=('LapNumber', 'max'), TotalLaps=('LapNumber', 'count')
            ).reset_index()

            if not stints.empty:
                fig_stints = go.Figure()
                for _, row in stints.iterrows():
                    comp = str(row['Compound']).upper()
                    c_color = COMPOUND_COLORS.get(comp, '#888888')
                    fig_stints.add_trace(go.Bar(
                        x=[row['TotalLaps']], y=[row['Driver']], base=row['StartLap'] - 1, orientation='h',
                        marker=dict(color=c_color, line=dict(color='#111', width=1)), name=comp,
                        hovertext=f"{row['Driver']} - Stint {row['Stint']}: {comp} ({row['TotalLaps']} laps)",
                        hoverinfo="text", showlegend=False
                    ))
                fig_stints.update_layout(template="plotly_dark", barmode='stack', xaxis=dict(title="LAP NUMBER"), yaxis=dict(title="DRIVER", autorange="reversed"), font=dict(family="Titillium Web"), height=550)
                st.plotly_chart(fig_stints, use_container_width=True)
        except Exception as e:
            st.warning(f"Tyre stint parsing notice: {e}")
    else:
        st.warning("No session data available for Tyre Strategy.")

# =========================================================
# TAB 7: RACE PACE ANALYSIS
# =========================================================
with tab_pace:
    if available_drivers and session is not None:
        try:
            valid_laps = session.laps.pick_quicklaps().copy()
            if not valid_laps.empty:
                valid_laps['LapTime_Seconds'] = valid_laps['LapTime'].dt.total_seconds()
                fig_pace = px.box(valid_laps, x='Driver', y='LapTime_Seconds', color='Driver', template="plotly_dark")
                fig_pace.update_layout(showlegend=False, height=500, font=dict(family="Titillium Web"))
                st.plotly_chart(fig_pace, use_container_width=True)
            else:
                st.info("No representative quick laps recorded for pace distribution.")
        except Exception as e:
            st.warning(f"Could not compute pace distribution: {e}")
    else:
        st.warning("No session data available for Race Pace analysis.")
        