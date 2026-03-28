import streamlit as st
import pandas as pd
from supabase import create_client, Client
import io
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Sistema Antenas Hugo", layout="wide")

# Verificamos que los Secrets existan
if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    st.error("❌ Error: No se encuentran las llaves en los Secrets de Streamlit.")
    st.stop()

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- LOGIN SIMPLIFICADO ---
if not st.session_state['logged_in']:
    st.title("📡 Acceso Directo - Prueba de Conexión")
    u_ing = st.text_input("Usuario (admin)").lower().strip()
    p_ing = st.text_input("Contraseña (admin123)", type='password').strip()
    
    if st.button("INGRESAR"):
        # Traemos el usuario
        res = supabase.table("usuarios").select("*").eq("username", u_ing).execute()
        
        if res.data:
            clave_en_db = res.data[0]['password']
            # COMPARACIÓN DIRECTA (Sin Hashes)
            if p_ing == clave_en_db:
                st.session_state['logged_in'] = True
                st.session_state['username'] = u_ing
                st.session_state['rol'] = res.data[0]['rol']
                st.rerun()
            else:
                st.error(f"Contraseña no coincide. Escribiste: {p_ing} / En DB hay: {clave_en_db}")
        else:
            st.error("El usuario no existe en Supabase.")

# --- EL RESTO DEL SISTEMA (IGUAL QUE ANTES) ---
else:
    st.sidebar.success(f"Conectado: {st.session_state['username']}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes"]
    choice = st.sidebar.selectbox("Menú", menu)

    if choice == "📊 Panel General":
        st.header("Clientes")
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            st.dataframe(df.drop(columns=['cuentas', 'cuenta_id']), use_container_width=True)
        else:
            st.info("No hay datos todavía.")

    elif choice == "📝 Registrar/Editar":
        st.header("Cargar Cliente")
        res_ctas = supabase.table("cuentas").select("*").execute()
        res_plns = supabase.table("planes").select("*").execute()
        if not res_ctas.data or not res_plns.data:
            st.warning("Cargá Cuentas y Planes primero.")
        else:
            with st.form("f"):
                nom = st.text_input("Nombre")
                cos = st.number_input("Costo", min_value=0.0)
                pla = st.selectbox("Plan", [p['nombre_plan'] for p in res_plns.data])
                map_c = {c['mail']: c['id'] for c in res_ctas.data}
                cta = st.selectbox("Cuenta", list(map_c.keys()))
                if st.form_submit_button("Guardar"):
                    d = {"nombre": nom, "plan": pla, "costo": cos, "cuenta_id": map_c[cta], "fecha_inst": str(datetime.now().date())}
                    supabase.table("clientes").insert(d).execute()
                    st.success("Guardado!")
                    st.rerun()

    elif choice == "📧 Cuentas":
        m = st.text_input("Mail")
        if st.button("Guardar"):
            supabase.table("cuentas").insert({"mail": m}).execute()
            st.rerun()
        res = supabase.table("cuentas").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))

    elif choice == "⚙️ Planes":
        p = st.text_input("Plan")
        if st.button("Guardar"):
            supabase.table("planes").insert({"nombre_plan": p}).execute()
            st.rerun()
        res = supabase.table("planes").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))
