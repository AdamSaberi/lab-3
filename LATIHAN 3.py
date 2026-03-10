import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import folium_static
import numpy as np
from pyproj import Transformer
from folium.plugins import MousePosition, Fullscreen

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem GIS Polygon DMS", layout="wide")

# --- 2. FUNGSI PEMBANTU (HELPER FUNCTIONS) ---

def decimal_to_dms(deg):
    """Menukarkan perpuluhan darjah kepada format D° M' S\" """
    d = int(deg)
    float_minutes = (deg - d) * 60
    m = int(float_minutes)
    float_seconds = (float_minutes - m) * 60
    s = round(float_seconds)
    
    if s >= 60:
        m += 1
        s = 0
    if m >= 60:
        d += 1
        m = 0
        
    return f"{d}°{m:02d}'{s:02d}\""

def calculate_bearing_dist(df):
    """Mengira bearing (DMS) dan jarak antara stesen"""
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
            'dist': dist, 
            'bearing_dms': bearing_dms, 
            'mid_lat': (p1['lat'] + p2['lat']) / 2, 
            'mid_lon': (p1['lon'] + p2['lon']) / 2, 
            'rotation': rotation
        })
    return results

# --- 3. PENGURUSAN LOGIN ---
if 'users_db' not in st.session_state:
    st.session_state['users_db'] = {"admin": "1234", "user1": "password"}

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login_page():
    st.title("🔐 Sistem GIS Polygon - Login")
    tab1, tab2 = st.tabs(["Login", "Lupa Password"])
    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Masuk"):
            if username in st.session_state['users_db'] and st.session_state['users_db'][username] == password:
                st.session_state['logged_in'] = True
                st.session_state['current_user'] = username
                st.rerun()
            else:
                st.error("Username atau Password salah!")
    with tab2:
        st.subheader("Set Semula Password")
        user_reset = st.text_input("Username untuk reset")
        new_pass = st.text_input("Password Baru", type="password")
        if st.button("Simpan Password Baru"):
            if user_reset in st.session_state['users_db']:
                st.session_state['users_db'][user_reset] = new_pass
                st.success(f"Password untuk {user_reset} telah dikemaskini!")
            else:
                st.error("Username tidak wujud!")

