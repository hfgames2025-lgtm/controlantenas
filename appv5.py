import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
import io

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Gestión de Antenas Pro", layout="wide", page_icon="📡")

# 2. FUNCIONES DE BASE DE DATOS Y SEGURIDAD
def get_connection():
    return sqlite3.connect('control_antenas.db', check_same_thread=False)

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

conn = get_connection()
c = conn.cursor()

# 3. CREACIÓN DE TABLAS (Actualizada con Series de Equipos)
c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, rol TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS cuentas 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, mail TEXT UNIQUE)''')
c.execute('''CREATE TABLE IF NOT EXISTS planes 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_plan TEXT UNIQUE)''')

# Agregamos los campos de serie si no existen (Migración básica)
try:
    c.execute('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, zona TEXT, 
                  plan TEXT, costo REAL, fecha_inst TEXT, serie_antena TEXT, 
                  serie_router TEXT, cuenta_id INTEGER,
                  FOREIGN KEY(cuenta_id) REFERENCES cuentas(id))''')
except:
    pass

# Usuario admin por defecto
c.execute("SELECT * FROM usuarios WHERE username = 'admin'")
if not c.fetchone():
    c.execute("INSERT INTO usuarios (username, password, rol) VALUES (?,?,?)", 
              ('admin', make_hashes('admin123'), 'Administrador'))
conn.commit()

