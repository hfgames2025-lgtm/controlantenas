import streamlit as st
import pandas as pd
from supabase import create_client, Client
import hashlib
import io
from datetime import datetime

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Sistema Antenas Hugo - Cloud", layout="wide", page_icon="📡")

# Conexión usando tus Secrets de Streamlit
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Función para verificar la clave admin123
def verificar_clave(clave_ingresada, clave_db):
    hash_ingresado = hashlib.sha256(clave_ingresada.encode()).hexdigest()
    return hash_ingresado == clave_db

# Manejo de la sesión
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'edit_client' not in st.session_state:
    st.session_state['edit_client'] = None

# --- PANTALLA DE LOGIN ---
if not st.session_state['logged_in']:
    st.title("🔐 Acceso al Sistema")
    u_input = st.text_input("Usuario").lower().strip()
    p_input = st.text_input("Contraseña", type='password').strip()
    
    if st.button("INGRESAR"):
        res = supabase.table("usuarios").select("*").eq("username", u_input).execute()
        if res.data:
            if verificar_clave(p_input, res.data[0]['password']):
                st.session_state['logged_in'] = True
                st.session_state['username'] = u_input
                st.session_state['rol'] = res.data[0]['rol']
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        else:
            st.error("El usuario no existe")

# --- SISTEMA ADENTRO ---
else:
    st.sidebar.title(f"👤 {st.session_state['username']}")
    menu = ["📊 Panel General", "📝 Registrar/Editar", "📧 Cuentas", "⚙️ Planes"]
    if st.session_state['rol'] == "Administrador":
        menu.append("👥 Usuarios")
    
    choice = st.sidebar.selectbox("Menú", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- 1. PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("Listado de Clientes")
        # Traemos datos uniendo la tabla clientes con el mail de la tabla cuentas
        res = supabase.table("clientes").select("*, cuentas(mail)").execute()
        
        if res.data:
            df_raw = pd.DataFrame(res.data)
            df = df_raw.copy()
            # Formateamos el mail de la cuenta para que se vea bien
            df['Cuenta Mail'] = df['cuentas'].apply(lambda x: x['mail'] if x else "N/A")
            
            # Métricas arriba
            st.metric("Total Clientes", len(df), f"${df['costo'].sum():,.2f} / mes")
            
            # Buscador
            busq = st.text_input("🔍 Buscar por nombre, zona o serie...")
            if busq:
                df = df[df.apply(lambda r: r.astype(str).str.contains(busq, case=False).any(), axis=1)]
            
            # Mostramos la tabla (quitando columnas internas de Supabase)
            st.dataframe(df.drop(columns=['cuentas', 'cuenta_id']), use_container_width=True)

            # Botón para descargar Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", output.getvalue(), "listado_clientes.xlsx")

            st.write("---")
            # Acciones de edición y borrado
            col_e, col_b = st.columns(2)
            with col_e:
                st.subheader("Modificar")
                id_edit = st.number_input("ID del cliente a editar", min_value=0, step=1)
                if st.button("Cargar para editar"):
                    st.session_state['edit_client'] = next((i for i in res.data if i['id'] == id_edit), None)
                    if st.session_state['edit_client']:
                        st.success("Cargado. Pasá a la pestaña 'Registrar/Editar'")
            
            if st.session_state['rol'] == "Administrador":
                with col_b:
                    st.subheader("Borrar")
                    id_del = st.number_input("ID del cliente a borrar", min_value=0, step=1)
                    if st.button("Eliminar Permanente"):
                        supabase.table("clientes").delete().eq("id", id_del).execute()
                        st.rerun()
        else:
            st.info("No hay datos. Cargá primero Cuentas y Planes.")

    # --- 2. REGISTRAR / EDITAR ---
    elif choice == "📝 Registrar/Editar":
        edit = st.session_state['edit_client']
        st.header("🛠️ Editar Cliente" if edit else "🆕 Nuevo Registro")
        
        # Necesitamos las cuentas y planes disponibles
        res_ctas = supabase.table("cuentas").select("*").execute()
        res_plns = supabase.table("planes").select("*").execute()

        if not res_ctas.data or not res_plns.data:
            st.error("⚠️ Error: Debés crear al menos una CUENTA y un PLAN antes de registrar clientes.")
        else:
            with st.form("form_clientes"):
                c1, c2 = st.columns(2)
                nombre = c1.text_input("Nombre Completo", value=edit['nombre'] if edit else "")
                zona = c1.text_input("Zona / Dirección", value=edit['zona'] if edit else "")
                costo = c2.number_input("Costo Mensual", value=float(edit['costo']) if edit else 0.0)
                s_antena = c2.text_input("Serie Antena", value=edit['serie_antena'] if edit else "")
                s_router = c2.text_input("Serie Router", value=edit['serie_router'] if edit else "")
                
                plan = st.selectbox("Plan de Servicio", [p['nombre_plan'] for p in res_plns.data])
                
                # Mapeo de mail a ID para la base de datos
                mapa_cuentas = {c['mail']: c['id'] for c in res_ctas.data}
                cuenta_sel = st.selectbox("Asignar a Cuenta Mail", list(mapa_cuentas.keys()))

                if st.form_submit_button("GUARDAR EN LA NUBE"):
                    datos = {
                        "nombre": nombre, "zona": zona, "plan": plan, "costo": costo,
                        "serie_antena": s_antena, "serie_router": s_router,
                        "cuenta_id": mapa_cuentas[cuenta_sel], "fecha_inst": str(datetime.now().date())
                    }
                    if edit:
                        supabase.table("clientes").update(datos).eq("id", edit['id']).execute()
                        st.session_state['edit_client'] = None
                        st.success("¡Cliente actualizado!")
                    else:
                        supabase.table("clientes").insert(datos).execute()
                        st.success("¡Cliente guardado con éxito!")
                    st.rerun()

    # --- 3. GESTIÓN DE CUENTAS ---
    elif choice == "📧 Cuentas":
        st.header("Administrar Cuentas Mail")
        nuevo_mail = st.text_input("Nuevo Email")
        if st.button("Guardar Cuenta"):
            try:
                supabase.table("cuentas").insert({"mail": nuevo_mail}).execute()
                st.success("Cuenta creada.")
                st.rerun()
            except:
                st.error("El mail ya existe o hubo un error.")
        
        res = supabase.table("cuentas").select("*").execute()
        if res.data:
            st.table(pd.DataFrame(res.data))

    # --- 4. GESTIÓN DE PLANES ---
    elif choice == "⚙️ Planes":
        st.header("Administrar Planes")
        nuevo_p = st.text_input("Nombre del Plan (ej: 20 Mega Hogar)")
        if st.button("Crear Plan"):
            supabase.table("planes").insert({"nombre_plan": nuevo_p}).execute()
            st.success("Plan creado.")
            st.rerun()
        
        res = supabase.table("planes").select("*").execute()
        if res.data:
            st.table(pd.DataFrame(res.data))

    # --- 5. GESTIÓN DE USUARIOS (Solo Admin) ---
    elif choice == "👥 Usuarios":
        st.header("Usuarios del Sistema")
        with st.form("nuevo_usuario"):
            u = st.text_input("Nombre de Usuario")
            p = st.text_input("Contraseña", type='password')
            r = st.selectbox("Rol", ["Operador", "Administrador"])
            if st.form_submit_button("Crear Usuario"):
                hash_p = hashlib.sha256(p.encode()).hexdigest()
                supabase.table("usuarios").insert({"username": u.lower(), "password": hash_p, "rol": r}).execute()
                st.rerun()
