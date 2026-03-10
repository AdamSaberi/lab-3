import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon
import json
from folium.plugins import MousePosition, Fullscreen

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem GIS Polygon DMS", layout="wide")

# Inisialisasi Password dalam Session State jika belum ada
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
    poly_coords = [[row['lon'], row['lat']] for i, row in df.iterrows()]
    poly_coords.append(poly_coords[0])
    features.append({
        "type": "Feature",
        "properties": {"name": "Lot Polygon"},
        "geometry": {"type": "Polygon", "coordinates": [poly_coords]}
    })
    for i, row in df.iterrows():
        features.append({
            "type": "Feature",
            "properties": {"STN": row['STN'], "E": row['E'], "N": row['N']},
            "geometry": {"type": "Point", "coordinates": [row['lon'], row['lat']]}
        })
    return json.dumps({"type": "FeatureCollection", "features": features}, indent=4)

# --- 3. HALAMAN LOGIN ---
def login_page():
    st.title("🔐 Login Sistem GIS")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Masuk"):
        if u == "admin" and p == st.session_state['password_db']:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("Username atau Password salah!")

# --- 4. HALAMAN TUKAR PASSWORD ---
def change_password_page():
    st.title("🔑 Tukar Password Admin")
    old_p = st.text_input("Password Semasa", type="password")
    new_p = st.text_input("Password Baru", type="password")
    confirm_p = st.text_input("Sahkan Password Baru", type="password")
    
    if st.button("Kemaskini Password"):
        if old_p != st.session_state['password_db']:
            st.error("Password semasa tidak tepat!")
        elif new_p != confirm_p:
            st.error("Sahkan password baru tidak sepadan!")
        elif len(new_p) < 4:
            st.warning("Password baru mestilah sekurang-kurangnya 4 aksara!")
        else:
            st.session_state['password_db'] = new_p
            st.success("✅ Password berjaya ditukar! Sila gunakan password baru untuk login akan datang.")

# --- 5. APLIKASI UTAMA (PETA) ---
def main_app():
    # Sidebar Navigasi
    st.sidebar.title("🚀 Menu Utama")
    choice = st.sidebar.selectbox("Navigasi", ["Peta GIS", "Tukar Password"])
    
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    if choice == "Tukar Password":
        change_password_page()
        return

    # Bahagian Peta GIS
    st.title("🗺️ Interactive Web GIS (DMS)")
    
    st.sidebar.divider()
    st.sidebar.header("⚙️ Tetapan Peta")
    map_mode = st.sidebar.radio("Jenis Peta:", ["Satelit (Google)", "Peta Jalan (OSM)"])
    
    st.sidebar.divider()
    show_stn = st.sidebar.checkbox("Paparkan Label Stesen", value=True)
    show_dim = st.sidebar.checkbox("Paparkan Bearing/Jarak", value=True)
    show_area = st.sidebar.checkbox("Paparkan Luas", value=True)
    
    st.sidebar.divider()
    uploaded_file = st.sidebar.file_uploader("Muat naik CSV (STN, E, N)", type='csv')

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        if all(col in df.columns for col in ['E', 'N']):
            transformer = Transformer.from_crs("EPSG:4390", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(df['E'].values, df['N'].values)
            df['lat'], df['lon'] = lat, lon
            
            geojson_str = convert_to_geojson(df)
            st.sidebar.download_button("📥 Download GeoJSON", data=geojson_str, file_name="data.geojson", mime="application/json")
            
            poly_geom = Polygon(list(zip(df['E'], df['N'])))
            center = [df['lat'].mean(), df['lon'].mean()]

            m_col1, m_col2 = st.columns([3, 1])
            with m_col2:
                st.metric("Luas (m²)", f"{poly_geom.area:.2f}")
                st.metric("Perimeter (m)", f"{poly_geom.length:.2f}")
                st.info("💡 **Tips:** Hover atau klik titik merah untuk koordinat.")

            with m_col1:
                m = folium.Map(location=center, zoom_start=19, max_zoom=22, tiles=None)
                if map_mode == "Satelit (Google)":
                    folium.TileLayer(
                        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                        attr='Google Satellite', name='Google Satellite', max_zoom=22, overlay=False
                    ).add_to(m)
                else:
                    folium.TileLayer('openstreetmap', name='OpenStreetMap', overlay=False).add_to(m)

                folium.Polygon(
                    locations=[[row['lat'], row['lon']] for i, row in df.iterrows()],
                    color="yellow", weight=3, fill=True, fill_opacity=0.2
                ).add_to(m)

                if show_area:
                    c_lon, c_lat = transformer.transform(poly_geom.centroid.x, poly_geom.centroid.y)
                    folium.Marker(location=[c_lat, c_lon], icon=folium.DivIcon(
                        html=f'<div style="font-size:10pt; color:yellow; font-weight:bold; width:150px; text-shadow:2px 2px #000; text-align:center;">LUAS: {poly_geom.area:.2f} m²</div>',
                        icon_anchor=(75, 5)
                    )).add_to(m)

                if show_dim:
                    dims = calculate_bearing_dist(df)
                    for d in dims:
                        folium.Marker(location=[d['mid_lat'], d['mid_lon']], icon=folium.DivIcon(
                            icon_size=(150,40), icon_anchor=(75,20),
                            html=f'''<div style="transform: rotate({d["rotation"]}deg); text-align:center;">
                                <div style="font-size:9pt; color:#00FFFF; font-weight:bold; text-shadow:1px 1px 2px #000; background:rgba(0,0,0,0.4); padding:2px; border-radius:3px; display:inline-block;">{d["bearing_dms"]}</div><br>
                                <div style="font-size:8pt; color:white; font-weight:bold; text-shadow:1px 1px 2px #000; background:rgba(0,0,0,0.4); padding:2px; border-radius:3px; display:inline-block;">{d["dist"]:.2f}m</div>
                            </div>'''
                        )).add_to(m)

                for i, row in df.iterrows():
                    info_box = f"""
                    <div style="font-family: sans-serif; size: 12px; width: 180px;">
                        <h4 style="margin:0; color:red;">Stesen {row['STN']}</h4>
                        <hr>
                        <b>E:</b> {row['E']:.3f}<br><b>N:</b> {row['N']:.3f}<br>
                        <b>Lat:</b> {row['lat']:.7f}<br><b>Lon:</b> {row['lon']:.7f}
                    </div>
                    """
                    folium.CircleMarker(
                        location=[row['lat'], row['lon']],
                        radius=10, color="white", weight=2, fill=True, fill_color="red", fill_opacity=0.9,
                        tooltip=folium.Tooltip(info_box, sticky=True),
                        popup=folium.Popup(info_box, max_width=300)
                    ).add_to(m)

                    if show_stn:
                        folium.Marker(
                            location=[row['lat'], row['lon']],
                            icon=folium.DivIcon(html=f'<div style="font-size:12pt; color:white; text-shadow:2px 2px #000; font-weight:bold; margin-left:15px; width:100px;">{row["STN"]}</div>')
                        ).add_to(m)

                Fullscreen().add_to(m)
                MousePosition(position='bottomleft', separator=' | ', prefix="WGS84: ").add_to(m)
                st_folium(m, width=1100, height=650, key="main_map")

            with st.expander("Lihat Jadual Data"):
                st.dataframe(df[['STN', 'E', 'N', 'lat', 'lon']], use_container_width=True)

# --- 6. JALANKAN PROGRAM ---
if __name__ == "__main__":
    if not st.session_state['logged_in']:
        login_page()
    else:
        main_app()

