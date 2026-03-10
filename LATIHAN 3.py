import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon
import json
from folium.plugins import MousePosition, Fullscreen
import os

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem GIS PUO", layout="wide")

# Nama fail imej logo
LOGO_IMAGE = "politeknik-ungku-umar-seeklogo-removebg-preview.png.png"

# Inisialisasi Password & Status Login
if 'password_db' not in st.session_state:
    st.session_state['password_db'] = "1234"
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- 2. FUNGSI PEMBANTU ---
def decimal_to_dms(deg):
    d = int(deg)
    float_minutes = (deg - d) * 60
    m = int(float_minutes)
    float_seconds = (float_minutes - m) * 60
    s = round(float_seconds)
    if s >= 60: m += 1; s = 0
    if m >= 60: d += 1; m = 0
    return f"{d}°{m:02d}'{s:02d}\""

def calculate_bearing_dist(df):
    results = []
    for i in range(len(df)):
        p1, p2 = df.iloc[i], df.iloc[(i + 1) % len(df)]
        de, dn = p2['E'] - p1['E'], p2['N'] - p1['N']
        dist = np.sqrt(de**2 + dn**2)
        bearing_decimal = (np.degrees(np.arctan2(de, dn)) + 360) % 360
        bearing_dms = decimal_to_dms(bearing_decimal)
        angle_deg = np.degrees(np.arctan2(dn, de))
        rotation = -angle_deg
        if rotation > 90: rotation -= 180
        elif rotation < -90: rotation += 180
        results.append({
            'dist': dist, 'bearing_dms': bearing_dms, 
            'mid_lat': (p1['lat'] + p2['lat']) / 2, 
            'mid_lon': (p1['lon'] + p2['lon']) / 2, 'rotation': rotation
        })
    return results

def convert_to_geojson(df):
    features = []
    
    # 1. Tambah Polygon Utama (Kawasan)
    poly_coords = [[row['lon'], row['lat']] for i, row in df.iterrows()]
    poly_coords.append(poly_coords[0])
    features.append({
        "type": "Feature",
        "properties": {"Name": "Lot Polygon", "Type": "Area"},
        "geometry": {"type": "Polygon", "coordinates": [poly_coords]}
    })
    
    # 2. Tambah Titik Stesen (Points)
    for i, row in df.iterrows():
        features.append({
            "type": "Feature",
            "properties": {
                "STN": row['STN'], 
                "Eing": row['E'], 
                "Ning": row['N']
            },
            "geometry": {"type": "Point", "coordinates": [row['lon'], row['lat']]}
        })

    # 3. Tambah Garisan (LineString) Bersama Data Bearing & Jarak (Untuk QGIS)
    dims = calculate_bearing_dist(df)
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        d = dims[i]
        
        features.append({
            "type": "Feature",
            "properties": {
                "Dari": str(p1['STN']),
                "Ke": str(p2['STN']),
                "Bearing": d['bearing_dms'],
                "Jarak_m": round(d['dist'], 3),
                "Label": f"{d['bearing_dms']} | {round(d['dist'], 3)}m"
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[p1['lon'], p1['lat']], [p2['lon'], p2['lat']]]
            }
        })
        
    return json.dumps({"type": "FeatureCollection", "features": features}, indent=4)

