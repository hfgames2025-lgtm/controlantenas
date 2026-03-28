import streamlit as st
import pandas as pd
from supabase import create_client, Client
import io
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Sistema Antenas Hugo", layout="wide", page_icon="📡")

# Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'edit_client' not in st.session_state: st.session_state['edit_client'] = None

# --- LOGIN (Texto Directo para evitar errores de Hash) ---
if not st.session_state['logged_in']:
    st.title("📡 Gestión de Antenas - Acceso")
    u_ing = st.text_input("Usuario").lower().strip()
    p_ing = st.text_input("Contraseña", type='password').strip()
    
    if st.button("INGRESAR"):
        res = supabase.table("usuarios").select("*").eq("username", u_ing).execute()
        if res.data:
            if p_ing == res.data[0]['password']:
                st.session_state['logged_in'] = True
                st.session_state['username'] = u_ing
                st.session_state['rol'] = res.data[0]['rol']
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        else:
            st.error("El usuario no existe")

# --- SISTEMA ADENTRO ---
else:
    st.sidebar.title(f"👤 {st.session_state['username']}")
    menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes", "👥 Usuarios"]
    choice = st.sidebar.selectbox("Menú", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- 1. PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("Listado de Clientes")
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            
            st.metric("Total Clientes", len(df), f"${df['costo'].sum():,.2f} Mensuales")
            
            busq = st.text_input("🔍 Buscar por nombre, zona, serie...")
            if busq:
                df = df[df.apply(lambda r: r.astype(str).str.contains(busq, case=False).any(), axis=1)]
            
            st.dataframe(df.drop(columns=['cuentas', 'cuenta_id']), use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Bajar Excel", output.getvalue(), "clientes.xlsx")

            st.write("---")
            col_e, col_b = st.columns(2)
            with col_e:
                id_edit = st.number_input("ID para EDITAR", min_value=0, step=1)
                if st.button("Cargar Datos"):
                    st.session_state['edit_client'] = next((i for i in res.data if i['id'] == id_edit), None)
                    if st.session_state['edit_client']: st.success("Cargado. Ve a Registrar/Editar")
            
            if st.session_state['rol'] == "Administrador":
                with col_b:
                    id_del = st.number_input("ID para BORRAR CLIENTE", min_value=0, step=1)
                    if st.button("❌ Eliminar Cliente"):
                        supabase.table("clientes").delete().eq("id", id_del).execute()
                        st.rerun()

    # --- 2. REGISTRAR / EDITAR ---
    elif choice == "📝 Registrar/Editar":
        edit = st.session_state['edit_client']
        st.header("🛠️ Editar" if edit else "🆕 Nuevo Registro")
        res_ctas = supabase.table("cuentas").select("*").execute()
        res_plns = supabase.table("planes").select("*").execute()

        if not res_ctas.data or not res_plns.data:
            st.warning("⚠️ Cargá Cuentas y Planes antes de seguir.")
        else:
            with st.form("form_registro"):
                c1, c2 = st.columns(2)
                nombre = c1.text_input("Nombre", value=edit['nombre'] if edit else "")
                zona = c1.text_input("Zona", value=edit['zona'] if edit else "")
                costo = c2.number_input("Costo", value=float(edit['costo']) if edit else 0.0)
                s_ant = c2.text_input("Serie Antena", value=edit['serie_antena'] if edit else "")
                s_rou = c2.text_input("Serie Router", value=edit['serie_router'] if edit else "")
                plan = st.selectbox("Plan", [p['nombre_plan'] for p in res_plns.data])
                map_c = {c['mail']: c['id'] for c in res_ctas.data}
                cta = st.selectbox("Cuenta Mail", list(map_c.keys()))

                if st.form_submit_button("GUARDAR DATOS"):
                    datos = {"nombre": nombre, "zona": zona, "plan": plan, "costo": costo, "serie_antena": s_ant, "serie_router": s_rou, "cuenta_id": map_c[cta], "fecha_inst": str(datetime.now().date())}
                    if edit:
                        supabase.table("clientes").update(datos).eq("id", edit['id']).execute()
                        st.session_state['edit_client'] = None
                    else:
                        supabase.table("clientes").insert(datos).execute()
                    st.success("¡Guardado!")
                    st.rerun()

    # --- 3. CUENTAS (Con Borrado) ---
    elif choice == "📧 Cuentas":
        st.header("Gestión de Cuentas Mail")
        with st.form("nueva_cuenta"):
            m = st.text_input("Nuevo Mail")
            if st.form_submit_button("Guardar"):
                supabase.table("cuentas").insert({"mail": m}).execute()
                st.rerun()
        
        res = supabase.table("cuentas").select("*").execute()
        if res.data:
            df_c = pd.DataFrame(res.data)
            st.table(df_c)
            if st.session_state['rol'] == "Administrador":
                id_c_del = st.number_input("ID de Cuenta para borrar", min_value=0, step=1)
                if st.button("❌ Borrar Cuenta"):
                    supabase.table("cuentas").delete().eq("id", id_c_del).execute()
                    st.rerun()

    # --- 4. PLANES (Con Borrado) ---
    elif choice == "⚙️ Planes":
        st.header("Gestión de Planes")
        with st.form("nuevo_plan"):
            p = st.text_input("Nombre del Plan")
            if st.form_submit_button("Crear"):
                supabase.table("planes").insert({"nombre_plan": p}).execute()
                st.rerun()
        
        res = supabase.table("planes").select("*").execute()
        if res.data:
            df_p = pd.DataFrame(res.data)
            st.table(df_p)
            if st.session_state['rol'] == "Administrador":
                id_p_del = st.number_input("ID de Plan para borrar", min_value=0, step=1)
                if st.button("❌ Borrar Plan"):
                    supabase.table("planes").delete().eq("id", id_p_del).execute()
                    st.rerun()

    # --- 5. USUARIOS (Crear y Borrar) ---
    elif choice == "👥 Usuarios":
        st.header("Gestión de Usuarios")
        if st.session_state['rol'] == "Administrador":
            with st.form("n_user"):
                new_u = st.text_input("Usuario")
                new_p = st.text_input("Contraseña")
                new_r = st.selectbox("Rol", ["Operador", "Administrador"])
                if st.form_submit_button("Crear Usuario"):
                    supabase.table("usuarios").insert({"username": new_u.lower(), "password": new_p, "rol": new_r}).execute()
                    st.success("Usuario creado.")
                    st.rerun()
            
            st.write("---")
            res_u = supabase.table("usuarios").select("id, username, rol").execute()
            if res_u.data:
                st.table(pd.DataFrame(res_u.data))
                id_u_del = st.number_input("ID de Usuario para borrar", min_value=0, step=1)
                if st.button("❌ Borrar Usuario"):
                    supabase.table("usuarios").delete().eq("id", id_u_del).execute()
                    st.rerun()
        else:
            st.error("No tenés permisos de administrador.")
