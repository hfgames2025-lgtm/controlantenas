import streamlit as st
import pandas as pd
from supabase import create_client, Client
import io
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="Sistema Antenas Hugo",
    layout="wide",
    page_icon="📡",
    initial_sidebar_state="expanded"
)

# --- DISEÑO CSS CORREGIDO PARA MÉTRICAS VISIBLES ---
st.markdown("""
    <style>
    /* Fondo general de la página */
    .stApp {
        background-color: #f0f2f6;
    }
    /* Estilo de las tarjetas de métricas (los globos) */
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #d1d5db !important;
        padding: 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
        color: #1f2937 !important;
    }
    /* Forzar color de texto en etiquetas de métrica */
    [data-testid="stMetricLabel"] {
        color: #4b5563 !important;
        font-weight: bold !important;
    }
    /* Forzar color de texto en valores de métrica */
    [data-testid="stMetricValue"] {
        color: #111827 !important;
    }
    /* Botones más definidos */
    div.stButton > button:first-child {
        border-radius: 8px;
        font-weight: bold;
        border: 1px solid #d1d5db;
    }
    </style>
    """, unsafe_allow_html=True)

# Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'edit_client' not in st.session_state: st.session_state['edit_client'] = None

# --- LOGIN ---
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.write("")
        st.title("🛰️ Control de Taller")
        with st.container(border=True):
            u_ing = st.text_input("Usuario").lower().strip()
            p_ing = st.text_input("Contraseña", type='password').strip()
            if st.button("🚀 Entrar al Sistema", use_container_width=True):
                res = supabase.table("usuarios").select("*").eq("username", u_ing).execute()
                if res.data and p_ing == res.data[0]['password']:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = u_ing
                    st.session_state['rol'] = res.data[0]['rol']
                    st.rerun()
                else:
                    st.error("Usuario o clave incorrectos.")

