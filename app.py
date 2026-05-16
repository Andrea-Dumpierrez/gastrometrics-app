import streamlit as st
import pandas as pd
import pydeck as pdk
from pymongo import MongoClient
import math
import altair as alt

# Configuración General
st.set_page_config(page_title="GastroMetrics", page_icon="🍽️", layout="wide")

# Conexión a MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["gastrometrics"]
collection = db["restaurants"]

# Lógica inteligente para recuperar coordenadas rotas
def fix_latitude(val):
    val = float(val)
    # Límites latitud en España: ~27 (Islas Canarias) a ~44 (Costa Norte)
    while val > 45 or val < 25:
        val = val / 10
    return val

def fix_longitude(val):
    val = float(val)
    # Límites longitud en España: ~-19 (Islas Canarias) a ~5 (Islas Baleares)
    while val > 5 or val < -20:
        val = val / 10
    return val

# Funcion para calcular el zoom dinamico basado en la dispersion de los puntos
def calculate_dynamic_zoom(df):
    if len(df) <= 1:
        return 13

    lat_spread = df["lat"].max() - df["lat"].min()
    lon_spread = df["lon"].max() - df["lon"].min()
    max_spread = max(lat_spread, lon_spread)

    if max_spread < 0.05:
        return 12 # Restaurantes muy juntos (mismo barrio o ciudad compacta)
    elif max_spread < 0.15:
        return 10 # Ciudad grande
    elif max_spread < 0.5:
        return 9  # Area metropolitana
    else:
        return 8  # Restaurantes dispersos por toda la region

# Fórmula matemática para el score de popularidad
def calculate_popularity(rating, reviews):
    if not rating or not reviews or reviews <= 0:
        return 0
    # Usamos log(reseñas + 1) para suavizar el impacto de miles de reseñas
    return round(rating * math.log1p(reviews), 2)

# Interfaz principal visible para el usuario
st.title("Gastrometría 🍽️")
st.write("Encuentra restaurantes recomendados según ubicación, cocina y valoración.")

# Barra lateral con filtros
st.sidebar.header("Filtros de Búsqueda 🔍")

# Obtenemos ciudades únicas para el selector
city_list = sorted([x for x in collection.distinct("city") if x])
selected_city = st.sidebar.selectbox("🏙️ Selecciona una ciudad:", city_list)

# Obtenemos tipos de comida únicos, separando los que vienen en listas (ej. "Italian, Pizza")
raw_cuisines = collection.distinct("cuisines")
cuisines_set = set()
for c in raw_cuisines:
    if pd.notnull(c) and str(c).lower() != "nan":
        for item in str(c).split(","):
            clean_item = item.strip()
            if clean_item:
                cuisines_set.add(clean_item)

cuisine_list = ["Cualquiera"] + sorted(list(cuisines_set))
selected_cuisine = st.sidebar.selectbox("🍝 Tipo de comida (opcional):", cuisine_list)

# Filtro de nota mínima (Rating original)
min_rating = st.sidebar.slider("⭐ Calificación mínima", 0.0, 5.0, 3.0, 0.5)

