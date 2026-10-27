"""
CUBA, NEW MEXICO — DATA ATLAS
A Streamlit dashboard for exploring public data about Cuba, New Mexico.

Run:
    pip install streamlit pandas plotly requests
    streamlit run cuba_new_mexico_atlas.py

Data sources are fetched live where practical. If a source is unavailable, the app
shows a clear notice rather than fabricating current values.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page + visual design
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CUBA, NM | Data Atlas",
    page_icon="🌵",
    layout="wide",
    initial_sidebar_state="expanded",
)

BG = "#07111f"
PANEL = "#0d1b2b"
PANEL2 = "#11263a"
CYAN = "#53e0d0"
GOLD = "#ffca68"
TEXT = "#eef5fb"
MUTED = "#9db0c3"
PINK = "#ff6b8a"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Space Grotesk', sans-serif; }}
    .stApp {{
        background:
          radial-gradient(ellipse at 80% 0%, rgba(83,224,208,.10), transparent 32%),
          radial-gradient(ellipse at 5% 12%, rgba(255,202,104,.08), transparent 28%),
          {BG};
        color: {TEXT};
    }}
    [data-testid="stSidebar"] {{ background: #091725; border-right: 1px solid #1e3449; }}
    [data-testid="stMetric"] {{
        background: linear-gradient(145deg, {PANEL2}, {PANEL});
        border: 1px solid #244056; border-radius: 16px; padding: 17px 18px;
    }}
    [data-testid="stMetricLabel"] {{ color: {MUTED}; }}
    [data-testid="stMetricValue"] {{ color: {TEXT}; font-weight: 700; }}
    .hero {{
        padding: 28px 30px 24px; border: 1px solid #29495c; border-radius: 22px;
        background: linear-gradient(120deg, rgba(17,38,58,.97), rgba(7,17,31,.86));
        position: relative; overflow: hidden; margin-bottom: 18px;
    }}
    .hero:after {{
        content: "36.02° N  /  106.96° W"; position: absolute; right: 25px; bottom: 18px;
        color: #5d8298; font: 12px 'DM Mono', monospace; letter-spacing: 2px;
    }}
    .eyebrow {{ color: {CYAN}; text-transform: uppercase; letter-spacing: 3px;
        font: 11px 'DM Mono', monospace; }}
    .hero h1 {{ font-size: clamp(34px, 5vw, 62px); line-height: 1.0; margin: 10px 0 12px;
        letter-spacing: -2.5px; color: {TEXT}; }}
    .hero p {{ max-width: 700px; color: #c0d0de; font-size: 16px; margin-bottom: 0; }}
    .section-kicker {{ color: {CYAN}; font: 11px 'DM Mono', monospace;
        letter-spacing: 2px; text-transform: uppercase; margin: 6px 0 4px; }}
    .panel {{
        border: 1px solid #21394d; border-radius: 16px; padding: 18px 20px;
        background: rgba(13,27,43,.85); min-height: 100%;
    }}
    .panel h3 {{ margin-top: 0; color: {TEXT}; }}
    .muted {{ color: {MUTED}; }}
    .big-number {{ font-size: 29px; font-weight: 700; color: {GOLD}; }}
    .tag {{ display: inline-block; padding: 4px 9px; border-radius: 999px;
        background: #153b43; color: {CYAN}; font: 11px 'DM Mono', monospace; }}
    div[data-testid="stTabs"] button {{ color: #aabccc; }}
    div[data-testid="stTabs"] button[aria-selected="true"] {{ color: {CYAN}; }}
    .stButton button {{ border-radius: 10px; border: 1px solid #31566b; }}
    a {{ color: {CYAN} !important; }}
    hr {{ border-color: #21394d; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
CENSUS_BASE = "https://api.census.gov/data"
CENSUS_VARS = {
    "NAME": "Place name",
    "B01003_001E": "Population",
    "B19013_001E": "Median household income",
    "B17001_002E": "People below poverty line",
    "B01002_001E": "Median age",
    "B25001_001E": "Housing units",
    "B25002_003E": "Vacant housing units",
    "B15003_022E": "Bachelor's degree",
    "B23025_005E": "Unemployed people",
    "B02001_002E": "White alone",
    "B02001_003E": "Black or African American alone",
    "B02001_005E": "Asian alone",
    "B03003_003E": "Hispanic or Latino",
}
# Cuba is an incorporated place in Sandoval County, New Mexico.
CUBA_LAT, CUBA_LON = 36.0228, -106.9584
COUNTY_FIPS, STATE_FIPS, PLACE_FIPS = "043", "35", "16920"
HEADERS = {"User-Agent": "CubaNMDataAtlas/1.0 (public-interest dashboard)"}


def get_json(url: str, params: dict | None = None, timeout: int = 12) -> Any:
    response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3600, show_spinner=False)
def census_place(year: int = 2023) -> tuple[dict, str | None]:
    """Fetch Census ACS 5-year place-level indicators."""
    variables = list(CENSUS_VARS.keys())
    url = f"{CENSUS_BASE}/{year}/acs/acs5"
    params = {
        "get": ",".join(variables),
        "for": f"place:{PLACE_FIPS}",
        "in": f"state:{STATE_FIPS}",
    }
    try:
        rows = get_json(url, params)
        if len(rows) < 2:
            return {}, "The Census API returned no place-level rows."
        headers, values = rows[0], rows[1]
        return dict(zip(headers, values)), None
    except Exception as exc:
        return {}, f"Census API unavailable: {exc}"


@st.cache_data(ttl=1800, show_spinner=False)
def current_weather() -> tuple[dict, str | None]:
    """Fetch current conditions from Open-Meteo (no API key)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": CUBA_LAT,
        "longitude": CUBA_LON,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "is_day,precipitation,rain,showers,snowfall,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                 "precipitation_sum,sunrise,sunset",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "America/Denver",
        "forecast_days": 7,
    }
    try:
        return get_json(url, params), None
    except Exception as exc:
        return {}, f"Weather service unavailable: {exc}"


