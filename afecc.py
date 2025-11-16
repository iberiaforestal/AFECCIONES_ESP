import streamlit as st
import requests
import geopandas as gpd
import tempfile
import os
from shapely.geometry import Point

# ===================== CONFIGURACIÓN =====================
st.set_page_config(page_title="Afecciones CARM · JCCM", layout="centered")
st.image("https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/logos.jpg", width=280)
st.title("Informe básico de Afecciones al medio")
st.markdown("---")

BASE_URL_CLM = "https://raw.githubusercontent.com/iberiaforestal/CATASTRO_JCCM/master/CATASTRO/"
PROVINCIAS = ["ALBACETE", "CIUDAD REAL", "CUENCA", "GUADALAJARA", "TOLEDO"]

# ===================== FUNCIÓN CARGAR SHAPEFILE CLM =====================
@st.cache_data(ttl=3600)
def cargar_parcelario_clm(provincia: str, municipio: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        exts = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
        paths = {}
        base = f"{BASE_URL_CLM}{provincia}/{municipio.upper()}/PARCELA"
        for ext in exts:
            url = base + ext
            try:
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                path = os.path.join(tmpdir, "PARCELA" + ext)
                with open(path, "wb") as f:
                    f.write(r.content)
                paths[ext] = path
            except:
                return None
        try:
            gdf = gpd.read_file(paths[".shp"]).to_crs(epsg=25830)
            return gdf
        except:
            return None

# ===================== INICIO =====================
comunidad = st.selectbox("Comunidad Autónoma", ["Región de Murcia", "Castilla-La Mancha"])

provincia = None
if comunidad == "Castilla-La Mancha":
    provincia = st.selectbox("Provincia", PROVINCIAS)

modo = st.radio("Modo de selección", ["Por polígono y parcela", "Por coordenadas"], horizontal=True)

# ===================== VARIABLES QUE SE PASARÁN =====================
x = y = poligono = parcela = municipio_final = None
gdf_parcela = None

if modo == "Por polígono y parcela":
    # ------------------- MURCIA -------------------
    if comunidad == "Región de Murcia":
        municipios_murcia = [
            "Abanilla","Abarán","Águilas","Albudeite","Alcantarilla","Aledo","Alguazas","Alhama de Murcia",
            "Archena","Beniel","Blanca","Bullas","Calasparra","Campos del Río","Caravaca de la Cruz",
            "Cartagena","Cehegín","Ceutí","Cieza","Fortuna","Fuente Álamo de Murcia","Jumilla",
            "Las Torres de Cotillas","La Unión","Librilla","Lorca","Lorquí","Los Alcázares","Mazarrón",
            "Molina de Segura","Moratalla","Mula","Murcia","Ojós","Pliego","Puerto Lumbreras","Ricote",
            "Santomera","San Javier","San Pedro del Pinatar","Torre Pacheco","Totana","Ulea",
            "Villanueva del Río Segura","Yecla"
        ]
        municipio = st.selectbox("Municipio", sorted(municipios_murcia, key=str.lower))
        municipio_final = municipio.upper().replace(" ", "_").replace("Á", "A").replace("É", "E").replace("Í", "I")

    # ------------------- CASTILLA-LA MANCHA -------------------
    else:
        with st.spinner(f"Cargando municipios de {provincia}..."):
            api_url = f"https://api.github.com/repos/iberiaforestal/CATASTRO_JCCM/contents/CATASTRO/{provincia}"
            try:
                items = requests.get(api_url, timeout=15).json()
                municipios = sorted([item["name"] for item in items if item["type"] == "dir"], key=str.lower)
                municipio = st.selectbox("Municipio", municipios)
                municipio_final = municipio.upper()
            except:
                st.error("Error al cargar municipios. Revisa tu conexión.")
                st.stop()

    # Cargar parcelario y seleccionar polígono/parcela
    if municipio:
        with st.spinner("Cargando parcelario (puede tardar unos segundos)..."):
            if comunidad == "Región de Murcia":
                # En Murcia el archivo se llama como el municipio
                url_shp = f"https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/CATASTRO/{municipio_final}.shp"
                try:
                    gdf = gpd.read_file(url_shp).to_crs(epsg=25830)
                except:
                    st.error("Error cargando parcelario de Murcia")
                    st.stop()
            else:
                gdf = cargar_parcelario_clm(provincia, municipio_final)

        if gdf is not None and len(gdf) > 0:
            poligono = st.selectbox("Polígono", sorted(gdf["MASA"].unique()))
            parcela = st.selectbox("Parcela", sorted(gdf[gdf["MASA"] == poligono]["PARCELA"].unique()))
            
            seleccion = gdf[(gdf["MASA"] == poligono) & (gdf["PARCELA"] == parcela)]
            if not seleccion.empty:
                centroide = seleccion.geometry.centroid.iloc[0]
                x, y = round(centroide.x, 2), round(centroide.y, 2)
                gdf_parcela = seleccion
                st.success(f"Parcela seleccionada → X: {x:,} | Y: {y:,}".replace(",", "."))
        else:
            st.error("No se pudo cargar el parcelario")

# ===================== BÚSQUEDA POR COORDENADAS =====================
else:
    col1, col2 = st.columns(2)
    with col1:
        x = st.number_input("X (ETRS89 UTM 30N)", value=660000.0, format="%.2f")
    with col2:
        y = st.number_input("Y (ETRS89 UTM 30N)", value=4190000.0, format="%.2f")

    if st.button("Buscar parcela en estas coordenadas", type="primary"):
        punto = Point(x, y)
        encontrado = False

        if comunidad == "Región de Murcia":
            with st.spinner("Buscando en toda la Región de Murcia..."):
                for mun in ["ABANILLA","ABARAN","AGUILAS","ALBUDEITE","ALCANTARILLA","ALEDO","ALGUAZAS","ALHAMA_DE_MURCIA",
                            "ARCHENA","BENIEL","BLANCA","BULLAS","CALASPARRA","CAMPOS_DEL_RIO","CARAVACA_DE_LA_CRUZ",
                            "CARTAGENA","CEHEGIN","CEUTI","CIEZA","FORTUNA","FUENTE_ALAMO_DE_MURCIA","JUMILLA",
                            "LAS_TORRES_DE_COTILLAS","LA_UNION","LIBRILLA","LORCA","LORQUI","LOS_ALCAZARES","MAZARRON",
                            "MOLINA_DE_SEGURA","MORATALLA","MULA","MURCIA","OJOS","PLIEGO","PUERTO_LUMBRERAS","RICOTE",
                            "SANTOMERA","SAN_JAVIER","SAN_PEDRO_DEL_PINATAR","TORRE_PACHECO","TOTANA","ULEA",
                            "VILLANUEVA_DEL_RIO_SEGURA","YECLA"]:
                    try:
                        url = f"https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/CATASTRO/{mun}.shp"
                        gdf_temp = gpd.read_file(url).to_crs(epsg=25830)
                        if gdf_temp.contains(punto).any():
                            fila = gdf_temp[gdf_temp.contains(punto)].iloc[0]
                            municipio_final = mun
                            poligono = fila["MASA"]
                            parcela = fila["PARCELA"]
                            encontrado = True
                            break
                    except:
                        continue

        else:  # Castilla-La Mancha (solo en la provincia seleccionada)
            with st.spinner(f"Buscando en la provincia de {provincia}..."):
                api_url = f"https://api.github.com/repos/iberiaforestal/CATASTRO_JCCM/contents/CATASTRO/{provincia}"
                items = requests.get(api_url).json()
                for item in items:
                    if item["type"] == "dir":
                        mun = item["name"]
                        gdf_temp = cargar_parcelario_clm(provincia, mun)
                        if gdf_temp is not None and gdf_temp.contains(punto).any():
                            fila = gdf_temp[gdf_temp.contains(punto)].iloc[0]
                            municipio_final = mun
                            poligono = fila["MASA"]
                            parcela = fila["PARCELA"]
                            encontrado = True
                            break

        if encontrado:
            st.success(f"¡Parcela encontrada!\n**{municipio_final}** → Pol {poligono} → Parcela {parcela}")
        else:
            st.error("No se encontró ninguna parcela en esas coordenadas")

# ===================== BOTÓN FINAL QUE REDIRIGE (VERSIÓN DEFINITIVA) =====================
st.markdown("---")

# Solo mostramos el botón cuando realmente tenemos parcela localizada
if x and y and poligono and parcela:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if comunidad == "Región de Murcia":
            if st.button("GENERAR INFORME → Región de Murcia", 
                         type="primary", use_container_width=True, key="btn_murcia"):
                
                # Guardamos todo EN EL MOMENTO DEL CLIC (así siempre está actualizado)
                st.session_state.update({
                    "lanzador_ok": True,
                    "comunidad": comunidad,
                    "provincia": provincia,
                    "municipio": municipio_final,
                    "poligono": poligono,
                    "parcela": parcela,
                    "x": x,
                    "y": y
                })
                
                # Forzamos un rerun limpio y luego saltamos
                st.rerun()
                
        else:  # Castilla-La Mancha
            if st.button("GENERAR INFORME → Castilla-La Mancha", 
                         type="primary", use_container_width=True, key="btn_jccm"):
                
                st.session_state.update({
                    "lanzador_ok": True,
                    "comunidad": comunidad,
                    "provincia": provincia,
                    "municipio": municipio_final,
                    "poligono": poligono,
                    "parcela": parcela,
                    "x": x,
                    "y": y
                })
                
                st.rerun()

# === REDIRECCIÓN REAL: se ejecuta en el segundo rerun (cuando los datos ya están guardados) ===
if st.session_state.get("lanzador_ok") and st.session_state.get("comunidad"):
    if st.session_state.comunidad == "Región de Murcia":
        st.switch_page("pages/carm.py")
    else:
        st.switch_page("pages/jccm.py")
