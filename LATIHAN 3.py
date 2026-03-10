import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import folium_static
import numpy as np
from pyproj import Transformer
from folium.plugins import MousePosition, Fullscreen

# --- 1. PENGURUSAN LOGIN & DATABASE PENGGUNA ---
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

# --- 2. APLIKASI UTAMA ---
def main_app():
    # Nota: Layout set di sini
    # st.set_page_config dah dipanggil di awal script biasanya
    
    col_h1, col_h2 = st.columns([8, 2])
    with col_h1:
        st.title(f"🗺️ Interactive Web GIS")
        st.write(f"Selamat Datang, **{st.session_state['current_user']}**! 👋")
    with col_h2:
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

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
            bearing = (np.degrees(np.arctan2(de, dn)) + 360) % 360
            
            # Kira rotation selari garisan
            angle_deg = np.degrees(np.arctan2(dn, de))
            rotation = -angle_deg
            if rotation > 90: rotation -= 180
            elif rotation < -90: rotation += 180
            
            results.append({
                'dist': dist, 'bearing': bearing, 
                'mid_lat': (p1['lat'] + p2['lat']) / 2, 
                'mid_lon': (p1['lon'] + p2['lon']) / 2, 
                'rotation': rotation
            })
        return results

    # SIDEBAR
    st.sidebar.header("⚙️ Konfigurasi")
    font_size_stn = st.sidebar.slider("Saiz Label Stesen", 8, 20, 11)
    font_size_dim = st.sidebar.slider("Saiz Bearing/Jarak", 6, 16, 9)
    map_type = st.sidebar.selectbox("Jenis Peta", ["Satelit (Google)", "OpenStreetMap"])
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
                m = folium.Map(location=center, zoom_start=20, max_zoom=22)
                
                Fullscreen().add_to(m)
                MousePosition().add_to(m)

                if map_type == "Satelit (Google)":
                    folium.TileLayer(
                        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                        attr='Google', name='Google Satellite', max_zoom=22, max_native_zoom=19
                    ).add_to(m)

                # 1. Polygon
                poly_coords = [[row['lat'], row['lon']] for i, row in df.iterrows()]
                folium.Polygon(
                    locations=poly_coords, color="yellow", weight=3, fill=True, fill_opacity=0.1,
                    popup=f"Luas: {poly_geom.area:.2f}m²"
                ).add_to(m)

                # 2. Label Stesen & Titik
                for i, row in df.iterrows():
                    # Titik
                    folium.CircleMarker(
                        location=[row['lat'], row['lon']], radius=3, color="red", fill=True,
                        popup=f"STN: {row['STN']}\nE: {row['E']}\nN: {row['N']}"
                    ).add_to(m)
                    # Label
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        icon=folium.DivIcon(
                            icon_size=(0,0), icon_anchor=(0,0),
                            html=f'<div style="font-size:{font_size_stn}pt; color:white; text-shadow:2px 2px #000; font-weight:bold; width:50px; margin-left:5px; margin-top:-10px;">{row["STN"]}</div>'
                        )
                    ).add_to(m)

                # 3. Bearing & Jarak (MELEKAT)
                dims = calculate_bearing_dist(df)
                for d in dims:
                    # KUNCI: Gunakan icon_size dan icon_anchor supaya teks berputar pada paksi tengah
                    folium.Marker(
                        location=[d['mid_lat'], d['mid_lon']],
                        icon=folium.DivIcon(
                            icon_size=(100,20), 
                            icon_anchor=(50,10), # Center of the div
                            html=f'''
                            <div style="
                                transform: rotate({d["rotation"]}deg); 
                                width: 100px; 
                                height: 20px;
                                display: flex;
                                justify-content: center;
                                align-items: center;
                                pointer-events: none;">
                                <span style="
                                    font-size: {font_size_dim}pt; 
                                    color: #00FFFF; 
                                    font-weight: bold; 
                                    text-shadow: 1px 1px 2px #000; 
                                    background: rgba(0,0,0,0.3); 
                                    padding: 1px 3px; 
                                    border-radius: 3px;
                                    white-space: nowrap;">
                                    {d["bearing"]:.1f}° | {d["dist"]:.2f}m
                                </span>
                            </div>'''
                        )
                    ).add_to(m)

                folium_static(m, width=1000, height=600)

            st.dataframe(df[['STN', 'E', 'N', 'lat', 'lon']])

# --- 3. RUN ---
if __name__ == "__main__":
    if not st.session_state['logged_in']:
        login_page()
    else:
        main_app()