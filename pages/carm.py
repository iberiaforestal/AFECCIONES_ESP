import streamlit as st
import folium
from streamlit.components.v1 import html
from fpdf import FPDF
from pyproj import Transformer
import requests
import xml.etree.ElementTree as ET
import geopandas as gpd
import tempfile
import os
from shapely.geometry import Point
import uuid
from datetime import datetime
from docx import Document
from branca.element import Template, MacroElement
from io import BytesIO
from staticmap import StaticMap, CircleMarker
import textwrap
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import shutil
from PIL import Image

# Sesión segura con reintentos
session = requests.Session()
retry = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504, 429])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

# ==============================================================
# DETECCIÓN DEL LANZADOR – AÑADE ESTO AL PRINCIPIO
# ==============================================================
if "lanzador_ok" in st.session_state:
    # VIENE DEL LANZADOR → CARGAMOS LOS DATOS AUTOMÁTICAMENTE
    municipio_sel = st.session_state.municipio
    masa_sel = st.session_state.poligono
    parcela_sel = st.session_state.parcela
    x = st.session_state.x
    y = st.session_state.y

    # Intentamos cargar la geometría completa de la parcela (mejor para afecciones)
    base_url = "https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/CATASTRO/"
    archivo = municipio_sel.upper().replace(" ", "_").replace("Á","A").replace("É","E").replace("Í","I")

    with tempfile.TemporaryDirectory() as tmpdir:
        exts = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
        paths = {}
        ok = True
        for ext in exts:
            try:
                r = requests.get(f"{base_url}{archivo}{ext}", timeout=30)
                r.raise_for_status()
                p = os.path.join(tmpdir, f"{archivo}{ext}")
                with open(p, "wb") as f:
                    f.write(r.content)
                paths[ext] = p
            except:
                ok = False
                break
        if ok:
            gdf = gpd.read_file(paths[".shp"]).to_crs(epsg=25830)
            sel = gdf[(gdf["MASA"] == masa_sel) & (gdf["PARCELA"] == parcela_sel)]
            if not sel.empty:
                parcela = sel
                query_geom_lanzador = sel.geometry.iloc[0]
            else:
                parcela = None
                query_geom_lanzador = Point(x, y)
        else:
            parcela = None
            query_geom_lanzador = Point(x, y)

    st.info("Datos cargados desde el lanzador principal.")
else:
    # NO VIENE DEL LANZADOR → LO MANDAMOS AL PRINCIPIO
    st.warning("Acceso directo no permitido. Volviendo al selector principal...")
    st.switch_page("afecc.py")  # ← nombre de tu lanzador
    st.stop()

# Diccionario con los nombres de municipios y sus nombres base de archivo
shp_urls = {
    "ABANILLA": "ABANILLA",
    "ABARAN": "ABARAN",
    "AGUILAS": "AGUILAS",
    "ALBUDEITE": "ALBUDEITE",
    "ALCANTARILLA": "ALCANTARILLA",
    "ALEDO": "ALEDO",
    "ALGUAZAS": "ALGUAZAS",
    "ALHAMA DE MURCIA": "ALHAMA_DE_MURCIA",
    "ARCHENA": "ARCHENA",
    "BENIEL": "BENIEL",
    "BLANCA": "BLANCA",
    "BULLAS": "BULLAS",
    "CALASPARRA": "CALASPARRA",
    "CAMPOS DEL RIO": "CAMPOS_DEL_RIO",
    "CARAVACA DE LA CRUZ": "CARAVACA_DE_LA_CRUZ",
    "CARTAGENA": "CARTAGENA",
    "CEHEGIN": "CEHEGIN",
    "CEUTI": "CEUTI",
    "CIEZA": "CIEZA",
    "FORTUNA": "FORTUNA",
    "FUENTE ALAMO DE MURCIA": "FUENTE_ALAMO_DE_MURCIA",
    "JUMILLA": "JUMILLA",
    "LAS TORRES DE COTILLAS": "LAS_TORRES_DE_COTILLAS",
    "LA UNION": "LA_UNION",
    "LIBRILLA": "LIBRILLA",
    "LORCA": "LORCA",
    "LORQUI": "LORQUI",
    "LOS ALCAZARES": "LOS_ALCAZARES",
    "MAZARRON": "MAZARRON",
    "MOLINA DE SEGURA": "MOLINA_DE_SEGURA",
    "MORATALLA": "MORATALLA",
    "MULA": "MULA",
    "MURCIA": "MURCIA",
    "OJOS": "OJOS",
    "PLIEGO": "PLIEGO",
    "PUERTO LUMBRERAS": "PUERTO_LUMBRERAS",
    "RICOTE": "RICOTE",
    "SANTOMERA": "SANTOMERA",
    "SAN JAVIER": "SAN_JAVIER",
    "SAN PEDRO DEL PINATAR": "SAN_PEDRO_DEL_PINATAR",
    "TORRE PACHECO": "TORRE_PACHECO",
    "TOTANA": "TOTANA",
    "ULEA": "ULEA",
    "VILLANUEVA DEL RIO SEGURA": "VILLANUEVA_DEL_RIO_SEGURA",
    "YECLA": "YECLA",
}

# Función para cargar shapefiles desde GitHub
@st.cache_data
def cargar_shapefile_desde_github(base_name):
    base_url = "https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/CATASTRO/"
    exts = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        local_paths = {}
        for ext in exts:
            filename = base_name + ext
            url = base_url + filename
            try:
                response = requests.get(url, timeout=100)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                st.error(f"Error al descargar {url}: {str(e)}")
                return None
            
            local_path = os.path.join(tmpdir, filename)
            with open(local_path, "wb") as f:
                f.write(response.content)
            local_paths[ext] = local_path
        
        shp_path = local_paths[".shp"]
        try:
            gdf = gpd.read_file(shp_path)
            return gdf
        except Exception as e:
            st.error(f"Error al leer shapefile {shp_path}: {str(e)}")
            return None

