import streamlit as st
import pandas as pd
from supabase import create_client, Client
import hashlib
from datetime import datetime

# 1. CONEXIÓN
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- LOGIN DE EMERGENCIA ---
if not st.session_state['logged_in']:
    st.title("📡 Sistema de Antenas - ACCESO DIRECTO")
    u_input = st.text_input("Usuario (Escribí admin)").lower().strip()
    p_input = st.text_input("Contraseña (Cualquier cosa)", type='password')
    
    if st.button("INGRESAR"):
        if u_input == "admin": # PUENTE: Solo revisa que el usuario sea admin
            st.session_state['logged_in'] = True
            st.session_state['username'] = "admin"
            st.session_state['rol'] = "Administrador"
            st.rerun()
        else:
            st.error("Escribí 'admin' para entrar")
else:
    # --- INTERFAZ DEL SISTEMA ---
    st.sidebar.success(f"Conectado como: {st.session_state['username']}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()
        
    menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes"]
    choice = st.sidebar.selectbox("Menú", menu)

    # --- PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("Listado de Clientes")
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            st.dataframe(df.drop(columns=['cuentas']), use_container_width=True)
        else:
            st.info("No hay clientes. Empezá creando una Cuenta y un Plan.")

    # --- REGISTRAR ---
    elif choice == "📝 Registrar/Editar":
        st.subheader("Nueva Instalación")
        ctas = supabase.table("cuentas").select("*").execute()
        plns = supabase.table("planes").select("*").execute()

        if not ctas.data or not plns.data:
            st.warning("⚠️ Primero creá una Cuenta Mail y un Plan en el menú de la izquierda.")
        else:
            with st.form("registro"):
                nombre = st.text_input("Nombre Cliente")
                zona = st.text_input("Zona")
                costo = st.number_input("Costo Mensual", min_value=0.0)
                s_ant = st.text_input("Serie Antena")
                s_rout = st.text_input("Serie Router")
                plan = st.selectbox("Plan", [p['nombre_plan'] for p in plns.data])
                cta_map = {c['mail']: c['id'] for c in ctas.data}
                cta = st.selectbox("Asignar a Cuenta", list(cta_map.keys()))

                if st.form_submit_button("GUARDAR EN LA NUBE"):
                    datos = {
                        "nombre": nombre, "zona": zona, "plan": plan, "costo": costo,
                        "serie_antena": s_ant, "serie_router": s_rout,
                        "cuenta_id": cta_map[cta], "fecha_inst": str(datetime.now().date())
                    }
                    supabase.table("clientes").insert(datos).execute()
                    st.success("¡Guardado! Ya podés verlo en el Panel General.")

    # --- CUENTAS (HACÉ ESTO PRIMERO) ---
    elif choice == "📧 Cuentas":
        st.header("Paso 1: Cargar Cuenta")
        nuevo_mail = st.text_input("Email de la cuenta")
        if st.button("Guardar Cuenta"):
            supabase.table("cuentas").insert({"mail": nuevo_mail}).execute()
            st.success("Cuenta guardada exitosamente.")
            st.rerun()
        res = supabase.table("cuentas").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))

    # --- PLANES ---
    elif choice == "⚙️ Planes":
        st.header("Paso 2: Cargar Plan")
        nuevo_p = st.text_input("Nombre del Plan (ej: 10 Mega)")
        if st.button("Guardar Plan"):
            supabase.table("planes").insert({"nombre_plan": nuevo_p}).execute()
            st.success("Plan guardado.")
            st.rerun()
