# 🏎️ F1 Performance & Telemetry Dashboard

An interactive data analysis and visualization dashboard built with Python, FastF1, Streamlit, and Plotly. This tool enables head-to-head driver telemetry comparisons, race pace breakdown, and tyre strategy tracking using official Formula 1 timing data.

---

## 📌 Features

- **Lap Telemetry Comparison:** Synchronized multi-channel traces (Speed, Longitudinal Acceleration/G-force, Throttle %, Brake Input) mapped over lap distance.
- **Track Map G-Force Visualization:** 2D GPS spatial mapping colored by longitudinal load (braking zones vs. acceleration zones).
- **Tyre Strategy Timeline:** Gantt chart breaking down every driver's stint lengths and compound choices using official Pirelli color coding.
- **Race Pace & Degradation:** Boxplot distributions of clean lap times (excluding pit/safety car laps) and LOWESS smoothed degradation trends.
- **Zero Forecasting:** Pure descriptive analytics and exploratory data analysis (EDA).

---

## 🛠️ Tech Stack

- **Data Source:** [FastF1](https://github.com/theOehrly/Fast-F1) (official timing, telemetry, and lap data)
- **Data Manipulation:** `pandas`, `numpy`, `scipy`
- **Visualization:** `plotly` (interactive web graphics)
- **Dashboard Framework:** `streamlit`

---

## 📂 Project Structure

```text
f1-telemetry-dashboard/
├── app.py                 # Main dashboard application
├── requirements.txt       # Project dependencies
├── README.md              # Project documentation
└── f1_cache/              # Cached session data (auto-generated)
```

---

## 🚀 Getting Started

### 1. Clone or Set Up the Repository

```bash
mkdir f1-telemetry-dashboard
cd f1-telemetry-dashboard
```

### 2. Create and Activate a Virtual Environment

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

*(Or manually: `pip install fastf1 streamlit plotly pandas numpy scipy statsmodels`)*

### 4. Run the Dashboard

```bash
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`.

---

## 📊 Analytical Methodology

1. **Telemetry Derivatives:** Longitudinal acceleration ($a$) is computed numerically as the first derivative of velocity over time:
   $$a = \frac{\Delta v}{\Delta t}$$
   This is subsequently scaled to G-forces ($1\text{G} = 9.81\text{ m/s}^2$) to assess braking efficiency and traction application.
2. **Data Cleaning:** Non-representative laps (in-laps, out-laps, and laps under Safety Car / Virtual Safety Car conditions) are filtered using `pick_quicklaps()` before computing stint degradation curves.
3. **Local Caching:** FastF1 local caching is enabled by default to prevent repeated API calls and accelerate reload performance.

---

## 📄 License

This project is licensed under the MIT License.