# --- LÓGICA DE SESIÓN ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- PANTALLA DE LOGIN ---
if not st.session_state['logged_in']:
    st.title("🔐 Acceso al Sistema de Antenas")
    user = st.text_input("Usuario")
    passwd = st.text_input("Contraseña", type='password')
    if st.button("Ingresar"):
        c.execute("SELECT password, rol FROM usuarios WHERE username = ?", (user,))
        data = c.fetchone()
        if data and check_hashes(passwd, data[0]):
            st.session_state['logged_in'] = True
            st.session_state['username'] = user
            st.session_state['rol'] = data[1]
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")
else:
    # --- INTERFAZ PRINCIPAL ---
    st.sidebar.title(f"Hola, {st.session_state['username']}")
    menu = ["📊 Panel General", "📝 Registrar Cliente", "📧 Gestionar Cuentas", "⚙️ Configurar Planes"]
    if st.session_state['rol'] == "Administrador":
        menu.append("👥 Gestionar Usuarios")
    
    choice = st.sidebar.selectbox("Ir a:", menu)
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- SECCIÓN: PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("Listado Global de Instalaciones")
        
        query = '''
            SELECT cl.id as ID, cl.nombre as Cliente, cl.zona as Ubicación, cl.plan as Plan, 
                   cl.costo as 'Costo Mens.', cl.fecha_inst as 'Fecha Inst.', 
                   cl.serie_antena as 'Serie Antena', cl.serie_router as 'Serie Router',
                   cu.mail as 'Cuenta Mail'
            FROM clientes cl JOIN cuentas cu ON cl.cuenta_id = cu.id
        '''
        df = pd.read_sql(query, conn)
        
        if not df.empty:
            col_met1, col_met2 = st.columns(2)
            with col_met1:
                st.metric("Clientes Totales", len(df))
            with col_met2:
                st.metric("Recaudación Mensual", f"${df['Costo Mens.'].sum():,.2f}")

            # Botón Exportar
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Clientes')
            
            st.download_button(
                label="📥 Descargar Listado en Excel",
                data=output.getvalue(),
                file_name=f"clientes_antenas_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            busqueda = st.text_input("🔍 Filtrar por nombre, zona o series")
            if busqueda:
                df = df[df.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)]
            
            st.dataframe(df, use_container_width=True)

            if st.session_state['rol'] == "Administrador":
                with st.expander("⚠️ Zona de Peligro: Eliminar Registro"):
                    id_borrar = st.number_input("ID del cliente a borrar", min_value=0, step=1)
                    if st.button("Confirmar Borrado"):
                        c.execute("DELETE FROM clientes WHERE id = ?", (id_borrar,))
                        conn.commit()
                        st.success("Cliente eliminado.")
                        st.rerun()
        else:
            st.info("Todavía no hay datos cargados.")

    # --- SECCIÓN: REGISTRAR CLIENTE (Con campos de Series) ---
    elif choice == "📝 Registrar Cliente":
        st.header("Nueva Instalación")
        cuentas_dis = pd.read_sql("SELECT c.id, c.mail, COUNT(cl.id) as ocupados FROM cuentas c LEFT JOIN clientes cl ON c.id = cl.cuenta_id GROUP BY c.id HAVING ocupados < 10", conn)
        planes_db = pd.read_sql("SELECT nombre_plan FROM planes", conn)

        if cuentas_dis.empty or planes_db.empty:
            st.warning("Faltan cuentas disponibles o planes configurados.")
        else:
            with st.form("reg"):
                c1, c2 = st.columns(2)
                with c1:
                    nombre = st.text_input("Nombre del Cliente")
                    zona = st.text_input("Zona / Paraje")
                    fecha = st.date_input("Fecha de Instalación", datetime.now())
                    plan = st.selectbox("Plan Elegido", planes_db['nombre_plan'].tolist())
                
                with c2:
                    s_antena = st.text_input("Nro de Serie Antena")
                    s_router = st.text_input("Nro de Serie Router (opcional)")
                    costo = st.number_input("Costo Mensual", min_value=0.0, step=100.0)
                    cta = st.selectbox("Asignar a Cuenta Mail", cuentas_dis['mail'].tolist())
                
                if st.form_submit_button("Guardar Instalación"):
                    if nombre and zona and s_antena:
                        id_c = int(cuentas_dis[cuentas_dis['mail'] == cta]['id'].values[0])
                        c.execute('''INSERT INTO clientes 
                                     (nombre, zona, plan, costo, fecha_inst, serie_antena, serie_router, cuenta_id) 
                                     VALUES (?,?,?,?,?,?,?,?)''', 
                                  (nombre, zona, plan, costo, str(fecha), s_antena, s_router, id_c))
                        conn.commit()
                        st.success("¡Datos guardados con éxito!")
                        st.rerun()
                    else:
                        st.error("El nombre, la zona y la serie de antena son obligatorios.")

    # --- GESTIONAR CUENTAS ---
    elif choice == "📧 Gestionar Cuentas":
        st.header("Cuentas")
        m = st.text_input("Nuevo Mail")
        if st.button("Agregar"):
            try:
                c.execute("INSERT INTO cuentas (mail) VALUES (?)", (m,))
                conn.commit()
                st.rerun()
            except: st.error("Error")
        st.table(pd.read_sql("SELECT c.mail as 'Cuenta', COUNT(cl.id) as 'Ocupados' FROM cuentas c LEFT JOIN clientes cl ON c.id = cl.cuenta_id GROUP BY c.id", conn))

    # --- CONFIGURAR PLANES ---
    elif choice == "⚙️ Configurar Planes":
        st.header("Planes")
        p = st.text_input("Nuevo Plan")
        if st.button("Añadir"):
            c.execute("INSERT INTO planes (nombre_plan) VALUES (?)", (p,))
            conn.commit()
            st.rerun()
        st.write(pd.read_sql("SELECT nombre_plan FROM planes", conn))

    # --- GESTIONAR USUARIOS ---
    elif choice == "👥 Gestionar Usuarios":
        st.header("Usuarios")
        with st.form("u"):
            un = st.text_input("Usuario")
            pw = st.text_input("Clave", type='password')
            rl = st.selectbox("Rol", ["Operador", "Administrador"])
            if st.form_submit_button("Crear"):
                try:
                    c.execute("INSERT INTO usuarios (username, password, rol) VALUES (?,?,?)", (un, make_hashes(pw), rl))
                    conn.commit()
                    st.success("Creado")
                except: st.error("Ya existe")
        st.write(pd.read_sql("SELECT username, rol FROM usuarios", conn))
