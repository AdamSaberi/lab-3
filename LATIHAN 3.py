import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import folium_static
import numpy as np
from pyproj import Transformer
from folium.plugins import MousePosition, Fullscreen

# Set konfigurasi halaman
st.set_page_config(page_title="Sistem GIS Polygon DMS", layout="wide")

# --- 1. FUNGSI PEMBANTU ---
def decimal_to_dms(deg):
    d = int(deg)
    float_minutes = (deg - d) * 60
    m = int(float_minutes)
    float_seconds = (float_minutes - m) * 60
    s = round(float_seconds)
    if s >= 60: m += 1; s = 0
    if m >= 60: d += 1; m = 0
    return f"{d}°{m:02d}'{s:02d}\""

# --- 2. LOGIN (Ringkas) ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Login")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Masuk"):
        if user == "admin" and pwd == "1234":
            st.session_state['logged_in'] = True
            st.rerun()
        else: st.error("Salah!")
    st.stop()

# --- 3. APLIKASI UTAMA ---
st.title("🗺️ Web GIS - Suis Satelit On/Off")

# Sidebar
st.sidebar.header("⚙️ Tetapan Peta")
# INI ADALAH SUIS ON/OFF YANG ANDA MAHU
map_mode = st.sidebar.radio("Pilih Paparan Peta:", ["Satelit (Google)", "Peta Jalan (OSM)"])

show_stn = st.sidebar.checkbox("Label Stesen", value=True)
show_dim = st.sidebar.checkbox("Bearing/Jarak", value=True)
uploaded_file = st.sidebar.file_uploader("Upload CSV (STN, E, N)", type='csv')

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    transformer = Transformer.from_crs("EPSG:4390", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(df['E'].values, df['N'].values)
    df['lat'], df['lon'] = lat, lon
    
    center = [df['lat'].mean(), df['lon'].mean()]
    
    # LOGIK SUIS (ON/OFF)
    if map_mode == "Satelit (Google)":
        m = folium.Map(location=center, zoom_start=19, max_zoom=22, tiles=None)
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google', name='Google Satellite', max_zoom=22, overlay=False
        ).add_to(m)
    else:
        m = folium.Map(location=center, zoom_start=19, max_zoom=22) # Lalai OSM

    # Lukis Data
    poly_coords = [[row['lat'], row['lon']] for i, row in df.iterrows()]
    folium.Polygon(locations=poly_coords, color="yellow", weight=3, fill=True, fill_opacity=0.2).add_to(m)

    # Label-label
    for i, row in df.iterrows():
        if show_stn:
            folium.Marker(
                location=[row['lat'], row['lon']],
                icon=folium.DivIcon(html=f'<div style="font-size:10pt; color:white; font-weight:bold; text-shadow:2px 2px #000;">{row["STN"]}</div>')
            ).add_to(m)

    # Display Map
    Fullscreen().add_to(m)
    folium_static(m, width=1000, height=600)
