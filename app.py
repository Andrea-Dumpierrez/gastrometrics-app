import streamlit as st
import pandas as pd
import pydeck as pdk
from pymongo import MongoClient

# -----------------------------
# CONFIGURACIÓN GENERAL
# -----------------------------
st.set_page_config(page_title="GastroMetrics", page_icon="🍽️", layout="wide")

# Conexión a MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["gastrometrics"]
collection = db["restaurants"]

# -----------------------------
# INTERFAZ
# -----------------------------
st.title("Gastrometría 🍽️")
st.write("Encuentra restaurantes recomendados según ubicación, cocina y valoración.")

tipo_busqueda = st.radio(
    "¿Cómo quieres buscar?",
    ["Ciudad", "Provincia"],
    horizontal=True
)

if tipo_busqueda == "Ciudad":
    opciones = sorted([x for x in collection.distinct("city") if x])
else:
    opciones = sorted([x for x in collection.distinct("province") if x])

ubicacion = st.selectbox("Selecciona una opción:", opciones)
tipo_comida = st.text_input("Tipo de comida (opcional):")
rating_min = st.slider("Calificación mínima", 0.0, 5.0, 3.0, 0.5)

# -----------------------------
# BÚSQUEDA
# -----------------------------
if st.button("Buscar"):

    campo = "city" if tipo_busqueda == "Ciudad" else "province"
    rating_bd = int(rating_min * 10)

    filtro = {
        campo: ubicacion,
        "avg_rating": {"$gte": rating_bd}
    }

    if tipo_comida.strip() != "":
        filtro["cuisines"] = {"$regex": tipo_comida, "$options": "i"}

    resultados = collection.find(
        filtro,
        {
            "restaurant_name": 1,
            "address": 1,
            "city": 1,
            "province": 1,
            "cuisines": 1,
            "avg_rating": 1,
            "total_reviews_count": 1,
            "latitude": 1,
            "longitude": 1,
            "_id": 0
        }
    ).sort([
        ("avg_rating", -1),
        ("total_reviews_count", -1)
    ]).limit(10)

    resultados = list(resultados)

    if resultados:
        st.success(f"Se encontraron {len(resultados)} restaurantes.")

        col1, col2 = st.columns([1.1, 1])

        with col1:
            for r in resultados:
                nombre = r.get("restaurant_name", "Sin nombre")
                direccion = r.get("address", "No disponible")
                ciudad = r.get("city", "No disponible")
                provincia = r.get("province", "No disponible")
                cocina = r.get("cuisines", "No disponible")
                reviews = r.get("total_reviews_count", "No disponible")

                avg_rating = r.get("avg_rating")
                rating = round(avg_rating / 10, 1) if avg_rating is not None else "No disponible"

                st.subheader(nombre)
                st.write(f"📍 Dirección: {direccion}")
                st.write(f"🏙️ Ciudad: {ciudad}")
                st.write(f"🗺️ Provincia: {provincia}")
                st.write(f"🍝 Cocina: {cocina}")
                st.write(f"⭐ Rating medio: {rating}")
                st.write(f"📝 Número de reseñas: {reviews}")
                st.markdown("---")

        with col2:
            df_mapa = pd.DataFrame(resultados)

            if not df_mapa.empty:
                df_mapa["latitude"] = pd.to_numeric(df_mapa["latitude"], errors="coerce")
                df_mapa["longitude"] = pd.to_numeric(df_mapa["longitude"], errors="coerce")

                df_mapa = df_mapa.dropna(subset=["latitude", "longitude"])

                if not df_mapa.empty:
                    # Corregir escala de coordenadas
                    df_mapa["lat"] = df_mapa["latitude"] / 1000000
                    df_mapa["lon"] = df_mapa["longitude"] / 1000000

                    df_mapa["rating_mostrado"] = df_mapa["avg_rating"].apply(
                        lambda x: round(x / 10, 1) if pd.notnull(x) else "No disponible"
                    )

                    st.subheader("Mapa de restaurantes")

                    view_state = pdk.ViewState(
                        latitude=float(df_mapa["lat"].mean()),
                        longitude=float(df_mapa["lon"].mean()),
                        zoom=8,
                        pitch=0
                    )

                    layer = pdk.Layer(
                        "ScatterplotLayer",
                        data=df_mapa,
                        get_position=["lon", "lat"],
                        get_radius=1500,
                        get_fill_color=[255, 0, 0, 140],
                        get_line_color=[255, 255, 255],
                        line_width_min_pixels=1,
                        stroked=True,
                        filled=True,
                        pickable=True
                    )

                    tooltip = {
                        "html": """
                        <b>{restaurant_name}</b><br/>
                        📍 {address}<br/>
                        ⭐ {rating_mostrado}<br/>
                        📝 {total_reviews_count} reseñas
                        """,
                        "style": {
                            "backgroundColor": "white",
                            "color": "black"
                        }
                    }

                    deck = pdk.Deck(
                        initial_view_state=view_state,
                        layers=[layer],
                        tooltip=tooltip
                    )

                    st.pydeck_chart(deck, use_container_width=True)

                else:
                    st.warning("No hay coordenadas válidas para mostrar el mapa.")
            else:
                st.warning("No hay resultados para generar el mapa.")

    else:
        st.error("No se encontraron restaurantes con esos filtros.")