@st.cache_data(ttl=3600, show_spinner=False)
def air_quality() -> tuple[dict, str | None]:
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": CUBA_LAT, "longitude": CUBA_LON,
        "current": "us_aqi,pm10,pm2_5,ozone,nitrogen_dioxide",
        "hourly": "us_aqi,pm2_5,pm10",
        "timezone": "America/Denver",
        "forecast_days": 2,
    }
    try:
        return get_json(url, params), None
    except Exception as exc:
        return {}, f"Air-quality service unavailable: {exc}"


@st.cache_data(ttl=3600, show_spinner=False)
def usgs_earthquakes() -> tuple[pd.DataFrame, str | None]:
    """Recent earthquakes within roughly 150 miles of Cuba, NM."""
    end = datetime.utcnow()
    start = end - timedelta(days=30)
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%d"),
        "endtime": end.strftime("%Y-%m-%d"),
        "latitude": CUBA_LAT, "longitude": CUBA_LON,
        "maxradiuskm": 240, "minmagnitude": 1.0,
        "orderby": "time", "limit": 500,
    }
    try:
        payload = get_json(url, params)
        rows = []
        for item in payload.get("features", []):
            props = item.get("properties", {})
            coords = item.get("geometry", {}).get("coordinates", [None, None, None])
            rows.append({
                "Time (UTC)": pd.to_datetime(props.get("time"), unit="ms", utc=True),
                "Magnitude": props.get("mag"),
                "Place": props.get("place"),
                "Depth (km)": coords[2],
                "Longitude": coords[0],
                "Latitude": coords[1],
                "USGS link": props.get("url"),
            })
        return pd.DataFrame(rows), None
    except Exception as exc:
        return pd.DataFrame(), f"USGS earthquake feed unavailable: {exc}"


@st.cache_data(ttl=3600, show_spinner=False)
def ncei_climate_link() -> str:
    return "https://www.ncei.noaa.gov/"


def safe_number(data: dict, key: str, default=None):
    value = data.get(key, default)
    if value in (None, "", "null", -666666666, "-666666666", -999999999, "-999999999"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_int(value):
    return "—" if value is None else f"{value:,.0f}"


def fmt_money(value):
    return "—" if value is None else f"${value:,.0f}"


def fmt_decimal(value, digits=1, suffix=""):
    return "—" if value is None else f"{value:,.{digits}f}{suffix}"


def weather_label(code: int | None) -> str:
    if code is None:
        return "Conditions unavailable"
    labels = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
    }
    return labels.get(int(code), f"Weather code {code}")