# Función para encontrar municipio, polígono y parcela a partir de coordenadas
def encontrar_municipio_poligono_parcela(x, y):
    try:
        punto = Point(x, y)
        for municipio, archivo_base in shp_urls.items():
            gdf = cargar_shapefile_desde_github(archivo_base)
            if gdf is None:
                continue
            seleccion = gdf[gdf.contains(punto)]
            if not seleccion.empty:
                parcela_gdf = seleccion.iloc[[0]]
                masa = parcela_gdf["MASA"].iloc[0]
                parcela = parcela_gdf["PARCELA"].iloc[0]
                return municipio, masa, parcela, parcela_gdf
        return "N/A", "N/A", "N/A", None
    except Exception as e:
        st.error(f"Error al buscar parcela: {str(e)}")
        return "N/A", "N/A", "N/A", None

# Función para transformar coordenadas de ETRS89 a WGS84
def transformar_coordenadas(x, y):
    try:
        x, y = float(x), float(y)
        if not (500000 <= x <= 800000 and 4000000 <= y <= 4800000):
            st.error("Coordenadas fuera del rango esperado para ETRS89 UTM Zona 30")
            return None, None
        transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(x, y)
        return lon, lat
    except ValueError:
        st.error("Coordenadas inválidas. Asegúrate de ingresar valores numéricos.")
        return None, None

# === FUNCIÓN DESCARGA CON CACHÉ ===
@st.cache_data(show_spinner=False, ttl=604800)  # 7 días
def _descargar_geojson(url):
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        return BytesIO(response.content)
    except Exception as e:
        if not hasattr(st, "_wfs_warnings"):
            st._wfs_warnings = set()
        warning_key = url.split('/')[-1]
        if warning_key not in st._wfs_warnings:
            st.warning(f"Servicio no disponible: {warning_key}")
            st._wfs_warnings.add(warning_key)
        return None

# === FUNCIÓN PRINCIPAL (SIN CACHÉ EN GEOMETRÍA) ===
def consultar_wfs_seguro(geom, url, nombre_afeccion, campo_nombre=None, campos_mup=None):
    """
    Consulta WFS con:
    - Descarga cacheada (rápida después de la 1ª vez)
    - Geometría NO cacheada (evita UnhashableParamError)
    """
    data = _descargar_geojson(url)
    if data is None:
        return f"Indeterminado: {nombre_afeccion} (servicio no disponible)"

    try:
        gdf = gpd.read_file(data)
        seleccion = gdf[gdf.intersects(geom)]
        
        if seleccion.empty:
            return f"No afecta a {nombre_afeccion}"

        # --- MODO MUP: campos personalizados ---
        if campos_mup:
            info = []
            for _, row in seleccion.iterrows():
                valores = [str(row.get(c.split(':')[0], "Desconocido")) for c in campos_mup]
                etiquetas = [c.split(':')[1] if ':' in c else c.split(':')[0] for c in campos_mup]
                info.append("\n".join(f"{etiquetas[i]}: {valores[i]}" for i in range(len(campos_mup))))
            return f"Dentro de {nombre_afeccion}:\n" + "\n\n".join(info)

        # --- MODO NORMAL: solo nombres ---
        else:
            nombres = ', '.join(seleccion[campo_nombre].dropna().unique())
            return f"Dentro de {nombre_afeccion}: {nombres}"

    except Exception as e:
        return f"Indeterminado: {nombre_afeccion} (error de datos)"

# Función para crear el mapa con afecciones específicas
def crear_mapa(lon, lat, afecciones=[], parcela_gdf=None):
    if lon is None or lat is None:
        st.error("Coordenadas inválidas para generar el mapa.")
        return None, afecciones
    
    m = folium.Map(location=[lat, lon], zoom_start=16)
    folium.Marker([lat, lon], popup=f"Coordenadas transformadas: {lon}, {lat}").add_to(m)

    if parcela_gdf is not None and not parcela_gdf.empty:
        try:
            parcela_4326 = parcela_gdf.to_crs("EPSG:4326")
            folium.GeoJson(
                parcela_4326.to_json(),
                name="Parcela",
                style_function=lambda x: {'fillColor': 'transparent', 'color': 'blue', 'weight': 2, 'dashArray': '5, 5'}
            ).add_to(m)
        except Exception as e:
            st.error(f"Error al añadir la parcela al mapa: {str(e)}")

    wms_layers = [
        ("Red Natura 2000", "SIG_LUP_SITES_CARM:RN2000"),
        ("Montes", "PFO_ZOR_DMVP_CARM:MONTES"),
        ("Vias Pecuarias", "PFO_ZOR_DMVP_CARM:VP_CARM")
    ]
    for name, layer in wms_layers:
        try:
            folium.raster_layers.WmsTileLayer(
                url="https://mapas-gis-inter.carm.es/geoserver/ows?SERVICE=WMS&?",
                name=name,
                fmt="image/png",
                layers=layer,
                transparent=True,
                opacity=0.25,
                control=True
            ).add_to(m)
        except Exception as e:
            st.error(f"Error al cargar la capa WMS {name}: {str(e)}")

    folium.LayerControl().add_to(m)

    legend_html = """
    {% macro html(this, kwargs) %}
<div style="
    position: fixed;
    bottom: 20px;
    left: 20px;
    background-color: white;
    border: 1px solid grey;
    z-index: 9999;
    font-size: 10px;
    padding: 5px;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.2);
    line-height: 1.1em;
    width: auto;
    transform: scale(0.75);
    transform-origin: top left;
">
    <b>Leyenda</b><br>
    <div>
        <img src="https://mapas-gis-inter.carm.es/geoserver/ows?service=WMS&version=1.3.0&request=GetLegendGraphic&format=image%2Fpng&width=20&height=20&layer=SIG_LUP_SITES_CARM%3ARN2000" alt="Red Natura"><br>
        <img src="https://mapas-gis-inter.carm.es/geoserver/ows?service=WMS&version=1.3.0&request=GetLegendGraphic&format=image%2Fpng&width=20&height=20&layer=PFO_ZOR_DMVP_CARM%3AMONTES" alt="Montes"><br>
        <img src="https://mapas-gis-inter.carm.es/geoserver/ows?service=WMS&version=1.3.0&request=GetLegendGraphic&format=image%2Fpng&width=20&height=20&layer=PFO_ZOR_DMVP_CARM%3AVP_CARM" alt="Vias Pecuarias"><br>
    </div>
</div>
{% endmacro %}
"""

    legend = MacroElement()
    legend._template = Template(legend_html)
    m.get_root().add_child(legend)

    for afeccion in afecciones:
        folium.Marker([lat, lon], popup=afeccion).add_to(m)

    uid = uuid.uuid4().hex[:8]
    mapa_html = f"mapa_{uid}.html"
    m.save(mapa_html)

    return mapa_html, afecciones

