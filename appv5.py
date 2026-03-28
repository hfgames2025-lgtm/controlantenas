import streamlit as st
import pandas as pd
from supabase import create_client, Client
import hashlib
import io
from datetime import datetime

# 1. CONEXIÓN (Ya probamos que esto funciona)
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
    st.title("📡 Gestión de Antenas - NUBE")
    u = st.text_input("Usuario").lower().strip() # Forzamos minúsculas y sacamos espacios
    p = st.text_input("Clave", type='password').strip()
    
    if st.button("Ingresar"):
        res = supabase.table("usuarios").select("*").eq("username", u).execute()
        if res.data and check_hashes(p, res.data[0]['password']):
            st.session_state['logged_in'] = True
            st.session_state['username'] = u
            st.session_state['rol'] = res.data[0]['rol']
            st.rerun()
        else:
            st.error("Usuario o clave incorrectos")
else:
    # --- INTERFAZ DENTRO DEL SISTEMA ---
    st.sidebar.title(f"👤 {st.session_state['username']}")
    menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes"]
    if st.session_state['rol'] == "Administrador":
        menu.append("👥 Usuarios")
    
    choice = st.sidebar.selectbox("Ir a:", menu)
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("Listado Real-Time")
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        
        if res.data:
            df_raw = pd.DataFrame(res.data)
            df = df_raw.copy()
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            
            st.metric("Clientes", len(df), f"${df['costo'].sum():,.2f} Mensuales")
            
            busq = st.text_input("🔍 Buscar por nombre, zona o serie...")
            if busq:
                df = df[df.apply(lambda r: r.astype(str).str.contains(busq, case=False).any(), axis=1)]
            
            st.dataframe(df.drop(columns=['cuentas']), use_container_width=True)

            # Botones de Acción
            col_e, col_b = st.columns(2)
            with col_e:
                id_e = st.number_input("ID para EDITAR", min_value=0, step=1)
                if st.button("Cargar Datos"):
                    st.session_state['edit_client'] = next((i for i in res.data if i['id'] == id_e), None)
                    if st.session_state['edit_client']: st.success("Cargado. Ve a 'Registrar/Editar'")
            
            if st.session_state['rol'] == "Administrador":
                with col_b:
                    id_b = st.number_input("ID para BORRAR", min_value=0, step=1)
                    if st.button("❌ ELIMINAR REGISTRO"):
                        supabase.table("clientes").delete().eq("id", id_b).execute()
                        st.rerun()
        else:
            st.info("No hay datos cargados en Supabase.")

    # --- REGISTRAR / EDITAR ---
    elif choice == "📝 Registrar/Editar":
        edit = st.session_state['edit_client']
        st.subheader("🛠️ Modificar" if edit else "🆕 Nueva Instalación")
        
        ctas = supabase.table("cuentas").select("*").execute()
        plns = supabase.table("planes").select("*").execute()

        if not ctas.data or not plns.data:
            st.warning("⚠️ Primero debés crear Cuentas y Planes.")
        else:
            with st.form("form_registro"):
                c1, c2 = st.columns(2)
                nombre = c1.text_input("Nombre", value=edit['nombre'] if edit else "")
                zona = c1.text_input("Zona", value=edit['zona'] if edit else "")
                costo = c2.number_input("Costo", value=float(edit['costo']) if edit else 0.0)
                s_antena = c2.text_input("Serie Antena", value=edit['serie_antena'] if edit else "")
                s_router = c2.text_input("Serie Router", value=edit['serie_router'] if edit else "")
                
                plan = st.selectbox("Plan", [p['nombre_plan'] for p in plns.data])
                cta_map = {c['mail']: c['id'] for c in ctas.data}
                cta = st.selectbox("Cuenta Mail", list(cta_map.keys()))

                if st.form_submit_button("GUARDAR DATOS"):
                    payload = {
                        "nombre": nombre, "zona": zona, "plan": plan, "costo": costo,
                        "serie_antena": s_antena, "serie_router": s_router,
                        "cuenta_id": cta_map[cta], "fecha_inst": str(datetime.now().date())
                    }
                    if edit:
                        supabase.table("clientes").update(payload).eq("id", edit['id']).execute()
                        st.session_state['edit_client'] = None
                    else:
                        supabase.table("clientes").insert(payload).execute()
                    st.success("¡Guardado en la nube!")
                    st.rerun()

    # --- OTROS MENÚS ---
    elif choice == "📧 Cuentas":
        m = st.text_input("Nuevo Mail")
        if st.button("Añadir"):
            supabase.table("cuentas").insert({"mail": m}).execute()
            st.rerun()
        res = supabase.table("cuentas").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))

    elif choice == "⚙️ Planes":
        p = st.text_input("Nombre Plan")
        if st.button("Crear"):
            supabase.table("planes").insert({"nombre_plan": p}).execute()
            st.rerun()
        res = supabase.table("planes").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))