# Botón de búsqueda
if st.sidebar.button("Buscar Restaurantes 🚀"):
    rating_threshold = int(min_rating * 10)
    
    # Construcción dinámica de la consulta a la base de datos
    query = {
        "city": selected_city,
        "avg_rating": {"$gte": rating_threshold}
    }
    
    # Añadimos filtros opcionales si el usuario los ha rellenado
    if selected_cuisine != "Cualquiera":
        query["cuisines"] = {"$regex": selected_cuisine, "$options": "i"}
    
    # ORDENACIÓN INTELIGENTE EN BASE DE DATOS 
    # Ordenamos en la BD por nota y reseñas para asegurar que los mejores candidatos entran en el pool de cálculo.
    cursor = collection.find(query).sort([
        ("avg_rating", -1), 
        ("total_reviews_count", -1)
    ]).limit(100) # Aumentamos el pool a 100 para más fiabilidad
    
    results = list(cursor)
    
    if results:
        # Creación de pestañas para organizar la vista
        tab_results, tab_stats = st.tabs(["📋 Resultados y Mapa", "📊 Estadísticas de la Ciudad"])
        
        with tab_results:
            # Creamos el DataFrame base con los 100 candidatos
            df_candidates = pd.DataFrame(results)
            
            # Procesamiento de coordenadas y cálculo de métricas para todos los candidatos
            df_candidates["lat"] = df_candidates["latitude"].apply(fix_latitude)
            df_candidates["lon"] = df_candidates["longitude"].apply(fix_longitude)
            df_candidates["display_rating"] = df_candidates["avg_rating"].apply(lambda x: round(x / 10, 1) if pd.notnull(x) else 0)
            df_candidates["popularity_score"] = df_candidates.apply(
                lambda row: calculate_popularity(row["display_rating"], row.get("total_reviews_count", 0)), 
                axis=1
            )
            
            # Ordenar FINALMENTE los candidatos por el Score de Popularidad exacto
            df_sorted = df_candidates.sort_values(by="popularity_score", ascending=False)
            
            # Creamos un DataFrame secundario SÓLO con los 10 mejores del ranking
            df_top_10 = df_sorted.head(10).copy()
            
            col_list, col_map = st.columns([1, 1.2])
            
            with col_list:
                st.subheader(f"Top 10 Restaurantes Populares en {selected_city}")
                # Iteramos sobre el DataFrame de los 10 mejores
                for _, row in df_top_10.iterrows():
                    st.markdown(f"### {row.get('restaurant_name', 'Sin nombre')}")
                    
                    # Gestión de datos nulos en la visualización
                    address = row.get('address', 'No disponible')
                    cuisines = row.get('cuisines', 'No disponible')
                    price = row.get('price_range', 'No disponible')
                    reviews = row.get('total_reviews_count', 0)

                    # Limpieza visual para evitar que salga "nan" en la interfaz
                    if pd.isna(address) or str(address).lower() == "nan": 
                        address = "No disponible"
                    if pd.isna(cuisines) or str(cuisines).lower() == "nan": 
                        cuisines = "No disponible"
                    if pd.isna(price) or str(price).lower() == "nan": 
                        price = "No disponible"
                    
                    st.write(f"📍 Dirección: {address}")
                    st.write(f"🍝 Cocina: {cuisines}")
                    st.write(f"💰 Precio: {price}")
                    st.write(f"⭐ Rating medio: {row['display_rating']}")
                    st.write(f"📝 Número de reseñas: {reviews}")
                    st.info(f"🔥 Score de Popularidad: {row['popularity_score']}")
                    st.divider()

            with col_map:
                st.subheader("🗺️ Mapa del Ranking")
                
                # Calculamos el centro del mapa SÓLO con la media de los 10 mejores
                dynamic_zoom = calculate_dynamic_zoom(df_top_10)

                view_state = pdk.ViewState(
                    latitude=float(df_top_10["lat"].mean()),
                    longitude=float(df_top_10["lon"].mean()),
                    zoom=dynamic_zoom,
                    pitch=0
                )
                
                # Dibujamos los 10 puntos del ranking
                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_top_10, # Usamos el DataFrame filtrado de 10
                    get_position=["lon", "lat"],
                    get_radius=100, # Radio fijo en metros
                    radius_min_pixels=6,
                    get_fill_color=[255, 0, 0, 140],
                    get_line_color=[255, 255, 255],
                    line_width_min_pixels=1,
                    stroked=True,
                    filled=True,
                    pickable=True
                )
                
                # Tooltip actualizado
                tooltip = {
                    "html": "<b>{restaurant_name}</b><br/>⭐ Rating: {display_rating}<br/>🔥 Score: {popularity_score}",
                    "style": {"backgroundColor": "white", "color": "black"}
                }
                
                st.pydeck_chart(pdk.Deck(
                    layers=[layer], 
                    initial_view_state=view_state,
                    tooltip=tooltip
                ))

        with tab_stats:
            st.subheader(f"Distribución de Cocinas (Basado en Top 100 de {selected_city})")
            # Usamos el DataFrame de candidatos (100) para estadísticas más ricas
            if "cuisines" in df_candidates.columns:
                # Limpieza y conteo de cocinas
                all_cuisines = df_candidates["cuisines"].dropna().astype(str).str.split(", ").explode()
                top_cuisines = all_cuisines.value_counts().head(10)
                
                if not top_cuisines.empty:
                    # Convertimos la Serie de datos a un DataFrame compatible con Altair
                    df_chart = top_cuisines.reset_index()
                    df_chart.columns = ["Cuisine", "Count"]

                    chart = alt.Chart(df_chart).mark_bar().encode(
                        x=alt.X("Cuisine", sort=None, title="", axis=alt.Axis(labelAngle=-45)),
                        y=alt.Y("Count", title="")
                    )
                    
                    # Dibujamos el grafico
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.warning("No hay datos de cocina suficientes para generar el gráfico.")
            else:
                st.warning("No hay datos de cocina suficientes para generar el gráfico.")

    else:
        st.error("No se encontraron restaurantes con esos filtros. Prueba a bajar la nota o quitar el filtro de precio.")