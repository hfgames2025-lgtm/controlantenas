import streamlit as st
import pandas as pd
from supabase import create_client, Client
import io
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA (Estética Global)
st.set_page_config(
    page_title="Gestión Taller Hugo",
    layout="wide",
    page_icon="📡",
    initial_sidebar_state="expanded"
)

# Estilo Personalizado con CSS
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div.stButton > button:first-child {
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'edit_client' not in st.session_state: st.session_state['edit_client'] = None

# --- PANTALLA DE LOGIN ---
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("") # Espacio
        st.write("")
        st.title("🛰️ Sistema de Gestión")
        with st.container(border=True):
            u_ing = st.text_input("Usuario").lower().strip()
            p_ing = st.text_input("Contraseña", type='password').strip()
            if st.button("🚀 Ingresar al Taller", use_container_width=True):
                res = supabase.table("usuarios").select("*").eq("username", u_ing).execute()
                if res.data and p_ing == res.data[0]['password']:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = u_ing
                    st.session_state['rol'] = res.data[0]['rol']
                    st.rerun()
                else:
                    st.error("Credenciales inválidas")

# --- SISTEMA ADENTRO ---
else:
    # Sidebar Profesional
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2092/2092663.png", width=80)
        st.title(f"Bienvenido, {st.session_state['username'].capitalize()}")
        st.write(f"🎭 Rol: **{st.session_state['rol']}**")
        st.divider()
        menu = ["📊 Resumen General", "📝 Registro y Edición", "📧 Gestión de Cuentas", "⚙️ Config. Planes", "👥 Usuarios"]
        choice = st.selectbox("Navegación", menu)
        st.write("")
        if st.button("🔒 Cerrar Sesión", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- 1. PANEL GENERAL ---
    if choice == "📊 Resumen General":
        st.header("📊 Vista General de Clientes")
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            
            # Métricas Visuales
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Abonados", len(df), "👤")
            m2.metric("Recaudación Estimada", f"USD {df['costo'].sum():,.0f}", "💰")
            m3.metric("Última Instalación", df['fecha_inst'].max(), "📅")
            
            st.write("---")
            busq = st.text_input("🔍 Filtrar por nombre, zona o números de serie...")
            if busq:
                df = df[df.apply(lambda r: r.astype(str).str.contains(busq, case=False).any(), axis=1)]
            
            st.dataframe(df.drop(columns=['cuentas', 'cuenta_id']), use_container_width=True, hide_index=True)

            col_a, col_b = st.columns([2, 1])
            with col_a:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 Descargar Reporte Excel", output.getvalue(), "planilla_taller.xlsx")

            # Sección de acciones rápidas
            st.subheader("⚡ Acciones Rápidas")
            with st.expander("Modificar o Eliminar Registros"):
                c1, c2 = st.columns(2)
                with c1:
                    id_edit = st.number_input("ID Cliente para editar", min_value=0, step=1)
                    if st.button("📝 Cargar para Editar", use_container_width=True):
                        st.session_state['edit_client'] = next((i for i in res.data if i['id'] == id_edit), None)
                        if st.session_state['edit_client']: st.success("Cargado. Ve a Registro.")
                with c2:
                    if st.session_state['rol'] == "Administrador":
                        id_del = st.number_input("ID Cliente para borrar", min_value=0, step=1)
                        if st.button("🗑️ Eliminar Permanente", use_container_width=True):
                            supabase.table("clientes").delete().eq("id", id_del).execute()
                            st.rerun()
        else:
            st.info("Aún no hay clientes registrados.")

    # --- 2. REGISTRAR / EDITAR ---
    elif choice == "📝 Registro y Edición":
        edit = st.session_state['edit_client']
        st.header("🛠️ Edición" if edit else "🆕 Registro de Instalación")
        
        res_ctas = supabase.table("cuentas").select("*").execute()
        res_plns = supabase.table("planes").select("*").execute()

        if not res_ctas.data or not res_plns.data:
            st.error("⚠️ Falta cargar Cuentas o Planes para poder registrar.")
        else:
            with st.form("form_registro", clear_on_submit=not edit):
                col_left, col_right = st.columns(2)
                with col_left:
                    nombre = st.text_input("Nombre del Cliente", value=edit['nombre'] if edit else "")
                    zona = st.text_input("Zona / Barrio", value=edit['zona'] if edit else "")
                    plan = st.selectbox("Plan Contratado", [p['nombre_plan'] for p in res_plns.data])
                with col_right:
                    costo = st.number_input("Costo Mensual", value=float(edit['costo']) if edit else 0.0)
                    s_antena = st.text_input("N° Serie Antena", value=edit['serie_antena'] if edit else "")
                    s_router = st.text_input("N° Serie Router", value=edit['serie_router'] if edit else "")
                
                map_c = {c['mail']: c['id'] for c in res_ctas.data}
                cta = st.selectbox("Asignar a Cuenta", list(map_c.keys()))

                if st.form_submit_button("💾 GUARDAR CAMBIOS" if edit else "➕ REGISTRAR INSTALACIÓN", use_container_width=True):
                    datos = {"nombre": nombre, "zona": zona, "plan": plan, "costo": costo, "serie_antena": s_antena, "serie_router": s_router, "cuenta_id": map_c[cta], "fecha_inst": str(datetime.now().date())}
                    if edit:
                        supabase.table("clientes").update(datos).eq("id", edit['id']).execute()
                        st.session_state['edit_client'] = None
                        st.success("✅ Actualizado correctamente")
                    else:
                        supabase.table("clientes").insert(datos).execute()
                        st.success("✅ Cliente registrado exitosamente")
                    st.rerun()

    # --- 3. CUENTAS ---
    elif choice == "📧 Gestión de Cuentas":
        st.header("📧 Configuración de Cuentas Mail")
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.container(border=True):
                m = st.text_input("Nuevo Email")
                if st.button("➕ Agregar Cuenta", use_container_width=True):
                    supabase.table("cuentas").insert({"mail": m}).execute()
                    st.rerun()
        with c2:
            res = supabase.table("cuentas").select("*").execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data), use_container_width=True, hide_index=True)
                if st.session_state['rol'] == "Administrador":
                    id_c = st.number_input("ID Cuenta a borrar", min_value=0, step=1)
                    if st.button("🗑️ Borrar"):
                        supabase.table("cuentas").delete().eq("id", id_c).execute()
                        st.rerun()

    # --- 4. PLANES ---
    elif choice == "⚙️ Config. Planes":
        st.header("⚙️ Planes de Servicio")
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.container(border=True):
                p = st.text_input("Nombre del Plan")
                if st.button("➕ Crear Plan", use_container_width=True):
                    supabase.table("planes").insert({"nombre_plan": p}).execute()
                    st.rerun()
        with c2:
            res = supabase.table("planes").select("*").execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data), use_container_width=True, hide_index=True)
                if st.session_state['rol'] == "Administrador":
                    id_p = st.number_input("ID Plan a borrar", min_value=0, step=1)
                    if st.button("🗑️ Eliminar"):
                        supabase.table("planes").delete().eq("id", id_p).execute()
                        st.rerun()

    # --- 5. USUARIOS ---
    elif choice == "👥 Usuarios":
        st.header("👥 Gestión de Accesos")
        if st.session_state['rol'] == "Administrador":
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                u = c1.text_input("Usuario")
                p = c2.text_input("Clave")
                r = c3.selectbox("Rol", ["Operador", "Administrador"])
                if st.button("➕ Crear Nuevo Usuario", use_container_width=True):
                    supabase.table("usuarios").insert({"username": u.lower(), "password": p, "rol": r}).execute()
                    st.rerun()
            
            st.divider()
            res_u = supabase.table("usuarios").select("id, username, rol").execute()
            if res_u.data:
                st.dataframe(pd.DataFrame(res_u.data), use_container_width=True, hide_index=True)
                id_u = st.number_input("ID Usuario para borrar", min_value=0, step=1)
                if st.button("🗑️ Eliminar Usuario"):
                    supabase.table("usuarios").delete().eq("id", id_u).execute()
                    st.rerun()