# Función para generar la imagen estática del mapa usando py-staticmaps
def generar_imagen_estatica_mapa(x, y, zoom=16, size=(800, 600)):
    lon, lat = transformar_coordenadas(x, y)
    if lon is None or lat is None:
        return None
    
    try:
        m = StaticMap(size[0], size[1], url_template='http://a.tile.openstreetmap.org/{z}/{x}/{y}.png')
        marker = CircleMarker((lon, lat), 'red', 12)
        m.add_marker(marker)
        
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "mapa.png")
        image = m.render(zoom=zoom)
        image.save(output_path)
        return output_path
    except Exception as e:
        st.error(f"Error al generar la imagen estática del mapa: {str(e)}")
        return None

# Clase personalizada para el PDF con encabezado y pie de página
class CustomPDF(FPDF):
    def __init__(self, logo_path):
        super().__init__()
        self.logo_path = logo_path

    def header(self):
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                # --- ÁREA IMPRIMIBLE (SIN MÁRGENES) ---
                available_width = self.w - self.l_margin - self.r_margin  # ¡CORRECTO!

                max_logo_height = 25  # Altura fija

                from PIL import Image
                img = Image.open(self.logo_path)
                ratio = img.width / img.height

                # Escalar al ancho disponible
                target_width = available_width
                target_height = target_width / ratio

                if target_height > max_logo_height:
                    target_height = max_logo_height
                    target_width = target_height * ratio

                # --- CENTRAR DENTRO DEL ÁREA IMPRIMIBLE ---
                x = self.l_margin + (available_width - target_width) / 2
                y = 5

                self.image(self.logo_path, x=x, y=y, w=target_width, h=target_height)
                self.set_y(y + target_height + 3)

            except Exception as e:
                st.warning(f"Error al cargar logo: {e}")
                self.set_y(30)
        else:
            self.set_y(30)

    def footer(self):
        if self.page_no() > 0:
            self.set_y(-15)
            self.set_draw_color(0, 0, 255)
            self.set_line_width(0.5)
            page_width = self.w - 2 * self.l_margin
            self.line(self.l_margin, self.get_y(), self.l_margin + page_width, self.get_y())
            
            self.set_y(-15)
            self.set_font("Arial", "", 9)
            self.set_text_color(0, 0, 0)
            self.cell(0, 10, f"Página {self.page_no()}", align="R")

# Función para generar el PDF con los datos de la solicitud
def hay_espacio_suficiente(pdf, altura_necesaria, margen_inferior=20):
    """
    Verifica si hay suficiente espacio en la página actual.
    margen_inferior: espacio mínimo que debe quedar debajo
    """
    espacio_disponible = pdf.h - pdf.get_y() - margen_inferior
    return espacio_disponible >= altura_necesaria