def chart_layout(fig, height=330):
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color=TEXT,
        margin=dict(l=8, r=8, t=35, b=8),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor="#20374a", zerolinecolor="#20374a")
    fig.update_yaxes(gridcolor="#20374a", zerolinecolor="#20374a")
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🌵 CUBA / NM")
    st.caption("COMMUNITY DATA ATLAS · v1.0")
    pages = ["Overview", "People & Economy", "Weather & Climate", "Environment", "Local Guide", "Sources & Methods"]
    if st.session_state.get("jump_page") in pages:
        default_page_index = pages.index(st.session_state.pop("jump_page"))
    else:
        default_page_index = pages.index(st.session_state.get("page_choice", "Overview")) if st.session_state.get("page_choice", "Overview") in pages else 0
    page = st.radio(
        "EXPLORE", pages, index=default_page_index, label_visibility="collapsed", key="page_choice"
    )
    st.divider()
    st.markdown("**DATA CONTROLS**")
    census_year = st.selectbox("ACS dataset", [2023, 2022, 2021, 2019], index=0,
                               help="ACS 5-year estimates. Some variables may be suppressed or unavailable.")
    st.caption("Census updates annually. Weather, air quality, and earthquake data are live API feeds.")
    if st.button("↻ Refresh cached data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("Coordinates are approximate town-center coordinates. This dashboard is informational, not an official government product.")

# Load data
with st.spinner("Connecting to public data feeds…"):
    census, census_error = census_place(census_year)
    weather, weather_error = current_weather()
    air, air_error = air_quality()
    quakes, quake_error = usgs_earthquakes()

population = safe_number(census, "B01003_001E")
income = safe_number(census, "B19013_001E")
poverty_people = safe_number(census, "B17001_002E")
median_age = safe_number(census, "B01002_001E")
housing_units = safe_number(census, "B25001_001E")
vacant_units = safe_number(census, "B25002_003E")
unemployed = safe_number(census, "B23025_005E")
bachelors = safe_number(census, "B15003_022E")
hispanic = safe_number(census, "B03003_003E")
white = safe_number(census, "B02001_002E")
black = safe_number(census, "B02001_003E")
asian = safe_number(census, "B02001_005E")

current = weather.get("current", {})
daily = weather.get("daily", {})
air_current = air.get("current", {})
air_hourly = air.get("hourly", {})

# Header shared across pages
st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">SAN JUAN BASIN · NEW MEXICO · PUBLIC DATA</div>
      <h1>CUBA, NEW MEXICO<span style="color:#53e0d0">.</span></h1>
      <p>A live, data-driven field guide to the people, weather, environment, and local context
      of a small high-desert community in northwestern New Mexico.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------------------------
if page == "Overview":
    st.markdown('<div class="section-kicker">01 / THE BIG PICTURE</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Population", fmt_int(population), help=f"ACS {census_year} 5-year estimate")
    m2.metric("Median household income", fmt_money(income), help=f"ACS {census_year} 5-year estimate")
    m3.metric("Median age", fmt_decimal(median_age), help=f"ACS {census_year} 5-year estimate")
    temp = safe_number(current, "temperature_2m")
    m4.metric("Temperature now", fmt_decimal(temp, 1, " °F"), help="Open-Meteo current conditions")

    st.markdown("")
    left, right = st.columns([1.25, 1])
    with left:
        st.markdown('<div class="section-kicker">LIVE CONDITIONS</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        if current:
            c1, c2, c3 = st.columns(3)
            c1.metric("Feels like", fmt_decimal(safe_number(current, "apparent_temperature"), 1, " °F"))
            c2.metric("Humidity", fmt_decimal(safe_number(current, "relative_humidity_2m"), 0, "%"))
            c3.metric("Wind", fmt_decimal(safe_number(current, "wind_speed_10m"), 1, " mph"))
            code = current.get("weather_code")
            st.markdown(f"### {weather_label(code)}")
            st.caption(f"Updated: {current.get('time', 'time not provided')} · local time")
            if daily.get("time"):
                today_max = daily.get("temperature_2m_max", [None])[0]
                today_min = daily.get("temperature_2m_min", [None])[0]
                st.write(f"Today's forecast range: **{fmt_decimal(today_min, 0, '°F')} – {fmt_decimal(today_max, 0, '°F')}**")
        else:
            st.warning(weather_error or "No weather data returned.")
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-kicker">PLACE PROFILE</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="panel">
              <span class="tag">HIGH DESERT</span> <span class="tag">SANDOVAL COUNTY</span>
              <h3 style="margin-top:14px">A crossroads community</h3>
              <p class="muted">Cuba sits along US Highway 550 in northwestern New Mexico, in the transition
              between the Colorado Plateau and the higher terrain of the Jemez region.</p>
              <p><b>Coordinates</b><br><span class="muted">{CUBA_LAT:.4f}, {CUBA_LON:.4f}</span></p>
              <p><b>Regional context</b><br><span class="muted">Road connections, public lands, ranching,
              regional services, and outdoor recreation all shape the wider area.</span></p>
              <p><a href="https://www.census.gov/quickfacts/" target="_blank">Explore Census QuickFacts ↗</a></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-kicker">AT A GLANCE</div>', unsafe_allow_html=True)
    a, b, c, d = st.columns(4)
    poverty_rate = (poverty_people / population * 100) if poverty_people is not None and population else None
    vacancy_rate = (vacant_units / housing_units * 100) if vacant_units is not None and housing_units else None
    a.metric("People below poverty line", fmt_decimal(poverty_rate, 1, "%"))
    b.metric("Housing units", fmt_int(housing_units))
    c.metric("Housing vacancy", fmt_decimal(vacancy_rate, 1, "%"))
    aqi = safe_number(air_current, "us_aqi")
    d.metric("US AQI", fmt_int(aqi))
    st.caption("A dash means a value was unavailable or suppressed by the source; it does not mean zero.")

    st.markdown('<div class="section-kicker">EXPLORE THE ATLAS</div>', unsafe_allow_html=True)
    tiles = st.columns(4)
    tile_data = [
        ("PEOPLE & ECONOMY", "Population, income, poverty, housing, education.", "People & Economy"),
        ("WEATHER & CLIMATE", "Current conditions and the 7-day outlook.", "Weather & Climate"),
        ("ENVIRONMENT", "Air quality and nearby earthquake activity.", "Environment"),
        ("LOCAL GUIDE", "Useful map and public-information links.", "Local Guide"),
    ]
    for col, (title, desc, target) in zip(tiles, tile_data):
        with col:
            st.markdown(f'<div class="panel"><div class="eyebrow">{title}</div><p class="muted">{desc}</p></div>', unsafe_allow_html=True)
            if st.button(f"Open {target} →", key=f"open_{target}", use_container_width=True):
                st.session_state["jump_page"] = target
                st.rerun()

# ---------------------------------------------------------------------------
# PEOPLE & ECONOMY
# ---------------------------------------------------------------------------
elif page == "People & Economy":
    st.markdown('<div class="section-kicker">02 / PEOPLE & ECONOMY</div>', unsafe_allow_html=True)
    st.caption(f"American Community Survey {census_year} 5-year estimates · place-level data · not a real-time count")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Population", fmt_int(population))
    m2.metric("Median household income", fmt_money(income))
    m3.metric("Median age", fmt_decimal(median_age))
    m4.metric("Housing units", fmt_int(housing_units))

    poverty_rate = (poverty_people / population * 100) if poverty_people is not None and population else None
    vacancy_rate = (vacant_units / housing_units * 100) if vacant_units is not None and housing_units else None
    st.markdown("### Community indicators")
    indicators = pd.DataFrame([
        {"Indicator": "People below poverty line", "Value": poverty_people},
        {"Indicator": "Unemployed people", "Value": unemployed},
        {"Indicator": "Bachelor's degree count (age 25+ table)", "Value": bachelors},
        {"Indicator": "Hispanic or Latino", "Value": hispanic},
        {"Indicator": "White alone", "Value": white},
        {"Indicator": "Black or African American alone", "Value": black},
        {"Indicator": "Asian alone", "Value": asian},
    ])
    indicators["Value"] = pd.to_numeric(indicators["Value"], errors="coerce")
    indicators = indicators.dropna(subset=["Value"])
    if not indicators.empty:
        fig = px.bar(indicators, x="Value", y="Indicator", orientation="h", text_auto=".3s",
                     color="Value", color_continuous_scale=["#174052", CYAN, GOLD])
        fig.update_layout(coloraxis_showscale=False, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(chart_layout(fig, 360), use_container_width=True)
    else:
        st.info(census_error or "No indicator data was available for this selection.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Housing snapshot")
        housing_rows = []
        if housing_units is not None:
            housing_rows.append({"Measure": "Total housing units", "Estimate": housing_units})
        if vacant_units is not None:
            housing_rows.append({"Measure": "Vacant housing units", "Estimate": vacant_units})
        if housing_rows:
            hdf = pd.DataFrame(housing_rows)
            fig = px.bar(hdf, x="Measure", y="Estimate", text_auto=".3s", color="Measure",
                         color_discrete_sequence=[CYAN, GOLD])
            fig.update_layout(showlegend=False)
            st.plotly_chart(chart_layout(fig, 280), use_container_width=True)
        else:
            st.info("Housing data is unavailable.")
        st.metric("Estimated vacancy rate", fmt_decimal(vacancy_rate, 1, "%"))
    with c2:
        st.markdown("#### Household and employment context")
        st.metric("People below poverty line (count)", fmt_int(poverty_people))
        st.metric("Unemployed people (count)", fmt_int(unemployed))
        st.markdown(
            '<div class="panel"><p class="muted">These are survey estimates, not administrative counts. '
            'Small-area estimates can have large margins of error. “Unemployed people” is not the same '
            'as the unemployment rate; the rate requires the civilian labor force denominator.</p></div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Retrieved Census values")
    if census:
        view = []
        for key, label in CENSUS_VARS.items():
            val = census.get(key)
            view.append({"Variable": key, "Description": label, "Estimate": val})
        st.dataframe(pd.DataFrame(view), use_container_width=True, hide_index=True)
        st.download_button(
            "⬇ Download Census data as CSV",
            pd.DataFrame(view).to_csv(index=False).encode("utf-8"),
            file_name=f"cuba_nm_acs_{census_year}.csv",
            mime="text/csv",
        )
    else:
        st.warning(census_error or "Census data is unavailable.")

# ---------------------------------------------------------------------------
# WEATHER & CLIMATE
# ---------------------------------------------------------------------------
elif page == "Weather & Climate":
    st.markdown('<div class="section-kicker">03 / WEATHER & CLIMATE</div>', unsafe_allow_html=True)
    if weather_error:
        st.warning(weather_error)
    if current:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Temperature", fmt_decimal(safe_number(current, "temperature_2m"), 1, " °F"))
        m2.metric("Feels like", fmt_decimal(safe_number(current, "apparent_temperature"), 1, " °F"))
        m3.metric("Relative humidity", fmt_decimal(safe_number(current, "relative_humidity_2m"), 0, "%"))
        m4.metric("Wind speed", fmt_decimal(safe_number(current, "wind_speed_10m"), 1, " mph"))
        st.markdown(f"**Current conditions:** {weather_label(current.get('weather_code'))}  ·  **Local timestamp:** {current.get('time', '—')}")
    if daily.get("time"):
        forecast = pd.DataFrame({
            "Date": pd.to_datetime(daily["time"]),
            "High (°F)": daily.get("temperature_2m_max", []),
            "Low (°F)": daily.get("temperature_2m_min", []),
            "Precipitation chance (%)": daily.get("precipitation_probability_max", []),
            "Precipitation (in)": daily.get("precipitation_sum", []),
        })
        st.markdown("### Seven-day forecast")
        temp_long = forecast.melt(id_vars="Date", value_vars=["High (°F)", "Low (°F)"],
                                  var_name="Temperature", value_name="Degrees F")
        fig = px.line(temp_long, x="Date", y="Degrees F", color="Temperature", markers=True,
                      color_discrete_map={"High (°F)": GOLD, "Low (°F)": CYAN})
        fig.update_traces(line_width=3)
        st.plotly_chart(chart_layout(fig, 360), use_container_width=True)
        c1, c2 = st.columns([1, 1.2])
        with c1:
            fig = px.bar(forecast, x="Date", y="Precipitation chance (%)", text_auto=".0f",
                         color="Precipitation chance (%)", color_continuous_scale=["#153b43", CYAN, GOLD])
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(chart_layout(fig, 300), use_container_width=True)
        with c2:
            st.dataframe(forecast, use_container_width=True, hide_index=True)
            st.download_button("⬇ Download forecast CSV", forecast.to_csv(index=False).encode("utf-8"),
                               "cuba_nm_7day_forecast.csv", "text/csv")
    else:
        st.info("Forecast data is currently unavailable.")
    st.markdown("### Climate research")
    st.markdown(
        "- [NOAA National Centers for Environmental Information](https://www.ncei.noaa.gov/) — historical climate observations and normals.\n"
        "- [NOAA Climate Data Online](https://www.ncei.noaa.gov/cdo-web/) — station-based historical records (an API token may be required).\n"
        "- [Open-Meteo forecast API](https://open-meteo.com/) — forecast model data used in the live panels."
    )
    st.caption("A seven-day forecast is not a long-term climate normal. Historical trends should be evaluated over many years.")

# ---------------------------------------------------------------------------
# ENVIRONMENT
# ---------------------------------------------------------------------------
elif page == "Environment":
    st.markdown('<div class="section-kicker">04 / ENVIRONMENT & EARTH SYSTEMS</div>', unsafe_allow_html=True)
    st.markdown("### Air quality")
    if air_error:
        st.warning(air_error)
    if air_current:
        aqi = safe_number(air_current, "us_aqi")
        pm25 = safe_number(air_current, "pm2_5")
        pm10 = safe_number(air_current, "pm10")
        ozone = safe_number(air_current, "ozone")
        a, b, c, d = st.columns(4)
        a.metric("US AQI", fmt_int(aqi))
        b.metric("PM2.5", fmt_decimal(pm25, 1, " μg/m³"))
        c.metric("PM10", fmt_decimal(pm10, 1, " μg/m³"))
        d.metric("Ozone", fmt_decimal(ozone, 1, " μg/m³"))
        if aqi is not None:
            if aqi <= 50:
                st.success("AQI category: Good (0–50).")
            elif aqi <= 100:
                st.info("AQI category: Moderate (51–100).")
            elif aqi <= 150:
                st.warning("AQI category: Unhealthy for sensitive groups (101–150).")
            elif aqi <= 200:
                st.warning("AQI category: Unhealthy (151–200).")
            elif aqi <= 300:
                st.error("AQI category: Very unhealthy (201–300).")
            else:
                st.error("AQI category: Hazardous (301+).")
    if air_hourly.get("time") and air_hourly.get("us_aqi"):
        aqidf = pd.DataFrame({
            "Time": pd.to_datetime(air_hourly["time"]),
            "US AQI": air_hourly.get("us_aqi", []),
            "PM2.5": air_hourly.get("pm2_5", []),
            "PM10": air_hourly.get("pm10", []),
        })
        fig = px.line(aqidf, x="Time", y="US AQI", markers=True)
        fig.update_traces(line_color=CYAN, line_width=2)
        st.markdown("#### Hourly AQI")
        st.plotly_chart(chart_layout(fig, 300), use_container_width=True)
    st.caption("Air quality is a model-based estimate for the selected coordinates, not necessarily a nearby regulatory monitor. Values can differ from official monitoring stations.")

    st.divider()
    st.markdown("### Recent earthquakes")
    if quake_error:
        st.warning(quake_error)
    elif quakes.empty:
        st.info("No qualifying earthquake events were returned for the past 30 days within 240 km.")
    else:
        q1, q2, q3 = st.columns(3)
        q1.metric("Events returned", f"{len(quakes):,}")
        q2.metric("Largest magnitude", fmt_decimal(quakes["Magnitude"].max(), 1))
        q3.metric("Average magnitude", fmt_decimal(quakes["Magnitude"].mean(), 2))
        plot_df = quakes.dropna(subset=["Magnitude"]).copy()
        fig = px.scatter(plot_df, x="Time (UTC)", y="Magnitude", size="Magnitude",
                         hover_name="Place", hover_data=["Depth (km)"],
                         color="Magnitude", color_continuous_scale=["#53e0d0", "#ffca68", "#ff6b8a"])
        st.plotly_chart(chart_layout(fig, 340), use_container_width=True)
        st.dataframe(quakes.drop(columns=["Longitude", "Latitude"]), use_container_width=True, hide_index=True)
        st.download_button("⬇ Download earthquake data", quakes.to_csv(index=False).encode("utf-8"),
                           "cuba_nm_earthquakes_30days.csv", "text/csv")
    st.markdown("### Public environmental data")
    st.markdown(
        "- [USGS Earthquake Catalog](https://earthquake.usgs.gov/earthquakes/search/) — seismic events and event details.\n"
        "- [EPA AirData](https://www.epa.gov/outdoor-air-quality-data) — official monitored air-quality data.\n"
        "- [AirNow](https://www.airnow.gov/) — public air-quality reports and health guidance.\n"
        "- [USGS National Water Information System](https://waterdata.usgs.gov/nwis) — streamflow, groundwater, and water-quality records where stations exist.\n"
        "- [New Mexico Environment Department](https://www.env.nm.gov/) — state environmental programs and reports."
    )

# ---------------------------------------------------------------------------
# LOCAL GUIDE
# ---------------------------------------------------------------------------
elif page == "Local Guide":
    st.markdown('<div class="section-kicker">05 / LOCAL GUIDE</div>', unsafe_allow_html=True)
    st.markdown("A practical launchpad for finding services, transport, maps, public records, and regional information.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class="panel">
              <div class="eyebrow">MAPS & TRANSPORT</div>
              <h3>Find your way around</h3>
              <p><a href="https://www.google.com/maps/search/?api=1&query=Cuba%2C+New+Mexico" target="_blank">Open Cuba in Google Maps ↗</a></p>
              <p><a href="https://www.openstreetmap.org/search?query=Cuba%2C%20New%20Mexico" target="_blank">Open OpenStreetMap ↗</a></p>
              <p><a href="https://www.nmroads.com/" target="_blank">New Mexico road conditions ↗</a></p>
              <p><a href="https://www.dot.nm.gov/" target="_blank">New Mexico Department of Transportation ↗</a></p>
            </div>
            """, unsafe_allow_html=True)
    with c2:
        st.markdown(
            """
            <div class="panel">
              <div class="eyebrow">PUBLIC INFORMATION</div>
              <h3>Government & community</h3>
              <p><a href="https://www.sandovalcountynm.gov/" target="_blank">Sandoval County official website ↗</a></p>
              <p><a href="https://www.census.gov/quickfacts/" target="_blank">Census QuickFacts ↗</a></p>
              <p><a href="https://www.nmhealth.org/" target="_blank">New Mexico Department of Health ↗</a></p>
              <p><a href="https://www.nm.gov/" target="_blank">State of New Mexico ↗</a></p>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("### Search nearby services")
    category = st.selectbox("What are you looking for?", [
        "Restaurants and cafes", "Gas stations", "Groceries", "Healthcare and pharmacies",
        "Lodging", "Parks and outdoor recreation", "Schools", "Public services"
    ])
    search_query = {
        "Restaurants and cafes": "restaurants and cafes",
        "Gas stations": "gas stations",
        "Groceries": "grocery stores",
        "Healthcare and pharmacies": "healthcare clinics pharmacies",
        "Lodging": "hotels motels lodging",
        "Parks and outdoor recreation": "parks hiking outdoor recreation",
        "Schools": "schools",
        "Public services": "public services government offices",
    }[category]
    map_url = "https://www.google.com/maps/search/?api=1&query=" + requests.utils.quote(f"{search_query} Cuba New Mexico")
    st.link_button(f"Search {category.lower()} around Cuba ↗", map_url, use_container_width=True)
    st.caption("Links open third-party services. Check current hours, contact details, road conditions, and service availability directly with the provider.")
    st.markdown("### Regional geography")
    st.markdown(
        f'<div class="panel"><b>Approximate town center</b><p class="muted">{CUBA_LAT:.4f}, {CUBA_LON:.4f}</p>'
        f'<iframe title="Map centered on Cuba, New Mexico" width="100%" height="360" frameborder="0" '
        f'style="border:0;border-radius:12px" loading="lazy" '
        f'src="https://www.openstreetmap.org/export/embed.html?bbox=-107.08%2C35.96%2C-106.83%2C36.09&layer=mapnik&marker={CUBA_LAT}%2C{CUBA_LON}"></iframe>'
        f'<p><a href="https://www.openstreetmap.org/?mlat={CUBA_LAT}&mlon={CUBA_LON}#map=12/{CUBA_LAT}/{CUBA_LON}" target="_blank">View larger map ↗</a></p></div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# SOURCES & METHODS
# ---------------------------------------------------------------------------
elif page == "Sources & Methods":
    st.markdown('<div class="section-kicker">06 / SOURCES & METHODS</div>', unsafe_allow_html=True)
    st.markdown("### Data source registry")
    sources = pd.DataFrame([
        {"Dataset": "Population, income, age, housing, poverty, selected demographics",
         "Provider": "U.S. Census Bureau", "Refresh": "Annual ACS 5-year estimates",
         "Method": f"API endpoint /{census_year}/acs/acs5, place FIPS {PLACE_FIPS}, state FIPS {STATE_FIPS}",
         "Link": f"https://api.census.gov/data/{census_year}/acs/acs5.html"},
        {"Dataset": "Current conditions and 7-day forecast", "Provider": "Open-Meteo",
         "Refresh": "Forecast model updates", "Method": "Forecast API at approximate town-center coordinates",
         "Link": "https://open-meteo.com/"},
        {"Dataset": "Air quality estimates", "Provider": "Open-Meteo Air Quality",
         "Refresh": "Hourly/model updates", "Method": "US AQI, PM2.5, PM10, ozone at approximate coordinates",
         "Link": "https://open-meteo.com/en/docs/air-quality-api"},
        {"Dataset": "Recent earthquakes", "Provider": "U.S. Geological Survey",
         "Refresh": "Live event catalog", "Method": "Past 30 days, magnitude ≥1.0, radius 240 km",
         "Link": "https://earthquake.usgs.gov/fdsnws/event/1/"},
    ])
    st.dataframe(sources, use_container_width=True, hide_index=True, column_config={
        "Link": st.column_config.LinkColumn("Source link")
    })
    st.markdown("### Important interpretation notes")
    st.markdown(
        """
        - **No single source contains “all data.”** This app combines selected public datasets and links to official portals for deeper research.
        - **Survey estimates are not exact counts.** ACS figures represent 5-year estimates and may carry substantial margins of error in small communities.
        - **Missing is not zero.** A blank or dash can mean a variable was suppressed, unavailable, or not returned by the API.
        - **Weather is not climate.** Forecast conditions are short-range predictions. Long-term climate analysis requires historical observations and normals.
        - **Air-quality estimates are not a substitute for official alerts.** Check AirNow and local authorities when making health decisions.
        - **Coordinates are approximate.** Weather and air-quality values describe a model grid around the town center, not every neighborhood.
        - **Not an official government dashboard.** Confirm critical details with the relevant agency or service.
        """
    )
    st.markdown("### Raw payload diagnostics")
    with st.expander("Census API response"):
        st.json(census if census else {"error": census_error or "No data"})
    with st.expander("Weather API response"):
        st.json(weather if weather else {"error": weather_error or "No data"})
    with st.expander("Air-quality API response"):
        st.json(air if air else {"error": air_error or "No data"})
    with st.expander("Earthquake feed status"):
        st.write(quake_error or f"{len(quakes)} events returned.")
        if not quakes.empty:
            st.json(quakes.head(5).to_dict(orient="records"))

st.divider()
st.markdown(
    f'<div style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;color:{MUTED};font:11px DM Mono,monospace">'
    f'<span>CUBA, NM DATA ATLAS · BUILT WITH STREAMLIT</span>'
    f'<span>LAST VIEWED {datetime.now().strftime("%Y-%m-%d %H:%M")} LOCAL</span>'
    f'<span>PUBLIC DATA · VERIFY BEFORE USE</span></div>',
    unsafe_allow_html=True,
)
