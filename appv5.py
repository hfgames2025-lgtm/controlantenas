import streamlit as st
from supabase import create_client, Client

st.title("Test de Conexión Hugo")

try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
    
    st.write("✅ Conexión técnica establecida")
    
    # Intentamos leer la tabla de usuarios
    res = supabase.table("usuarios").select("*").execute()
    st.write("📊 Datos encontrados en la tabla usuarios:", res.data)
    
except Exception as e:
    st.error(f"❌ Error detectado: {e}")