# --- 4. APLIKASI UTAMA ---
def main_app():
    # Header & Logout
    col_h1, col_h2 = st.columns([8, 2])
    with col_h1:
        st.title(f"🗺️ Interactive Web GIS (DMS Format)")
        st.write(f"User Aktif: **{st.session_state['current_user']}**")
    with col_h2:
        if st.button("Logout", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- SIDEBAR KONFIGURASI ---
    st.sidebar.header("⚙️ Tetapan Peta")
    
    # SUIS ON/OFF SATELIT
    map_mode = st.sidebar.radio(
        "Jenis Paparan Peta:", 
        ["Satelit (Google)", "Peta Jalan (OSM)"]
    )
    
    st.sidebar.divider()
    
    st.sidebar.subheader("Kawalan Label")
    show_stn = st.sidebar.checkbox("Paparkan Label Stesen", value=True)
    show_dim = st.sidebar.checkbox("Paparkan Bearing/Jarak", value=True)
    show_area_label = st.sidebar.checkbox("Paparkan Luas", value=True)
    
    st.sidebar.subheader("Saiz Teks")
    font_size_stn = st.sidebar.slider("Saiz Label Stesen", 8, 20, 11)
    font_size_dim = st.sidebar.slider("Saiz Bearing/Jarak", 6, 16, 9)
    
    uploaded_file = st.sidebar.file_uploader("Muat Naik fail CSV (STN, E, N)", type='csv')

    # --- PEMPROSESAN DATA & PETA ---
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        
        if all(col in df.columns for col in ['E', 'N']):
            # Transformer Koordinat (EPSG:4390 ke WGS84)
            transformer = Transformer.from_crs("EPSG:4390", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(df['E'].values, df['N'].values)
            df['lat'], df['lon'] = lat, lon
            
            # Geometri Polygon & Info Lot
            poly_geom = Polygon(list(zip(df['E'], df['N'])))
            center = [df['lat'].mean(), df['lon'].mean()]

            m_col1, m_col2 = st.columns([3, 1])
            
            with m_col2:
                st.markdown("### 📊 Ringkasan Lot")
                st.metric("Luas (m²)", f"{poly_geom.area:.2f}")
                st.metric("Perimeter (m)", f"{poly_geom.length:.2f}")

            with m_col1:
                # Inisialisasi Peta
                if map_mode == "Satelit (Google)":
                    m = folium.Map(location=center, zoom_start=19, max_zoom=22, tiles=None)
                    folium.TileLayer(
                        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                        attr='Google',
                        name='Google Satellite',
                        max_zoom=22,
                        max_native_zoom=19,
                        overlay=False
                    ).add_to(m)
                else:
                    m = folium.Map(location=center, zoom_start=19, max_zoom=22)

                Fullscreen().add_to(m)
                MousePosition().add_to(m)

                # 1. Melukis Polygon
                poly_coords = [[row['lat'], row['lon']] for i, row in df.iterrows()]
                folium.Polygon(
                    locations=poly_coords, color="yellow", weight=3, fill=True, fill_opacity=0.15,
                    popup=f"Luas: {poly_geom.area:.2f} m²"
                ).add_to(m)

                # 2. Label Luas di Tengah
                if show_area_label:
                    c_lon, c_lat = transformer.transform(poly_geom.centroid.x, poly_geom.centroid.y)
                    folium.Marker(
                        location=[c_lat, c_lon],
                        icon=folium.DivIcon(
                            html=f'''<div style="font-size: 10pt; color: yellow; font-weight: bold; text-align: center; width: 150px; text-shadow: 2px 2px 4px #000;">
                                    LUAS: {poly_geom.area:.2f} m²</div>''',
                            icon_anchor=(75, 5)
                        )
                    ).add_to(m)

                # 3. Label Stesen & Titik Interaktif (Popup)
                for i, row in df.iterrows():
                    # HTML untuk Popup Info Stesen
                    popup_content = f"""
                    <div style="font-family: Arial; min-width: 150px;">
                        <h4 style="margin: 0; color: #d9534f;">Stesen: {row['STN']}</h4>
                        <hr style="margin: 5px 0;">
                        <b>Cassini E:</b> {row['E']:.3f}<br>
                        <b>Cassini N:</b> {row['N']:.3f}<br>
                        <b>WGS84 Lat:</b> {row['lat']:.6f}<br>
                        <b>WGS84 Lon:</b> {row['lon']:.6f}
                    </div>
                    """
                    
                    # Marker Titik (CircleMarker) - Klik untuk Popup
                    folium.CircleMarker(
                        location=[row['lat'], row['lon']], 
                        radius=6, 
                        color="red", 
                        fill=True,
                        fill_color="red",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_content, max_width=300)
                    ).add_to(m)
                    
                    # Label Nama Stesen (Teks putih)
                    if show_stn:
                        folium.Marker(
                            location=[row['lat'], row['lon']],
                            icon=folium.DivIcon(
                                html=f'''<div style="font-size:{font_size_stn}pt; color:white; text-shadow:2px 2px #000; font-weight:bold; width:60px;">{row["STN"]}</div>'''
                            )
                        ).add_to(m)

                # 4. Bearing & Jarak (Dimensi)
                if show_dim:
                    dims = calculate_bearing_dist(df)
                    for d in dims:
                        folium.Marker(
                            location=[d['mid_lat'], d['mid_lon']],
                            icon=folium.DivIcon(
                                icon_size=(150,40), icon_anchor=(75,20),
                                html=f'''
                                <div style="transform: rotate({d["rotation"]}deg); text-align:center; pointer-events:none;">
                                    <div style="font-size:{font_size_dim}pt; color:#00FFFF; font-weight:bold; text-shadow:1px 1px 2px #000; background:rgba(0,0,0,0.4); padding:0 2px; border-radius:3px; display:inline-block;">{d["bearing_dms"]}</div><br>
                                    <div style="font-size:{font_size_dim-1}pt; color:white; font-weight:bold; text-shadow:1px 1px 2px #000; background:rgba(0,0,0,0.4); padding:0 2px; border-radius:3px; display:inline-block;">{d["dist"]:.2f}m</div>
                                </div>'''
                            )
                        ).add_to(m)

                # Render Peta Akhir
                folium_static(m, width=1000, height=600)

            # Jadual Data
            with st.expander("Klik untuk lihat Jadual Data Koordinat"):
                st.dataframe(df[['STN', 'E', 'N', 'lat', 'lon']], use_container_width=True)
        else:
            st.error("Ralat: Pastikan fail CSV mempunyai kolum 'STN', 'E', dan 'N'.")

# --- 5. JALANKAN APLIKASI ---
if __name__ == "__main__":
    if not st.session_state['logged_in']:
        login_page()
    else:
        main_app()
