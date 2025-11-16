import streamlit as st
import requests
import geopandas as gpd
import tempfile
import os
from shapely.geometry import Point
from pyproj import Transformer

# === REDIRECCIÓN INMEDIATA AL PRINCIPIO DEL SCRIPT ===
if st.session_state.get("_redirect") == "carm":
    st.switch_page("pages/carm.py")
elif st.session_state.get("_redirect") == "jccm":
    st.switch_page("pages/jccm.py")

# ===================== CONFIGURACIÓN =====================
st.set_page_config(page_title="Afecciones CARM · JCCM", layout="centered")
st.image("https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/logos.jpg", width=280)
st.title("Informe básico de Afecciones al medio")
st.markdown("---")

BASE_URL_CLM = "https://raw.githubusercontent.com/iberiaforestal/CATASTRO_JCCM/master/CATASTRO/"
PROVINCIAS = ["ALBACETE", "CIUDAD REAL", "CUENCA", "GUADALAJARA", "TOLEDO"]

# ===================== FUNCIÓN CARGAR SHAPEFILE CLM (MEJORADA CON LOGS) =====================
@st.cache_data(ttl=3600)
def cargar_parcelario_clm(provincia: str, municipio: str):
    base = f"{BASE_URL_CLM}{provincia}/{municipio.upper()}/PARCELA"
    st.info(f"Intentando cargar parcelario de {municipio.upper()} ({provincia})...")  # Log temporal

    with tempfile.TemporaryDirectory() as tmpdir:
        exts = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
        paths = {}
        for ext in exts:
            url = base + ext
            try:
                r = requests.get(url, timeout=60)  # Timeout más largo
                if r.status_code == 404:
                    st.error(f"Archivo no encontrado: {url} (404 - Verifica si el shapefile está subido)")
                    return None
                r.raise_for_status()
                path = os.path.join(tmpdir, "PARCELA" + ext)
                with open(path, "wb") as f:
                    f.write(r.content)
                paths[ext] = path
            except requests.exceptions.RequestException as e:
                st.error(f"Error descargando {url}: {str(e)}")
                return None
        try:
            gdf = gpd.read_file(paths[".shp"]).to_crs(epsg=25830)
            st.success(f"Parcelario cargado correctamente ({len(gdf)} parcelas)")
            return gdf
        except Exception as e:
            st.error(f"Error leyendo shapefile: {str(e)}")
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
                response = requests.get(api_url, timeout=15)
                response.raise_for_status()
                items = response.json()
                municipios = sorted([item["name"] for item in items if item["type"] == "dir"], key=str.lower)
                st.info(f"Encontrados {len(municipios)} municipios en {provincia}")
                if not municipios:
                    st.error(f"No se encontraron municipios en {provincia}. El directorio está vacío en GitHub. Verifica el repo y sube las carpetas de municipios.")
                    st.stop()
                municipio = st.selectbox("Municipio", municipios)
                municipio_final = municipio.upper()
            except Exception as e:
                st.error(f"Error al cargar municipios de {provincia}: {str(e)}")
                st.stop()

    # Cargar parcelario y seleccionar polígono/parcela
    if municipio:
        with st.spinner("Cargando parcelario (puede tardar unos segundos)..."):
            if comunidad == "Región de Murcia":
                # Código de Murcia sin cambios (funciona perfecto)
                url_shp = f"https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/CATASTRO/{municipio_final}.shp"
                try:
                    gdf = gpd.read_file(url_shp).to_crs(epsg=25830)
                except:
                    st.error("Error cargando parcelario de Murcia")
                    st.stop()
            else:
                gdf = cargar_parcelario_clm(provincia, municipio_final)  # Tu función mejorada con logs
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
                st.error("No se pudo seleccionar la parcela. Verifica los datos.")
        else:
            st.error("No se pudo cargar el parcelario. Verifica que PARCELA.shp esté subido en el repo GitHub para este municipio.")

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
        else:  # Castilla-La Mancha
            with st.spinner(f"Buscando en la provincia de {provincia}..."):
                api_url = f"https://api.github.com/repos/iberiaforestal/CATASTRO_JCCM/contents/CATASTRO/{provincia}"
                try:
                    items = requests.get(api_url, timeout=15).json()
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
                except Exception as e:
                    st.error(f"Error en búsqueda por coordenadas en {provincia}: {str(e)}")
        if encontrado:
            st.success(f"¡Parcela encontrada!\n**{municipio_final}** → Pol {poligono} → Parcela {parcela}")
            # ← ¡¡AQUÍ ESTABA EL FALLO!! → asignamos las variables para que el botón aparezca
            x = punto.x
            y = punto.y
            # Forzamos que el botón aparezca
            st.session_state.found_x = x
            st.session_state.found_y = y
            st.session_state.found_poligono = poligono
            st.session_state.found_parcela = parcela
            st.session_state.found_municipio = municipio_final
            st.rerun()  # Para que el botón aparezca inmediatamente 
        else:
            st.error("No se encontró ninguna parcela en esas coordenadas")

# ===================== BOTÓN FINAL QUE REDIRIGE =====================
st.markdown("---")

# Detectamos si tenemos datos (ya sea por selección manual o por coordenadas)
datos_listos = (x and y and poligono and parcela) or st.session_state.get("found_x")

if datos_listos:
    # Si vinieron por coordenadas, usamos esos datos
    if st.session_state.get("found_x"):
        x = st.session_state.found_x
        y = st.session_state.found_y
        poligono = st.session_state.found_poligono
        parcela = st.session_state.found_parcela
        municipio_final = st.session_state.found_municipio

    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        if comunidad == "Región de Murcia":
            if st.button("GENERAR INFORME → Región de Murcia", type="primary", use_container_width=True, key="go_murcia"):
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
                st.session_state._redirect = "carm"
                st.rerun()
        else:
            if st.button("GENERAR INFORME → Castilla-La Mancha", type="primary", use_container_width=True, key="go_jccm"):
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
                st.session_state._redirect = "jccm"
                st.rerun()

