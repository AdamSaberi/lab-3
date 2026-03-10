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

# --- 1. FUNGSI PEMBANTU (HELPER FUNCTIONS) ---

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

# --- 2. PENGURUSAN LOGIN ---
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

# --- 3. APLIKASI UTAMA ---
def main_app():
    col_h1, col_h2 = st.columns([8, 2])
    with col_h1:
        st.title(f"🗺️ Interactive Web GIS (DMS Format)")
        st.write(f"Selamat Datang, **{st.session_state['current_user']}**! 👋")
    with col_h2:
        if st.button("Logout", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # Transformer Koordinat (Kertau/Cassini EPSG:4390 ke WGS84 EPSG:4326)
    transformer = Transformer.from_crs("EPSG:4390", "EPSG:4326", always_xy=True)

    def transform_coords(df):
        lon, lat = transformer.transform(df['E'].values, df['N'].values)
        df['lat'], df['lon'] = lat, lon
        return df

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
                'dist': dist, 
                'bearing_dms': bearing_dms, 
                'mid_lat': (p1['lat'] + p2['lat']) / 2, 
                'mid_lon': (p1['lon'] + p2['lon']) / 2, 
                'rotation': rotation
            })
        return results

    # --- SIDEBAR SETTINGS ---
    st.sidebar.header("⚙️ Konfigurasi")
    
    st.sidebar.subheader("Kawalan Paparan")
    show_stn = st.sidebar.checkbox("Paparkan Label Stesen", value=True)
    show_dim = st.sidebar.checkbox("Paparkan Bearing/Jarak (Susun Menegak)", value=True)
    show_area_label = st.sidebar.checkbox("Paparkan Luas di Tengah", value=True)
    
    st.sidebar.divider()
    
    st.sidebar.subheader("Saiz Teks")
    font_size_stn = st.sidebar.slider("Saiz Label Stesen", 8, 20, 11)
    font_size_dim = st.sidebar.slider("Saiz Bearing/Jarak", 6, 16, 9)
    
    uploaded_file = st.sidebar.file_uploader("Pilih fail CSV (STN, E, N)", type='csv')

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        if all(col in df.columns for col in ['E', 'N']):
            df = transform_coords(df)
            poly_geom = Polygon(list(zip(df['E'], df['N'])))
            
            m_col1, m_col2 = st.columns([3, 1])
            
            with m_col2:
                st.markdown("### 📊 Ringkasan Lot")
                st.metric("Luas (m²)", f"{poly_geom.area:.3f}")
                st.metric("Perimeter (m)", f"{poly_geom.length:.3f}")

            with m_col1:
                center = [df['lat'].mean(), df['lon'].mean()]
                
                # Inisialisasi Peta dengan base layer OpenStreetMap
                m = folium.Map(location=center, zoom_start=19, max_zoom=22, control_scale=True)
                
                # Tambah Satelit (Google) sebagai TileLayer tambahan
                google_satellite = folium.TileLayer(
                    tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                    attr='Google',
                    name='Satelit (Google)',
                    max_zoom=22,
                    max_native_zoom=19,
                    show=True  # Set kepada True jika ingin satelit sebagai default
                ).add_to(m)

                # Tambah OpenStreetMap (Default)
                folium.TileLayer('openstreetmap', name='Peta Jalan (OSM)').add_to(m)
                
                Fullscreen().add_to(m)
                MousePosition().add_to(m)

                # Kumpulan Feature (untuk membolehkan label di-on/off juga jika perlu)
                fg_polygon = folium.FeatureGroup(name="Polygon & Luas").add_to(m)
                fg_labels = folium.FeatureGroup(name="Label Stesen & Dimensi").add_to(m)

                # 1. Melukis Polygon
                poly_coords = [[row['lat'], row['lon']] for i, row in df.iterrows()]
                folium.Polygon(
                    locations=poly_coords, color="yellow", weight=3, fill=True, fill_opacity=0.1,
                    popup=f"Luas: {poly_geom.area:.2f}m²"
                ).add_to(fg_polygon)

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
                    ).add_to(fg_polygon)

                # 3. Label Stesen
                for i, row in df.iterrows():
                    folium.CircleMarker(
                        location=[row['lat'], row['lon']], radius=3, color="red", fill=True,
                        popup=f"STN: {row['STN']}\nE: {row['E']}\nN: {row['N']}"
                    ).add_to(fg_labels)
                    
                    if show_stn:
                        folium.Marker(
                            location=[row['lat'], row['lon']],
                            icon=folium.DivIcon(
                                icon_size=(0,0), icon_anchor=(0,0),
                                html=f'''<div style="font-size:{font_size_stn}pt; color:white; text-shadow:2px 2px #000; 
                                        font-weight:bold; width:50px; margin-left:5px; margin-top:-10px;">{row["STN"]}</div>'''
                            )
                        ).add_to(fg_labels)

                # 4. Bearing & Jarak
                if show_dim:
                    dims = calculate_bearing_dist(df)
                    for d in dims:
                        folium.Marker(
                            location=[d['mid_lat'], d['mid_lon']],
                            icon=folium.DivIcon(
                                icon_size=(150,40), 
                                icon_anchor=(75,20),
                                html=f'''
                                <div style="transform: rotate({d["rotation"]}deg); width: 150px; display: flex; flex-direction: column; align-items: center; justify-content: center; pointer-events: none;">
                                    <span style="font-size: {font_size_dim}pt; color: #00FFFF; font-weight: bold; text-shadow: 1px 1px 2px #000; background: rgba(0,0,0,0.5); padding: 0px 4px; border-radius: 3px; line-height: 1.2; white-space: nowrap;">
                                        {d["bearing_dms"]}
                                    </span>
                                    <span style="font-size: {font_size_dim - 1}pt; color: #FFFFFF; font-weight: bold; text-shadow: 1px 1px 2px #000; background: rgba(0,0,0,0.5); padding: 0px 4px; border-radius: 3px; line-height: 1.2; margin-top: 2px; white-space: nowrap;">
                                        {d["dist"]:.2f}m
                                    </span>
                                </div>'''
                            )
                        ).add_to(fg_labels)

                # --- LAYER CONTROL (Butang On/Off Satelit) ---
                folium.LayerControl(position='topright', collapsed=False).add_to(m)

                folium_static(m, width=1000, height=600)

            with st.expander("Lihat Data Koordinat"):
                st.dataframe(df[['STN', 'E', 'N', 'lat', 'lon']], use_container_width=True)
        else:
            st.error("Format fail tidak betul. Pastikan ada kolum 'E' dan 'N'.")

# --- 4. RUN ---
if __name__ == "__main__":
    if not st.session_state['logged_in']:
        login_page()
    else:
        main_app()