# --- 3. HALAMAN LOGIN ---
def login_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists(LOGO_IMAGE):
            st.image(LOGO_IMAGE, use_container_width=True)
        
        st.markdown("<h2 style='text-align: center;'>LOG MASUK SISTEM GIS</h2>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            submit = st.form_submit_button("MASUK", use_container_width=True)
            
            if submit:
                if u == "admin" and p == st.session_state['password_db']:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Username atau Password salah!")

# --- 4. HALAMAN TUKAR PASSWORD ---
def change_password_page():
    st.subheader("🔑 Kemaskini Keselamatan")
    with st.container(border=True):
        old_p = st.text_input("Password Semasa", type="password")
        new_p = st.text_input("Password Baru", type="password")
        confirm_p = st.text_input("Sahkan Password Baru", type="password")
        
        if st.button("Simpan Password Baru"):
            if old_p != st.session_state['password_db']:
                st.error("Password semasa salah!")
            elif new_p != confirm_p:
                st.error("Sahkan password baru tidak sepadan!")
            elif len(new_p) < 4:
                st.warning("Password mestilah sekurang-kurangnya 4 aksara!")
            else:
                st.session_state['password_db'] = new_p
                st.success("✅ Berjaya ditukar!")

# --- 5. APLIKASI UTAMA ---
def main_app():
    # --- HEADER ---
    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_IMAGE):
            st.image(LOGO_IMAGE, width=180)
    
    with col_title:
        st.markdown("<h1 style='margin-bottom:0;'>Interactive Web GIS (DMS)</h1>", unsafe_allow_html=True)
        st.markdown("<p style='margin-top:0; color:grey;'>Jabatan Kejuruteraan Awam, Politeknik Ungku Omar</p>", unsafe_allow_html=True)
    
    st.divider()

    # Sidebar
    st.sidebar.title("🚀 Navigasi")
    choice = st.sidebar.selectbox("Menu", ["Peta GIS", "Tukar Password"])
    
    if st.sidebar.button("🚪 Log Keluar", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

    if choice == "Tukar Password":
        change_password_page()
        return

    st.sidebar.divider()
    map_mode = st.sidebar.radio("Jenis Peta:", ["Satelit (Google)", "Peta Jalan (OSM)"])
    show_stn = st.sidebar.checkbox("Label Stesen", value=True)
    show_dim = st.sidebar.checkbox("Bearing & Jarak", value=True)
    show_area = st.sidebar.checkbox("Paparan Luas", value=True)
    
    st.sidebar.divider()
    uploaded_file = st.sidebar.file_uploader("Muat naik fail CSV (STN, E, N)", type='csv')

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        if all(col in df.columns for col in ['E', 'N']):
            # Transform Cassini (EPSG:4390) ke WGS84
            transformer = Transformer.from_crs("EPSG:4390", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(df['E'].values, df['N'].values)
            df['lat'], df['lon'] = lat, lon
            
            # --- PENYEDIAAN DATA UNTUK MUAT TURUN ---
            geojson_str = convert_to_geojson(df)
            st.sidebar.download_button(
                label="📥 Download GeoJSON (Untuk QGIS)", 
                data=geojson_str, 
                file_name="GIS_PUO_Data.geojson", 
                mime="application/json",
                help="Fail ini mengandungi Polygon, Points, dan LineString berserta data Bearing/Jarak."
            )
            
            poly_geom = Polygon(list(zip(df['E'], df['N'])))
            center = [df['lat'].mean(), df['lon'].mean()]

            m_col1, m_col2 = st.columns([3, 1])
            with m_col2:
                st.metric("Luas (m²)", f"{poly_geom.area:.2f}")
                st.metric("Perimeter (m)", f"{poly_geom.length:.2f}")

            with m_col1:
                m = folium.Map(location=center, zoom_start=19, max_zoom=22, tiles=None)
                if map_mode == "Satelit (Google)":
                    folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Satellite', max_zoom=22).add_to(m)
                else:
                    folium.TileLayer('openstreetmap').add_to(m)

                # Lukis Polygon
                folium.Polygon(locations=[[row['lat'], row['lon']] for i, row in df.iterrows()], color="yellow", weight=3, fill=True, fill_opacity=0.2).add_to(m)

                # Bearing & Jarak (Visual di Peta)
                dims = calculate_bearing_dist(df)
                if show_dim:
                    for d in dims:
                        folium.Marker(location=[d['mid_lat'], d['mid_lon']], icon=folium.DivIcon(
                            html=f'<div style="transform: rotate({d["rotation"]}deg); text-align:center; font-size:8pt; color:#00FFFF; font-weight:bold; text-shadow:1px 1px #000;">{d["bearing_dms"]}<br>{d["dist"]:.2f}m</div>'
                        )).add_to(m)

                # Marker Stesen
                for i, row in df.iterrows():
                    folium.CircleMarker(location=[row['lat'], row['lon']], radius=6, color="red", fill=True).add_to(m)
                    if show_stn:
                        folium.Marker(location=[row['lat'], row['lon']], icon=folium.DivIcon(
                            html=f'<div style="font-size:11pt; color:white; text-shadow:1px 1px #000; font-weight:bold; margin-left:12px;">{row["STN"]}</div>'
                        )).add_to(m)

                Fullscreen().add_to(m)
                MousePosition().add_to(m)
                st_folium(m, width=1100, height=600, key="main_map")

# --- 6. RUN ---
if __name__ == "__main__":
    if not st.session_state['logged_in']:
        login_page()
    else:
        main_app()
