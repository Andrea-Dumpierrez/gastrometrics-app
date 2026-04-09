import streamlit as st
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["gastrometrics"]
collection = db["restaurants"]

st.title("Recomendador de Restaurantes")
st.write("Introduce una ciudad o provincia.")

ciudad = st.text_input("Escribe una ciudad o provincia:")

if st.button("Buscar"):
    if ciudad.strip() == "":
        st.warning("Por favor, escribe una ciudad o provincia.")
    else:
        resultados = collection.find(
            {
                "$or": [
                    {"city": {"$regex": f"^{ciudad}$", "$options": "i"}},
                    {"province": {"$regex": f"^{ciudad}$", "$options": "i"}}
                ]
            },
            {
                "restaurant_name": 1,
                "address": 1,
                "city": 1,
                "province": 1,
                "avg_rating": 1,
                "total_reviews_count": 1,
                "restaurant_link": 1,
                "_id": 0
            }
        ).sort("avg_rating", -1).limit(10)

        resultados = list(resultados)

        if resultados:
            st.success(f"Resultados para {ciudad}:")

            for r in resultados:
                rating = r.get("avg_rating")
                rating = round(rating / 10, 1) if rating else "No disponible"

                st.subheader(r.get("restaurant_name", "Sin nombre"))
                st.write(f"📍 {r.get('address', 'No disponible')}")
                st.write(f"🏙️ {r.get('city', 'No disponible')} ({r.get('province', '')})")
                st.write(f"⭐ {rating}")
                st.write(f"📝 {r.get('total_reviews_count', 'No disponible')} reseñas")
                st.write(f"🔗 {r.get('restaurant_link', 'No disponible')}")
                st.markdown("---")
        else:
            st.error("No se encontraron restaurantes.")