def generar_pdf(datos, x, y, filename):
    logo_path = "logos.jpg"

    if not os.path.exists(logo_path):
        st.error("FALTA EL ARCHIVO: 'logos.jpg' en la raíz del proyecto.")
        st.markdown(
            "Descárgalo aquí: [logos.jpg](https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/logos.jpg)"
        )
        logo_path = None
    else:
        st.success("Logo local cargado correctamente")

    # === RECUPERAR query_geom ===
    query_geom = query_geom_lanzador  # Usamos la del lanzador

    # === OBTENER URLs DESDE SESSION_STATE ===
    urls = st.session_state.get('wfs_urls', {})
    vp_url = urls.get('vp')
    zepa_url = urls.get('zepa')
    lic_url = urls.get('lic')
    enp_url = urls.get('enp')
    esteparias_url = urls.get('esteparias')
    uso_suelo_url = urls.get('uso_suelo')
    tortuga_url = urls.get('tortuga')
    perdicera_url = urls.get('perdicera')
    nutria_url = urls.get('nutria')
    fartet_url = urls.get('fartet')
    malvasia_url = urls.get('malvasia')
    garbancillo_url = urls.get('garbancillo')
    flora_url = urls.get('flora')
    
    # Crear instancia de la clase personalizada
    pdf = CustomPDF(logo_path)
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()

    # TÍTULO GRANDE SOLO EN LA PRIMERA PÁGINA
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 12, "Informe preliminar de Afecciones Forestales", ln=True, align="C")
    pdf.ln(10)

    azul_rgb = (141, 179, 226)

    campos_orden = [
        ("Fecha informe", datos.get("fecha_informe", "").strip()),
        ("Nombre", datos.get("nombre", "").strip()),
        ("Apellidos", datos.get("apellidos", "").strip()),
        ("DNI", datos.get("dni", "").strip()),
        ("Dirección", datos.get("dirección", "").strip()),
        ("Teléfono", datos.get("teléfono", "").strip()),
        ("Email", datos.get("email", "").strip()),
    ]

    def seccion_titulo(texto):
        pdf.set_fill_color(*azul_rgb)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 10, texto, ln=True, fill=True)
        pdf.ln(2)

    def campo_orden(pdf, titulo, valor):
        pdf.set_font("Arial", "B", 12)
        pdf.cell(50, 7, f"{titulo}:", ln=0)
        pdf.set_font("Arial", "", 12)
        
        valor = valor.strip() if valor else "No especificado"
        wrapped_text = textwrap.wrap(valor, width=60)
        if not wrapped_text:
            wrapped_text = ["No especificado"]
        
        for line in wrapped_text:
            pdf.cell(0, 7, line, ln=1)

    seccion_titulo("1. Datos del solicitante")
    for titulo, valor in campos_orden:
        campo_orden(pdf, titulo, valor)

    objeto = datos.get("objeto de la solicitud", "").strip()
    pdf.ln(2)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "Objeto de la solicitud:", ln=True)
    pdf.set_font("Arial", "", 11)
    wrapped_objeto = textwrap.wrap(objeto if objeto else "No especificado", width=60)
    for line in wrapped_objeto:
        pdf.cell(0, 7, line, ln=1)
        
    seccion_titulo("2. Localización")
    for campo in ["municipio", "polígono", "parcela"]:
        valor = datos.get(campo, "").strip()
        campo_orden(pdf, campo.capitalize(), valor if valor else "No disponible")

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 10, f"Coordenadas ETRS89: X = {x}, Y = {y}", ln=True)

    imagen_mapa_path = generar_imagen_estatica_mapa(x, y)
    if imagen_mapa_path and os.path.exists(imagen_mapa_path):
        epw = pdf.w - 2 * pdf.l_margin
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, "Mapa de localización:", ln=True, align="C")
        image_width = epw * 0.5
        x_centered = pdf.l_margin + (epw - image_width) / 2  # Calcular posición x para centrar
        pdf.image(imagen_mapa_path, x=x_centered, w=image_width)
    else:
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 7, "No se pudo generar el mapa de localización.", ln=True)

    pdf.add_page()
    pdf.ln(10)
    seccion_titulo("3. Afecciones detectadas")

    afecciones_keys = ["Afección TM"]
    vp_key = "afección VP"
    mup_key = "afección MUP"
    zepa_key = "afección ZEPA"
    lic_key = "afección LIC"
    enp_key = "afección ENP"
    esteparias_key = "afección ESTEPARIAS"
    uso_suelo_key = "Afección PLANEAMIENTO"
    tortuga_key = "Afección PLAN RECUPERACION TORTUGA MORA"
    perdicera_key = "Afección PLAN RECUPERACION ÁGUILA PERDICERA"
    nutria_key = "Afección PLAN RECUPERACION NUTRIA"
    fartet_key = "Afección PLAN RECUPERACION FARTET"
    malvasia_key = "Afección PLAN RECUPERACION MALVASIA"
    garbancillo_key = "Afección PLAN RECUPERACION GARBANCILLO"
    flora_key = "Afección PLAN RECUPERACION FLORA"
        
    # === PROCESAR TODAS LAS CAPAS (VP, ZEPA, LIC, ENP) ===
    def procesar_capa(url, key, valor_inicial, campos, detectado_list):
        valor = datos.get(key, "").strip()
        if valor and not valor.startswith("No afecta") and not valor.startswith("Error"):
            try:
                data = _descargar_geojson(url)
                if data is None:
                    return "Error al consultar"
                gdf = gpd.read_file(data)
                seleccion = gdf[gdf.intersects(query_geom)]
                if not seleccion.empty:
                    for _, props in seleccion.iterrows():
                        fila = tuple(props.get(campo, "N/A") for campo in campos)
                        detectado_list.append(fila)
                    return ""
                return valor_inicial
            except Exception as e:
                st.error(f"Error al procesar {key}: {e}")
                return "Error al consultar"
        return valor_inicial if not detectado_list else ""

    # === VP ===
    vp_detectado = []
    vp_valor = procesar_capa(
        vp_url, "afección VP", "No afecta a ninguna Vía Pecuaria",
        ["vp_cod", "vp_nb", "vp_mun", "vp_sit_leg", "vp_anch_lg"],
        vp_detectado
    )

    # === ZEPA ===
    zepa_detectado = []
    zepa_valor = procesar_capa(
        zepa_url, "afección ZEPA", "No afecta a ninguna Zona de especial protección para las aves",
        ["site_code", "site_name"],
        zepa_detectado
    )

    # === LIC ===
    lic_detectado = []
    lic_valor = procesar_capa(
        lic_url, "afección LIC", "No afecta a ningún Lugar de Interés Comunitario",
        ["site_code", "site_name"],
        lic_detectado
    )

    # === ENP ===
    enp_detectado = []
    enp_valor = procesar_capa(
        enp_url, "afección ENP", "No afecta a ningún Espacio Natural Protegido",
        ["nombre", "figura"],
        enp_detectado
    )

    # === ESTEPARIAS ===
    esteparias_detectado = []
    esteparias_valor = procesar_capa(
        esteparias_url, "afección esteparias", "No afecta a zona de distribución de aves esteparias",
        ["cuad_10km", "especie", "nombre"],
        esteparias_detectado
    )

    # === USO DEL SUELO ===
    uso_suelo_detectado = []
    uso_suelo_valor = procesar_capa(
        uso_suelo_url, "afección uso_suelo", "No afecta a ningún uso del suelo protegido",
        ["Uso_Especifico", "Clasificacion"],
        uso_suelo_detectado
    )
    
    # === TORTUGA MORA ===
    tortuga_detectado = []
    tortuga_valor = procesar_capa(
        tortuga_url, "afección tortuga", "No afecta al Plan de Recuperación de la tortuga mora",
        ["cat_id", "cat_desc"],
        tortuga_detectado
    )

    # === AGUILA PERDICERA ===
    perdicera_detectado = []
    perdicera_valor = procesar_capa(
        perdicera_url, "afección perdicera", "No afecta al Plan de Recuperación del águila perdicera",
        ["zona", "nombre"],
        perdicera_detectado
    )

    # === NUTRIA ===
    nutria_detectado = []
    nutria_valor = procesar_capa(
        nutria_url, "afección nutria", "No afecta al Plan de Recuperación de la nutria",
        ["tipo_de_ar", "nombre"],
        nutria_detectado
    )    

    # === FARTET ===
    fartet_detectado = []
    fartet_valor = procesar_capa(
        fartet_url, "afección fartet", "No afecta al Plan de Recuperación del fartet",
        ["clasificac", "nombre"],
        fartet_detectado
    )

    # === MALVASIA ===
    malvasia_detectado = []
    malvasia_valor = procesar_capa(
        malvasia_url, "afección malvasia", "No afecta al Plan de Recuperación de la malvasía",
        ["clasificac", "nombre"],
        malvasia_detectado
    )

    # === GARBANCILLO ===
    garbancillo_detectado = []
    garbancillo_valor = procesar_capa(
        garbancillo_url, "afección garbancillo", "No afecta al Plan de Recuperación del garbancillo",
        ["tipo", "nombre"],
        garbancillo_detectado
    )

    # === FLORA ===
    flora_detectado = []
    flora_valor = procesar_capa(
        flora_url, "afección flora", "No afecta al Plan de Recuperación de la flora",
        ["tipo", "nombre"],
        flora_detectado
    )

    # === TM ===
    tm_valor = datos.get("Afección TM", "No afecta a ningún Término Municipal")

    # === MUP ===
    mup_valor = datos.get("afección MUP", "No afecta a ningún Monte de Utilidad Pública")

    # ... (continúa con el resto del código de afecciones y texto condicionado de tu documento original)

    # === TEXTO CONDICIONADO (de tu documento original) ===
    condicionado_texto = """
    1.- De acuerdo con lo establecido en el articulo 18 de la ley 43/2003 de 21 de noviembre de Montes, el propietario de montes privados debera comunicar a la administracion forestal competente de la comunidad autonoma la transmision de la propiedad de montes privados con una superficie superior a 25 hectareas.
    2.- Para la transmision de montes privados de superficie superior a 50 hectareas requerira el previo informe favorable de los titulares de dichos montes y, para los montes catalogados, el del organo forestal de la comunidad autonoma.
    3.- De acuerdo con lo establecido en el articulo 25.5 de la ley 43/2003 de 21 de noviembre de Montes, para posibilitar el ejercicio del derecho de adquisicion preferente a traves de la accion de tanteo, el transmitente debera notificar fehacientemente a la Administracion publica titular de ese derecho los datos relativos al precio y caracteristicas de la transmision proyectada, la cual dispondra de un plazo de tres meses, a partir de dicha notificacion, para ejercitar dicho derecho, mediante el abono o consignacion de su importe en las referidas condiciones.
    4.- En relacion al Dominio Publico Pecuario, salvaguardando lo que pudiera resultar de los futuros deslindes, en la parcela objeto este informe, cualquier construccion, plantacion, vallado, obras, instalaciones, etc., no deberian realizarse dentro del area delimitada como Dominio Publico Pecuario provisional para evitar invadir este.
    En todo caso, no podra interrumpirse el transito por el Dominio Publico Pecuario, dejando siempre el paso adecuado para el transito ganadero y otros usos legalmente establecidos en la Ley 3/1995, de 23 de marzo, de Vias Pecuarias.
    5.- El Planeamiento se regira por la Ley 13/2015, de 30 de marzo, de ordenacion territorial y urbanistica de la Region de Murcia, y por el PGOU del termino municipal. El Regimen del suelo no urbanizable se recoge en el articulo 5 de la citada Ley. Se indica que en casos de suelo no urbanizables.
    6.- En suelo no urbanizable se prestara especial atencion a la Disposicion adicional segunda de la Ley 3/2020, de 27 de julio, de recuperacion y proteccion del Mar Menor, solicitando para posibles cambios de uso lo establecido en el articulo 8 de la Ley 8/2014, de 21 de noviembre, de Medidas Tributarias, de Simplificacion Administrativa y en materia de Funcion Publica.
    7.- Los Planes de Gestion de la Red Natura 2000 aprobados, en la actualidad para la Comunidad Autonoma de la Region de Murcia son:
        - Decreto n. 13/2017, de 1 de marzo - Declaracion de las ZEC \"Minas de la Celia\" y \"Cueva de las Yeseras\" y aprobacion de su Plan de Gestion.
        - Decreto n. 259/2019, de 10 de octubre - Declaracion de ZEC y aprobacion del Plan de Gestion Integral de los Espacios Protegidos del Mar Menor y la Franja Litoral Mediterranea.
        - Decreto n. 231/2020, de 29 de diciembre - Aprobacion del Plan de Gestion Integral de los Espacios Protegidos Red Natura 2000 de la Sierra de Ricote y La Navela.
        - Decreto n. 47/2022, de 5 de mayo - Declaracion de ZEC y aprobacion del Plan de Gestion Integral de los Espacios Protegidos Red Natura 2000 del Alto Guadalentin; y aprobacion de los Planes de gestion de las ZEC del Cabezo de la Jara y Rambla de Nogalte y de la Sierra de Enmedio.
        - Decreto n. 252/2022, de 22 de diciembre - Declaracion de ZEC y aprobacion del Plan de Gestion Integral de los espacios protegidos de los relieves y cuencas centro-orientales de la Region de Murcia.
        - Decreto n. 28/2025, de 10 de abril - Declaracion de ZEC y aprobacion del Plan de Gestion Integral de los Espacios Protegidos del Altiplano de la Region de Murcia.
    8.- Los Planes de Ordenacion de los Recursos Naturales aprobados, en la actualidad para la Comunidad Autonoma de la Region de Murcia son:
        - Parque Regional Sierra de la Pila - Decreto n 43/2004, de 14 de mayo (aprobado definitivamente; BORM n 130, de 07/06/2004).
        - Parque Regional Sierra de El Carche - Decreto n 69/2002, de 22 de marzo (aprobado; BORM n 77, de 04/04/2002).
        - Parque Regional Salinas y Arenales de San Pedro del Pinatar - Decreto 44/1995, de 26 de mayo de 1995 (BORM n 151, de 01/07/1995).
        - Parque Regional Calblanque, Monte de las Cenizas y Pena del Aguila - Decreto 45/1995, de 26 de mayo de 1995 (BORM n 152, de 03/07/1995).
        - Parque Regional Sierra Espuna (incluido el Paisaje Protegido Barrancos de Gebas) - Decreto 13/1995, de 31 de marzo de 1995 (aprobacion del PORN; BORM n 85, de 11/04/1995).
        - Humedal del Ajauque y Rambla Salada - Orden (1998) (fase inicial).
        - Saladares del Guadalentin - Orden (29/12/1998) (fase inicial).
        - Sierra de Salinas - Orden (03/07/2002) (fase inicial).
        - Carrascoy y El Valle - Orden (18/05/2005) (fase inicial - ademas, existe en 2025 proyecto de Plan / Plan de Gestion/ZEC en informacion publica).
        - Sierra de la Muela, Cabo Tinoso y Roldan - Orden (15/03/2006) (fase inicial).
    9.- Los Planes de Recuperacion de Flora aprobados, en la actualidad para la Comunidad Autonoma de la Region de Murcia son:
        - Decreto 244/2014, de 19 de diciembre: aprueba los planes de recuperacion de las especies Cistus heterophyllus subsp. carthaginensis, Erica arborea, Juniperus turbinata, Narcissus nevadensis subsp. enemeritoi y Scrophularia arguta. Publicado en BORM n 297, de 27/12/2014.
        - Decreto 12/2007, de 22 de febrero: aprueba el plan de recuperacion de la especie Astragalus nitidiflorus (\"garbancillo de Tallante\"). Publicado en BORM n 51, de 3/03/2007.
    10.- Los Planes de Recuperacion de Fauna aprobados, en la actualidad para la Comunidad Autonoma de la Region de Murcia son:
        - Decreto n. 59/2016, de 22 de junio, de aprobacion de los planes de recuperacion del aguila perdicera, la nutria y el fartet.
        - Decreto n. 70/2016, de 12 de julio - Catalogacion de la malvasia cabeciblanca como especie en peligro de extincion y aprobacion de su Plan de Recuperacion en la Region de Murcia.
    """

    # --- TODAS LAS LÍNEAS EN UNA LISTA ---
    parrafos = [p.strip() for p in condicionado_texto.split('\n\n') if p.strip()]

    # --- DIVIDIR LÍNEAS EN 2 GRUPOS DE ALTURA SIMILAR ---
    col1_parrafos = []
    col2_parrafos = []
    altura_col1 = 0
    altura_col2 = 0

    ancho_columna = (pdf.w - 2 * pdf.l_margin - 5) / 2
    line_h = 6

    for parrafo in parrafos:
        # Estimar altura
        h_parrafo = 0
        for linea in parrafo.split('\n'):
            if linea.strip():
                line_width = pdf.get_string_width(linea)
                num_lineas = max(1, int(line_width / ancho_columna) + 1)
                h_parrafo += num_lineas * line_h
            else:
                h_parrafo += line_h

        if altura_col1 <= altura_col2:
            col1_parrafos.append(parrafo)
            altura_col1 += h_parrafo
        else:
            col2_parrafos.append(parrafo)
            altura_col2 += h_parrafo

    # --- GUARDAR POSICIÓN INICIAL ---
    y_inicio = pdf.get_y()
    pdf.set_x(pdf.l_margin)

    # --- ESCRIBIR COLUMNA 1 ---
    for parrafo in col1_parrafos:
        pdf.multi_cell(ancho_columna, line_h, parrafo, align="J")
       
    y_final_col1 = pdf.get_y()

    # --- ESCRIBIR COLUMNA 2 (misma altura que la 1) ---
    pdf.set_xy(pdf.l_margin + ancho_columna + 5, y_inicio)
    for parrafo in col2_parrafos:
        pdf.multi_cell(ancho_columna, line_h, parrafo, align="J")
        
    # Ajustar altura final
    pdf.set_y(max(y_final_col1, pdf.get_y()))   
        
    # === PIE ===
    pdf.ln(10)
    pdf.set_font("Arial", "", 9)
    pdf.multi_cell(0, line_h,
        "La normativa de referencia esta actualizada a fecha de uno de enero de dos mil veintiseis, y sera revisada trimestralmente.\n\n"
        "Para mas informacion:\n"
        "E-mail: info@iberiaforestal.es",
        align="J"
    )

    pdf.output(filename)
    return filename

