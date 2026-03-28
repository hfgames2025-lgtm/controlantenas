import streamlit as st
import pandas as pd
from supabase import create_client, Client
import hashlib
import io
from datetime import datetime

# 1. CONEXIÓN A LA NUBE (Supabase)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# --- SESIÓN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'edit_client' not in st.session_state: st.session_state['edit_client'] = None

# --- LOGIN ---
if not st.session_state['logged_in']:
    st.title("📡 Sistema de Antenas - NUBE")
    u = st.text_input("Usuario")
    p = st.text_input("Clave", type='password')
    if st.button("Entrar"):
        # Buscamos el usuario en Supabase
        res = supabase.table("usuarios").select("*").eq("username", u).execute()
        if res.data and check_hashes(p, res.data[0]['password']):
            st.session_state['logged_in'] = True
            st.session_state['username'] = u
            st.session_state['rol'] = res.data[0]['rol']
            st.rerun()
        else: st.error("Usuario o clave incorrectos")
else:
    st.sidebar.title(f"Hola {st.session_state['username']}")
    menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes"]
    if st.session_state['rol'] == "Administrador": menu.append("👥 Usuarios")
    choice = st.sidebar.selectbox("Ir a:", menu)

    # --- PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("Listado de Clientes en la Nube")
        # Traemos clientes y el mail de su cuenta asociada
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            # Limpiamos el formato del mail que viene de la relación
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            
            st.metric("Total Clientes", len(df), f"${df['costo'].sum():,.2f} Recaudación")
            
            busq = st.text_input("🔍 Buscar...")
            if busq: df = df[df.apply(lambda r: r.astype(str).str.contains(busq, case=False).any(), axis=1)]
            
            st.dataframe(df.drop(columns=['cuentas']), use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                id_e = st.number_input("ID para EDITAR", min_value=0, step=1)
                if st.button("Cargar para Modificar"):
                    st.session_state['edit_client'] = next((item for item in res.data if item["id"] == id_e), None)
                    st.success("Cargado. Ve a la pestaña Registrar.")
            
            if st.session_state['rol'] == "Administrador":
                with col2:
                    id_b = st.number_input("ID para BORRAR", min_value=0, step=1)
                    if st.button("Borrar Permanente"):
                        supabase.table("clientes").delete().eq("id", id_b).execute()
                        st.rerun()
        else: st.info("No hay datos guardados todavía.")

    # --- REGISTRAR / EDITAR ---
    elif choice == "📝 Registrar/Editar":
        edit = st.session_state['edit_client']
        st.subheader("Modificar" if edit else "Nueva Instalación")
        
        ctas = supabase.table("cuentas").select("*").execute()
        plns = supabase.table("planes").select("*").execute()

        if not ctas.data or not plns.data:
            st.warning("Cargá primero una Cuenta y un Plan.")
        else:
            with st.form("f"):
                c1, c2 = st.columns(2)
                nombre = c1.text_input("Nombre", value=edit['nombre'] if edit else "")
                zona = c1.text_input("Zona", value=edit['zona'] if edit else "")
                costo = c2.number_input("Costo", value=float(edit['costo']) if edit else 0.0)
                s_ant = c2.text_input("Serie Antena", value=edit['serie_antena'] if edit else "")
                s_rou = c2.text_input("Serie Router", value=edit['serie_router'] if edit else "")
                
                plan = st.selectbox("Plan", [p['nombre_plan'] for p in plns.data])
                cta_map = {c['mail']: c['id'] for c in ctas.data}
                cta = st.selectbox("Cuenta Mail", list(cta_map.keys()))

                if st.form_submit_button("GUARDAR EN LA NUBE"):
                    datos = {
                        "nombre": nombre, "zona": zona, "plan": plan, "costo": costo, 
                        "serie_antena": s_ant, "serie_router": s_rou, "cuenta_id": cta_map[cta],
                        "fecha_inst": str(datetime.now().date())
                    }
                    if edit:
                        supabase.table("clientes").update(datos).eq("id", edit['id']).execute()
                        st.session_state['edit_client'] = None
                    else:
                        supabase.table("clientes").insert(datos).execute()
                    st.success("¡Guardado correctamente!")
                    st.rerun()

    # --- CUENTAS Y PLANES ---
    elif choice == "📧 Cuentas":
        m = st.text_input("Nuevo Mail de Cuenta")
        if st.button("Añadir Cuenta"):
            supabase.table("cuentas").insert({"mail": m}).execute()
            st.rerun()
        res = supabase.table("cuentas").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))

    elif choice == "⚙️ Planes":
        p = st.text_input("Nombre del Plan")
        if st.button("Crear Plan"):
            supabase.table("planes").insert({"nombre_plan": p}).execute()
            st.rerun()
        res = supabase.table("planes").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))
