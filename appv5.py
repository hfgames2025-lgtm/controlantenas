import streamlit as st
import pandas as pd
from supabase import create_client, Client
import hashlib
import io
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Sistema Antenas Hugo", layout="wide")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Función de Hash corregida
def generar_hash(palabra):
    return hashlib.sha256(palabra.encode('utf-8')).hexdigest()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'edit_client' not in st.session_state: st.session_state['edit_client'] = None

# --- LOGIN ---
if not st.session_state['logged_in']:
    st.title("📡 Acceso al Sistema")
    u_ingresado = st.text_input("Usuario").lower().strip()
    p_ingresada = st.text_input("Contraseña", type='password').strip()
    
    if st.button("INGRESAR"):
        if u_ingresado and p_ingresada:
            res = supabase.table("usuarios").select("*").eq("username", u_ingresado).execute()
            if res.data:
                hash_db = res.data[0]['password']
                hash_intento = generar_hash(p_ingresada)
                
                if hash_intento == hash_db:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = u_ingresado
                    st.session_state['rol'] = res.data[0]['rol']
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
            else:
                st.error("El usuario no existe")
        else:
            st.warning("Por favor completa los campos")

# --- SISTEMA ADENTRO ---
else:
    st.sidebar.title(f"👤 {st.session_state['username']}")
    menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes", "👥 Usuarios"]
    choice = st.sidebar.selectbox("Menú", menu)
    
    if st.sidebar.button("Salir"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("Clientes Registrados")
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            st.dataframe(df.drop(columns=['cuentas', 'cuenta_id']), use_container_width=True)
            
            # Exportar Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Bajar Excel", output.getvalue(), "clientes.xlsx")
        else:
            st.info("No hay clientes todavía.")

    # --- REGISTRAR ---
    elif choice == "📝 Registrar/Editar":
        st.header("Nuevo Registro")
        res_ctas = supabase.table("cuentas").select("*").execute()
        res_plns = supabase.table("planes").select("*").execute()

        if not res_ctas.data or not res_plns.data:
            st.error("Faltan Cuentas o Planes.")
        else:
            with st.form("f_cli"):
                nom = st.text_input("Nombre")
                zon = st.text_input("Zona")
                cos = st.number_input("Costo", min_value=0.0)
                ant = st.text_input("Serie Antena")
                rou = st.text_input("Serie Router")
                pla = st.selectbox("Plan", [p['nombre_plan'] for p in res_plns.data])
                
                map_c = {c['mail']: c['id'] for c in res_ctas.data}
                cta = st.selectbox("Cuenta Mail", list(map_c.keys()))

                if st.form_submit_button("GUARDAR"):
                    d = {"nombre": nom, "zona": zon, "plan": pla, "costo": cos, 
                         "serie_antena": ant, "serie_router": rou, "cuenta_id": map_c[cta],
                         "fecha_inst": str(datetime.now().date())}
                    supabase.table("clientes").insert(d).execute()
                    st.success("Guardado!")
                    st.rerun()

    # --- CUENTAS ---
    elif choice == "📧 Cuentas":
        m = st.text_input("Nuevo Email")
        if st.button("Guardar Cuenta"):
            supabase.table("cuentas").insert({"mail": m}).execute()
            st.rerun()
        res = supabase.table("cuentas").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))

    # --- PLANES ---
    elif choice == "⚙️ Planes":
        p = st.text_input("Nombre Plan")
        if st.button("Crear Plan"):
            supabase.table("planes").insert({"nombre_plan": p}).execute()
            st.rerun()
        res = supabase.table("planes").select("*").execute()
        if res.data: st.table(pd.DataFrame(res.data))