# Interfaz de Streamlit (LIMPIA PARA LANZADOR)
st.image(
    "https://raw.githubusercontent.com/iberiaforestal/AFECCIONES_CARM/main/logos.jpg",
    width=250
)
st.title("Informe básico de Afecciones al medio – Región de Murcia")

st.success("Parcela cargada correctamente.")
st.write(f"Municipio: {municipio_sel}")
st.write(f"Polígono: {masa_sel}")
st.write(f"Parcela: {parcela_sel}")

with st.form("formulario"):
    nombre = st.text_input("Nombre")
    apellidos = st.text_input("Apellidos")
    dni = st.text_input("DNI")
    direccion = st.text_input("Dirección")
    telefono = st.text_input("Teléfono")
    email = st.text_input("Correo electrónico")
    objeto = st.text_area("Objeto de la solicitud", max_chars=255)
    submitted = st.form_submit_button("Generar informe")

if 'mapa_html' not in st.session_state:
    st.session_state['mapa_html'] = None
if 'pdf_file' not in st.session_state:
    st.session_state['pdf_file'] = None
if 'afecciones' not in st.session_state:
    st.session_state['afecciones'] = []

if submitted:
    # === 1. LIMPIAR ARCHIVOS DE BÚSQUEDAS ANTERIORES ===
    for key in ['mapa_html', 'pdf_file']:
        if key in st.session_state and st.session_state[key]:
            try:
                if os.path.exists(st.session_state[key]):
                    os.remove(st.session_state[key])
            except:
                pass
    st.session_state.pop('mapa_html', None)
    st.session_state.pop('pdf_file', None)

    # === 2. VALIDAR CAMPOS OBLIGATORIOS ===
    if not nombre or not apellidos or not dni or x == 0 or y == 0:
        st.warning("Por favor, completa todos los campos obligatorios y asegúrate de que las coordenadas son válidas.")
    else:
        # === 3. TRANSFORMAR COORDENADAS ===
        lon, lat = transformar_coordenadas(x, y)
        if lon is None or lat is None:
            st.error("No se pudo generar el informe debido a coordenadas inválidas.")
        else:
            # === 4. DEFINIR query_geom (UNA VEZ) ===
            query_geom = query_geom_lanzador

            # === 5. GUARDAR query_geom Y URLs EN SESSION_STATE ===
            st.session_state['query_geom'] = query_geom
            flora_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_ZOR_PLANIGEST_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_ZOR_PLANIGEST_CARM:planes_recuperacion_flora2014&outputFormat=application/json"
            garbancillo_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_ZOR_PLANIGEST_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_ZOR_PLANIGEST_CARM:plan_recuperacion_garbancillo&outputFormat=application/json"
            malvasia_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_ZOR_PLANIGEST_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_ZOR_PLANIGEST_CARM:plan_recuperacion_malvasia&outputFormat=application/json"
            fartet_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_ZOR_PLANIGEST_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_ZOR_PLANIGEST_CARM:plan_recuperacion_fartet&outputFormat=application/json"
            nutria_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_ZOR_PLANIGEST_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_ZOR_PLANIGEST_CARM:plan_recuperacion_nutria&outputFormat=application/json"
            perdicera_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_ZOR_PLANIGEST_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_ZOR_PLANIGEST_CARM:plan_recuperacion_perdicera&outputFormat=application/json"
            tortuga_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_DES_BIOTA_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_DES_BIOTA_CARM:tortuga_distribucion_2001&outputFormat=application/json"
            uso_suelo_url = "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo&outputFormat=application/json"
            esteparias_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_DES_BIOTA_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_DES_BIOTA_CARM:esteparias_ceea_2019_10x10&outputFormat=application/json"
            enp_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_LUP_SITES_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_LUP_SITES_CARM:ENP&outputFormat=application/json"
            zepa_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_LUP_SITES_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_LUP_SITES_CARM:ZEPA&outputFormat=application/json"
            lic_url = "https://mapas-gis-inter.carm.es/geoserver/SIG_LUP_SITES_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=SIG_LUP_SITES_CARM:LIC-ZEC&outputFormat=application/json"
            vp_url = "https://mapas-gis-inter.carm.es/geoserver/PFO_ZOR_DMVP_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=PFO_ZOR_DMVP_CARM:VP_CARM&outputFormat=application/json"
            tm_url = "https://mapas-gis-inter.carm.es/geoserver/MAP_UAD_DIVISION-ADMINISTRATIVA_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=MAP_UAD_DIVISION-ADMINISTRATIVA_CARM:recintos_municipales_inspire_carm_etrs89&outputFormat=application/json"
            mup_url = "https://mapas-gis-inter.carm.es/geoserver/PFO_ZOR_DMVP_CARM/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=PFO_ZOR_DMVP_CARM:MONTES&outputFormat=application/json"
            st.session_state['wfs_urls'] = {
                'enp': enp_url, 'zepa': zepa_url, 'lic': lic_url,
                'vp': vp_url, 'tm': tm_url, 'mup': mup_url, 
                'esteparias': esteparias_url,
                'uso_suelo': uso_suelo_url,
                'tortuga': tortuga_url,
                'perdicera': perdicera_url,
                'nutria': nutria_url,
                'fartet': fartet_url,
                'malvasia': malvasia_url,
                'garbancillo': garbancillo_url,
                'flora': flora_url
            }

            # === 6. CONSULTAR AFECCIONES ===
            afeccion_flora = consultar_wfs_seguro(query_geom, flora_url, "FLORA", campo_nombre="tipo")
            afeccion_garbancillo = consultar_wfs_seguro(query_geom, garbancillo_url, "GARBANCILLO", campo_nombre="tipo")
            afeccion_malvasia = consultar_wfs_seguro(query_geom, malvasia_url, "MALVASIA", campo_nombre="clasificac")
            afeccion_fartet = consultar_wfs_seguro(query_geom, fartet_url, "FARTET", campo_nombre="clasificac")
            afeccion_nutria = consultar_wfs_seguro(query_geom, nutria_url, "NUTRIA", campo_nombre="tipo_de_ar")
            afeccion_perdicera = consultar_wfs_seguro(query_geom, perdicera_url, "ÁGUILA PERDICERA", campo_nombre="zona")
            afeccion_tortuga = consultar_wfs_seguro(query_geom, tortuga_url, "TORTUGA MORA", campo_nombre="cat_desc")
            afeccion_uso_suelo = consultar_wfs_seguro(query_geom, uso_suelo_url, "PLANEAMIENTO", campo_nombre="Clasificacion")
            afeccion_esteparias = consultar_wfs_seguro(query_geom, esteparias_url, "ESTEPARIAS", campo_nombre="nombre")
            afeccion_enp = consultar_wfs_seguro(query_geom, enp_url, "ENP", campo_nombre="nombre")
            afeccion_zepa = consultar_wfs_seguro(query_geom, zepa_url, "ZEPA", campo_nombre="site_name")
            afeccion_lic = consultar_wfs_seguro(query_geom, lic_url, "LIC", campo_nombre="site_name")
            afeccion_vp = consultar_wfs_seguro(query_geom, vp_url, "VP", campo_nombre="vp_nb")
            afeccion_tm = consultar_wfs_seguro(query_geom, tm_url, "TM", campo_nombre="nameunit")
            afeccion_mup = consultar_wfs_seguro(
                query_geom, mup_url, "MUP",
                campos_mup=["id_monte:ID", "nombremont:Nombre", "municipio:Municipio", "propiedad:Propiedad"]
            )
            afecciones = [afeccion_flora, afeccion_garbancillo, afeccion_malvasia, afeccion_fartet, afeccion_nutria, afeccion_perdicera, afeccion_tortuga, afeccion_uso_suelo, afeccion_esteparias, afeccion_enp, afeccion_zepa, afeccion_lic, afeccion_vp, afeccion_tm, afeccion_mup]

            # === 7. CREAR DICCIONARIO `datos` ===
            datos = {
                "fecha_informe": datetime.today().strftime('%d/%m/%Y'),
                "nombre": nombre, "apellidos": apellidos, "dni": dni,
                "dirección": direccion, "teléfono": telefono, "email": email,
                "objeto de la solicitud": objeto,
                "afección MUP": afeccion_mup, "afección VP": afeccion_vp,
                "afección ENP": afeccion_enp, "afección ZEPA": afeccion_zepa,
                "afección LIC": afeccion_lic, "Afección TM": afeccion_tm,
                "afección esteparias": afeccion_esteparias,
                "afección uso_suelo": afeccion_uso_suelo,
                "afección tortuga": afeccion_tortuga,
                "afección perdicera": afeccion_perdicera,
                "afección nutria": afeccion_nutria,
                "afección fartet": afeccion_fartet,
                "afección malvasia": afeccion_malvasia,
                "afección garbancillo": afeccion_garbancillo,
                "afección flora": afeccion_flora,
                "coordenadas_x": x, "coordenadas_y": y,
                "municipio": municipio_sel, "polígono": masa_sel, "parcela": parcela_sel
            }

            # === 8. MOSTRAR RESULTADOS EN PANTALLA ===
            st.write(f"Municipio seleccionado: {municipio_sel}")
            st.write(f"Polígono seleccionado: {masa_sel}")
            st.write(f"Parcela seleccionada: {parcela_sel}")

            # === 9. GENERAR MAPA ===
            mapa_html, afecciones_lista = crear_mapa(lon, lat, afecciones, parcela_gdf=parcela)
            if mapa_html:
                st.session_state['mapa_html'] = mapa_html
                st.session_state['afecciones'] = afecciones_lista
                st.subheader("Resultado de las afecciones")
                for afeccion in afecciones_lista:
                    st.write(f"• {afeccion}")
                with open(mapa_html, 'r') as f:
                    html(f.read(), height=500)

            # === 10. GENERAR PDF (AL FINAL, CUANDO `datos` EXISTE) ===
            pdf_filename = f"informe_{uuid.uuid4().hex[:8]}.pdf"
            try:
                generar_pdf(datos, x, y, pdf_filename)
                st.session_state['pdf_file'] = pdf_filename
            except Exception as e:
                st.error(f"Error al generar el PDF: {str(e)}")

            # === 11. LIMPIAR DATOS TEMPORALES ===
            st.session_state.pop('query_geom', None)
            st.session_state.pop('wfs_urls', None)

if st.session_state.get('mapa_html') and st.session_state.get('pdf_file'):
    try:
        with open(st.session_state['pdf_file'], "rb") as f:
            st.download_button("📄 Descargar informe PDF", f, file_name="informe_afecciones.pdf")
    except Exception as e:
        st.error(f"Error al descargar el PDF: {str(e)}")

    try:
        with open(st.session_state['mapa_html'], "r") as f:
            st.download_button("🌍 Descargar mapa HTML", f, file_name="mapa_busqueda.html")
    except Exception as e:
        st.error(f"Error al descargar el mapa HTML: {str(e)}")
