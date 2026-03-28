import streamlit as st
import pandas as pd
from supabase import create_client, Client
import hashlib
from datetime import datetime

# 1. CONEXIÓN (Probada y funcionando)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

def check_hashes(password, hashed_text):
    return hashlib.sha256(str.encode(password)).hexdigest() == hashed_text

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("📡 Acceso al Sistema - Nube")
    
    # Usamos strip() para borrar cualquier espacio accidental al principio o final
    u_input = st.text_input("Usuario").lower().strip()
    p_input = st.text_input("Contraseña", type='password').strip()
    
    if st.button("INGRESAR AHORA"):
        # Traemos el usuario de la base
        res = supabase.table("usuarios").select("*").eq("username", u_input).execute()
        
        if res.data:
            datos_db = res.data[0]
            if check_hashes(p_input, datos_db['password']):
                st.session_state['logged_in'] = True
                st.session_state['rol'] = datos_db['rol']
                st.session_state['username'] = u_input
                st.rerun()
            else:
                st.error(f"❌ La contraseña no coincide para el usuario '{u_input}'")
        else:
            st.error(f"❌ El usuario '{u_input}' no existe en la base de datos de Supabase")
            
else:
    # --- SI LOGRÁS ENTRAR, VES ESTO ---
    st.sidebar.success(f"Conectado como: {st.session_state['username']}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()
        
    menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes"]
    choice = st.sidebar.selectbox("Menú", menu)

    # --- PANEL GENERAL (Simplificado para probar) ---
    if choice == "📊 Panel General":
        st.header("Clientes en la Nube")
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data))
        else:
            st.info("Conexión OK. No hay clientes cargados aún.")

    # --- CARGA DE CUENTAS (HACÉ ESTO PRIMERO) ---
    elif choice == "📧 Cuentas":
        st.subheader("Paso 1: Cargar una Cuenta")
        nuevo_mail = st.text_input("Email de la cuenta (ej: cuenta1@gmail.com)")
        if st.button("Guardar Cuenta"):
            supabase.table("cuentas").insert({"mail": nuevo_mail}).execute()
            st.success("Cuenta guardada!")
            st.rerun()
