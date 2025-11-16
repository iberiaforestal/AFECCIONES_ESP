import streamlit as st
import geopandas as gpd
import requests
import tempfile
import os
from shapely.geometry import Point

# ===================== CONFIGURACIÓN =====================
BASE_URL_MURCIA = "https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/CATASTRO/"
BASE_URL_CLM = "https://raw.githubusercontent.com/iberiaforestal/CATASTRO_JCCM/master/CATASTRO/"

PROVINCIAS_CLM = ["ALBACETE", "CIUDAD REAL", "CUENCA", "GUADALAJARA", "TOLEDO"]

st.set_page_config(page_title="Afecciones CARM & JCCM", layout="centered")
st.image("https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/logos.jpg", width=300)
st.title("Informe básico de Afecciones al medio")
st.markdown("---")

comunidad = st.selectbox("Selecciona la Comunidad Autónoma", ["Región de Murcia", "Castilla-La Mancha"])

# ===================== CARGAR SHAPEFILE =====================
@st.cache_data(ttl=3600)
def cargar_shapefile(comunidad: str, municipio: str, provincia: str = None):
    with tempfile.TemporaryDirectory() as tmpdir:
        exts = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
        paths = {}

        if comunidad == "Región de Murcia":
            url_template = BASE_URL_MURCIA + f"{municipio.upper().replace(' ', '_')}{{}}"
            filename = municipio.upper().replace(" ", "_")
        else:
            url_template = BASE_URL_CLM + f"{provincia}/{municipio.upper()}/PARCELA{{}}"
            filename = "PARCELA"

        for ext in exts:
            url = url_template.format(ext)
            try:
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                path = os.path.join(tmpdir, filename + ext)
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

# ===================== BÚSQUEDA COORDENADAS =====================
def buscar_parcela(x, y, comunidad):
    punto = Point(x, y)
    if comunidad == "Región de Murcia":
        municipios = ["ABANILLA","ABARAN","AGUILAS","ALBUDEITE","ALCANTARILLA","ALEDO","ALGUAZAS","ALHAMA_DE_MURCIA",
                      "ARCHENA","BENIEL","BLANCA","BULLAS","CALASPARRA","CAMPOS_DEL_RIO","CARAVACA_DE_LA_CRUZ",
                      "CARTAGENA","CEHEGIN","CEUTI","CIEZA","FORTUNA","FUENTE_ALAMO_DE_MURCIA","JUMILLA",
                      "LAS_TORRES_DE_COTILLAS","LA_UNION","LIBRILLA","LORCA","LORQUI","LOS_ALCAZARES","MAZARRON",
                      "MOLINA_DE_SEGURA","MORATALLA","MULA","MURCIA","OJOS","PLIEGO","PUERTO_LUMBRERAS","RICOTE",
                      "SANTOMERA","SAN_JAVIER","SAN_PEDRO_DEL_PINATAR","TORRE_PACHECO","TOTANA","ULEA",
                      "VILLANUEVA_DEL_RIO_SEGURA","YECLA"]
        for mun in municipios:
            gdf = cargar_shapefile("Región de Murcia", mun)
            if gdf is not None and gdf.contains(punto).any():
                fila = gdf[gdf.contains(punto)].iloc[0]
                return mun, fila["MASA"], fila["PARCELA"]
    else:
        for prov in PROVINCIAS_CLM:
            api_url = f"https://api.github.com/repos/iberiaforestal/CATASTRO_JCCM/contents/CATASTRO/{prov}"
            try:
                items = requests.get(api_url).json()
                for item in items:
                    if item["type"] == "dir":
                        mun = item["name"]
                        gdf = cargar_shapefile("Castilla-La Mancha", mun, prov)
                        if gdf is not None and gdf.contains(punto).any():
                            fila = gdf[gdf.contains(punto)].iloc[0]
                            return f"{prov}/{mun}", fila["MASA"], fila["PARCELA"]
            except:
                continue
    return None, None, None

# ===================== INTERFAZ =====================
col1, col2 = st.columns(2)
with col1:
    x = st.number_input("X (ETRS89 UTM 30N)", value=660000.0, step=1.0, format="%.2f")
with col2:
    y = st.number_input("Y (ETRS89 UTM 30N)", value=4190000.0, step=1.0, format="%.2f")

if st.button("LOCALIZAR PARCELA Y CONTINUAR", type="primary", use_container_width=True):
    if x <= 0 or y <= 0:
        st.error("Introduce coordenadas válidas")
    else:
        with st.spinner("Buscando parcela en " + comunidad + "..."):
            resultado = buscar_parcela(x, y, comunidad)
        
        if resultado[0] is not None:
            municipio_o_ruta, poligono, parcela = resultado
            
            st.success(f"¡Parcela encontrada!\n\n**{comunidad}**\nPolígono {poligono} → Parcela {parcela}")
            
            # GUARDAMOS EN session_state PARA LA OTRA APP
            st.session_state.comunidad = comunidad
            st.session_state.x = x
            st.session_state.y = y
            st.session_state.poligono = poligono
            st.session_state.parcela = parcela
            st.session_state.municipio = municipio_o_ruta

            # REDIRECCIÓN AUTOMÁTICA
            if comunidad == "Región de Murcia":
                st.switch_page("pages/CARM_app.py")
            else:
                st.switch_page("pages/JCCM_app.py")
                
        else:
            st.error("No se encontró ninguna parcela en esas coordenadas")

st.markdown("---")
st.caption("App lanzador común → redirige automáticamente a la app específica de cada comunidad")
