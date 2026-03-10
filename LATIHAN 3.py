import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon, Point, mapping
import json
from folium.plugins import MousePosition, Fullscreen

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem GIS Polygon DMS", layout="wide")

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

# FUNGSI BARU: CONVERT TO GEOJSON
def convert_to_geojson(df):
    features = []
    # 1. Tambah Polygon Feature
    poly_coords = [[row['lon'], row['lat']] for i, row in df.iterrows()]
    poly_coords.append(poly_coords[0]) # Tutup polygon
    
    poly_feature = {
        "type": "Feature",
        "properties": {"name": "Lot Polygon", "type": "Boundary"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [poly_coords]
        }
    }
    features.append(poly_feature)
    
    # 2. Tambah Point Features (Stesen)
    for i, row in df.iterrows():
        point_feature = {
            "type": "Feature",
            "properties": {
                "STN": row['STN'],
                "E_Cassini": row['E'],
                "N_Cassini": row['N'],
                "Lat_WGS84": row['lat'],
                "Lon_WGS84": row['lon']
            },
            "geometry": {
                "type": "Point",
                "coordinates": [row['lon'], row['lat']]
            }
        }
        features.append(point_feature)
        
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    return json.dumps(geojson_data, indent=4)

# --- 3. LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

def login_page():
    st.title("🔐 Login Sistem GIS")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Masuk"):
        if u == "admin" and p == "1234":
            st.session_state['logged_in'] = True
            st.rerun()
        else: st.error("Salah!")

# --- 4. APLIKASI UTAMA ---
def main_app():
    col_h1, col_h2 = st.columns([8, 2])
    with col_h1: st.title("🗺️ Interactive Web GIS (DMS)")
    with col_h2: 
        if st.button("Logout"): 
            st.session_state['logged_in'] = False
            st.rerun()

    # SIDEBAR
    st.sidebar.header("⚙️ Tetapan")
    map_mode = st.sidebar.radio("Pilih Paparan Peta:", ["Satelit (Google)", "Peta Jalan (OSM)"])
    
    st.sidebar.divider()
    show_stn = st.sidebar.checkbox("Label Stesen", value=True)
    show_dim = st.sidebar.checkbox("Bearing/Jarak", value=True)
    show_area = st.sidebar.checkbox("Paparkan Luas", value=True)
    
    st.sidebar.divider()
    uploaded_file = st.sidebar.file_uploader("Upload CSV (STN, E, N)", type='csv')

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        if all(col in df.columns for col in ['E', 'N']):
            # Transform Koordinat
            transformer = Transformer.from_crs("EPSG:4390", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(df['E'].values, df['N'].values)
            df['lat'], df['lon'] = lat, lon
            
            # GeoJSON Export Button di Sidebar
            geojson_str = convert_to_geojson(df)
            st.sidebar.download_button(
                label="📥 Download GeoJSON",
                data=geojson_str,
                file_name="data_gis.geojson",
                mime="application/json"
            )
            
            poly_geom = Polygon(list(zip(df['E'], df['N'])))
            center = [df['lat'].mean(), df['lon'].mean()]

            m_col1, m_col2 = st.columns([3, 1])
            with m_col2:
                st.metric("Luas (m²)", f"{poly_geom.area:.2f}")
                st.metric("Perimeter (m)", f"{poly_geom.length:.2f}")
                st.info("💡 Klik titik merah untuk koordinat stesen.")

            with m_col1:
                m = folium.Map(location=center, zoom_start=19, max_zoom=22, tiles=None)

                if map_mode == "Satelit (Google)":
                    folium.TileLayer(
                        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                        attr='Google Satellite', name='Satelit', max_zoom=22, overlay=False
                    ).add_to(m)
                else:
                    folium.TileLayer('openstreetmap', name='OSM', overlay=False).add_to(m)

                # 1. Lukis Polygon
                poly_coords = [[row['lat'], row['lon']] for i, row in df.iterrows()]
                folium.Polygon(locations=poly_coords, color="yellow", weight=3, fill=True, fill_opacity=0.2).add_to(m)

                # 2. Label Luas
                if show_area:
                    c_lon, c_lat = transformer.transform(poly_geom.centroid.x, poly_geom.centroid.y)
                    folium.Marker(location=[c_lat, c_lon], icon=folium.DivIcon(
                        html=f'<div style="font-size:10pt; color:yellow; font-weight:bold; text-align:center; width:150px; text-shadow:2px 2px #000;">LUAS: {poly_geom.area:.2f} m²</div>',
                        icon_anchor=(75, 5)
                    )).add_to(m)

                # 3. Titik Stesen & Popup
                for i, row in df.iterrows():
                    popup_html = f"""
                    <div style="font-family: Arial; font-size: 12px; width: 180px;">
                        <strong style="color:red;">STN: {row['STN']}</strong><br>
                        <hr style="margin:5px 0;">
                        <b>E (Cassini):</b> {row['E']:.3f}<br>
                        <b>N (Cassini):</b> {row['N']:.3f}<br>
                        <b>Lat (WGS84):</b> {row['lat']:.7f}<br>
                        <b>Lon (WGS84):</b> {row['lon']:.7f}
                    </div>
                    """
                    folium.CircleMarker(
                        location=[row['lat'], row['lon']], 
                        radius=7, color="red", fill=True, fill_opacity=0.9,
                        popup=folium.Popup(popup_html, max_width=250)
                    ).add_to(m)
                    
                    if show_stn:
                        folium.Marker(location=[row['lat'], row['lon']], icon=folium.DivIcon(
                            html=f'<div style="font-size:11pt; color:white; text-shadow:2px 2px #000; font-weight:bold; width:60px;">{row["STN"]}</div>'
                        )).add_to(m)

                # 4. Bearing & Jarak
                if show_dim:
                    dims = calculate_bearing_dist(df)
                    for d in dims:
                        folium.Marker(location=[d['mid_lat'], d['mid_lon']], icon=folium.DivIcon(
                            icon_size=(150,40), icon_anchor=(75,20),
                            html=f'''<div style="transform: rotate({d["rotation"]}deg); text-align:center; pointer-events:none;">
                                <div style="font-size:9pt; color:#00FFFF; font-weight:bold; text-shadow:1px 1px 2px #000; background:rgba(0,0,0,0.5); padding:0 4px; border-radius:3px; display:inline-block;">{d["bearing_dms"]}</div><br>
                                <div style="font-size:8pt; color:white; font-weight:bold; text-shadow:1px 1px 2px #000; background:rgba(0,0,0,0.5); padding:0 4px; border-radius:3px; display:inline-block;">{d["dist"]:.2f}m</div>
                            </div>'''
                        )).add_to(m)

                Fullscreen().add_to(m)
                st_folium(m, width=1000, height=600, key=f"peta_{map_mode}", returned_objects=[])

            with st.expander("Klik untuk lihat Jadual Data"):
                st.dataframe(df[['STN', 'E', 'N', 'lat', 'lon']], use_container_width=True)

# --- 5. JALANKAN ---
if __name__ == "__main__":
    if not st.session_state['logged_in']: login_page()
    else: main_app()