# --- SISTEMA ADENTRO ---
else:
    with st.sidebar:
        st.title("📡 Menú Taller")
        st.write(f"Usuario: **{st.session_state['username'].upper()}**")
        st.divider()
        menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes", "👥 Usuarios"]
        choice = st.selectbox("Sección:", menu)
        if st.button("🔒 Salir", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- 1. PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("📊 Resumen de Instalaciones")
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            
            # Estas son las métricas que ahora tienen fondo blanco sólido y sombra
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Clientes", f"{len(df)} pers.")
            m2.metric("Recaudación Total", f"USD {df['costo'].sum():,.0f}")
            
            df_ctas = df['Cuenta Mail'].value_counts().reset_index()
            df_ctas.columns = ['Cuenta Mail', 'Cant. Clientes']
            m3.metric("Cuentas en Uso", len(df_ctas))
            
            st.write("---")
            st.subheader("👥 Clientes por Cuenta")
            st.dataframe(df_ctas, hide_index=True, use_container_width=True)
            
            st.write("---")
            st.subheader("📋 Listado Detallado")
            busq = st.text_input("🔍 Buscar...")
            if busq:
                df = df[df.apply(lambda r: r.astype(str).str.contains(busq, case=False).any(), axis=1)]
            
            st.dataframe(df.drop(columns=['cuentas', 'cuenta_id']), use_container_width=True, hide_index=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", output.getvalue(), "listado.xlsx")

            with st.expander("🛠️ Acciones (Editar/Borrar)"):
                c1, c2 = st.columns(2)
                with c1:
                    id_edit = st.number_input("ID para editar", min_value=0, step=1)
                    if st.button("📝 Cargar Datos"):
                        st.session_state['edit_client'] = next((i for i in res.data if i['id'] == id_edit), None)
                        if st.session_state['edit_client']: st.success("Cargado. Ve a Registrar.")
                with c2:
                    if st.session_state['rol'] == "Administrador":
                        id_del = st.number_input("ID para eliminar", min_value=0, step=1)
                        if st.button("🗑️ Borrar"):
                            supabase.table("clientes").delete().eq("id", id_del).execute()
                            st.rerun()
        else:
            st.info("No hay datos cargados.")

    # --- 2. REGISTRAR / EDITAR ---
    elif choice == "📝 Registrar/Editar":
        edit = st.session_state['edit_client']
        st.header("🛠️ Modificar" if edit else "🆕 Nuevo Registro")
        
        res_ctas = supabase.table("cuentas").select("*").execute()
        res_plns = supabase.table("planes").select("*").execute()

        if not res_ctas.data or not res_plns.data:
            st.error("Faltan Cuentas o Planes.")
        else:
            with st.form("f_reg", clear_on_submit=not edit):
                col1, col2 = st.columns(2)
                with col1:
                    nombre = st.text_input("Nombre Cliente", value=edit['nombre'] if edit else "")
                    zona = st.text_input("Zona", value=edit['zona'] if edit else "")
                    plan = st.selectbox("Plan", [p['nombre_plan'] for p in res_plns.data])
                    fecha_def = datetime.strptime(edit['fecha_inst'], '%Y-%m-%d') if edit else datetime.now()
                    fecha_inst = st.date_input("Fecha de Instalación", value=fecha_def)
                with col2:
                    costo = st.number_input("Costo", value=float(edit['costo']) if edit else 0.0)
                    s_ant = st.text_input("Serie Antena", value=edit['serie_antena'] if edit else "")
                    s_rou = st.text_input("Serie Router", value=edit['serie_router'] if edit else "")
                    map_c = {c['mail']: c['id'] for c in res_ctas.data}
                    cta = st.selectbox("Cuenta Mail", list(map_c.keys()))

                if st.form_submit_button("💾 GUARDAR"):
                    d = {
                        "nombre": nombre, "zona": zona, "plan": plan, "costo": costo, 
                        "serie_antena": s_ant, "serie_router": s_rou, 
                        "cuenta_id": map_c[cta], "fecha_inst": str(fecha_inst)
                    }
                    if edit:
                        supabase.table("clientes").update(d).eq("id", edit['id']).execute()
                        st.session_state['edit_client'] = None
                    else:
                        supabase.table("clientes").insert(d).execute()
                    st.success("¡Guardado!")
                    st.rerun()

    # --- 3. CUENTAS ---
    elif choice == "📧 Cuentas":
        st.header("📧 Cuentas Mail")
        c1, c2 = st.columns([1, 2])
        with c1:
            m = st.text_input("Nuevo Mail")
            if st.button("➕ Agregar"):
                supabase.table("cuentas").insert({"mail": m}).execute()
                st.rerun()
        with c2:
            res = supabase.table("cuentas").select("*").execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data), use_container_width=True, hide_index=True)
                if st.session_state['rol'] == "Administrador":
                    id_c = st.number_input("ID Cuenta a borrar", min_value=0, step=1)
                    if st.button("🗑️ Borrar Cuenta"):
                        supabase.table("cuentas").delete().eq("id", id_c).execute()
                        st.rerun()

    # --- 4. PLANES ---
    elif choice == "⚙️ Planes":
        st.header("⚙️ Planes")
        c1, c2 = st.columns([1, 2])
        with c1:
            p = st.text_input("Nombre Plan")
            if st.button("➕ Crear"):
                supabase.table("planes").insert({"nombre_plan": p}).execute()
                st.rerun()
        with c2:
            res = supabase.table("planes").select("*").execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data), use_container_width=True, hide_index=True)
                if st.session_state['rol'] == "Administrador":
                    id_p = st.number_input("ID Plan a borrar", min_value=0, step=1)
                    if st.button("🗑️ Borrar Plan"):
                        supabase.table("planes").delete().eq("id", id_p).execute()
                        st.rerun()

    # --- 5. USUARIOS ---
    elif choice == "👥 Usuarios":
        st.header("👥 Accesos")
        if st.session_state['rol'] == "Administrador":
            with st.container(border=True):
                u, p, r = st.columns(3)
                new_u = u.text_input("Usuario")
                new_p = p.text_input("Clave")
                new_r = r.selectbox("Rol", ["Operador", "Administrador"])
                if st.button("➕ Crear Usuario"):
                    supabase.table("usuarios").insert({"username": new_u.lower(), "password": new_p, "rol": new_r}).execute()
                    st.rerun()
            res_u = supabase.table("usuarios").select("id, username, rol").execute()
            if res_u.data:
                st.dataframe(pd.DataFrame(res_u.data), use_container_width=True, hide_index=True)
                id_u = st.number_input("ID Usuario a borrar", min_value=0, step=1)
                if st.button("🗑️ Borrar"):
                    supabase.table("usuarios").delete().eq("id", id_u).execute()
                    st.rerun()
