import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Gestión de Antenas Pro", layout="wide", page_icon="📡")

def get_connection():
    return sqlite3.connect('control_antenas.db', check_same_thread=False)

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

conn = get_connection()
c = conn.cursor()

# 2. TABLAS
c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, rol TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS cuentas (id INTEGER PRIMARY KEY AUTOINCREMENT, mail TEXT UNIQUE)''')
c.execute('''CREATE TABLE IF NOT EXISTS planes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_plan TEXT UNIQUE)''')
c.execute('''CREATE TABLE IF NOT EXISTS clientes 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, zona TEXT, 
              plan TEXT, costo REAL, fecha_inst TEXT, serie_antena TEXT, 
              serie_router TEXT, cuenta_id INTEGER,
              FOREIGN KEY(cuenta_id) REFERENCES cuentas(id))''')

# Admin por defecto
c.execute("SELECT * FROM usuarios WHERE username = 'admin'")
if not c.fetchone():
    c.execute("INSERT INTO usuarios (username, password, rol) VALUES (?,?,?)", ('admin', make_hashes('admin123'), 'Administrador'))
conn.commit()

# 3. LÓGICA DE SESIÓN Y EDICIÓN
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'edit_client' not in st.session_state: st.session_state['edit_client'] = None

if not st.session_state['logged_in']:
    st.title("🔐 Acceso al Sistema")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type='password')
    if st.button("Ingresar"):
        c.execute("SELECT password, rol FROM usuarios WHERE username = ?", (u,))
        d = c.fetchone()
        if d and check_hashes(p, d[0]):
            st.session_state['logged_in'], st.session_state['username'], st.session_state['rol'] = True, u, d[1]
            st.rerun()
        else: st.error("Error de acceso")
else:
    st.sidebar.title(f"Usuario: {st.session_state['username']}")
    menu = ["📊 Panel General", "📝 Registrar/Editar Cliente", "📧 Gestionar Cuentas", "⚙️ Configurar Planes"]
    if st.session_state['rol'] == "Administrador": menu.append("👥 Gestionar Usuarios")
    
    choice = st.sidebar.selectbox("Ir a:", menu)
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- PANEL GENERAL ---
    if choice == "📊 Panel General":
        st.header("Listado de Instalaciones")
        df = pd.read_sql('''SELECT cl.id as ID, cl.nombre as Cliente, cl.zona as Ubicación, cl.plan as Plan, 
                            cl.costo as 'Costo Mens.', cl.fecha_inst as 'Fecha Inst.', 
                            cl.serie_antena as 'Serie Antena', cl.serie_router as 'Serie Router',
                            cu.mail as 'Cuenta Mail' FROM clientes cl JOIN cuentas cu ON cl.cuenta_id = cu.id''', conn)
        
        if not df.empty:
            st.metric("Total Clientes", len(df), f"${df['Costo Mens.'].sum():,.2f} Recaudación")
            
            # Botón Excel
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel", out.getvalue(), f"clientes_{datetime.now().strftime('%Y%m%d')}.xlsx")

            busq = st.text_input("🔍 Buscar...")
            if busq: df = df[df.apply(lambda r: r.astype(str).str.contains(busq, case=False).any(), axis=1)]
            
            st.dataframe(df, use_container_width=True)

            # ACCIONES DE EDICIÓN
            st.subheader("🛠️ Gestionar Registros")
            col_ed, col_del = st.columns(2)
            with col_ed:
                id_e = st.number_input("ID para EDITAR", min_value=0, step=1)
                if st.button("Cargar datos para modificar"):
                    cliente_data = pd.read_sql("SELECT * FROM clientes WHERE id = ?", conn, params=(id_e,))
                    if not cliente_data.empty:
                        st.session_state['edit_client'] = cliente_data.iloc[0].to_dict()
                        st.success(f"Datos de {st.session_state['edit_client']['nombre']} cargados. Ve a la pestaña 'Registrar/Editar Cliente'.")
                    else: st.error("ID no encontrado")

            if st.session_state['rol'] == "Administrador":
                with col_del:
                    id_b = st.number_input("ID para ELIMINAR", min_value=0, step=1)
                    if st.button("❌ Confirmar Borrado"):
                        c.execute("DELETE FROM clientes WHERE id = ?", (id_b,))
                        conn.commit()
                        st.rerun()
        else: st.info("No hay datos.")

    # --- REGISTRAR / EDITAR CLIENTE ---
    elif choice == "📝 Registrar/Editar Cliente":
        is_edit = st.session_state['edit_client'] is not None
        st.header("✏️ Editar Cliente" if is_edit else "📝 Nueva Instalación")
        
        datos = st.session_state['edit_client'] if is_edit else {}
        
        cuentas_dis = pd.read_sql("SELECT id, mail FROM cuentas", conn) # Traemos todas para permitir cambios de cuenta
        planes_db = pd.read_sql("SELECT nombre_plan FROM planes", conn)

        if cuentas_dis.empty or planes_db.empty:
            st.warning("Configurá cuentas y planes primero.")
        else:
            with st.form("form_registro"):
                c1, c2 = st.columns(2)
                with c1:
                    nombre = st.text_input("Nombre", value=datos.get('nombre', ""))
                    zona = st.text_input("Zona", value=datos.get('zona', ""))
                    # Manejo de fecha para edición
                    fecha_def = datetime.strptime(datos.get('fecha_inst'), '%Y-%m-%d') if is_edit else datetime.now()
                    fecha = st.date_input("Fecha", fecha_def)
                with c2:
                    s_ant = st.text_input("Serie Antena", value=datos.get('serie_antena', ""))
                    s_rout = st.text_input("Serie Router", value=datos.get('serie_router', ""))
                    costo = st.number_input("Costo", min_value=0.0, value=float(datos.get('costo', 0.0)))
                    
                col_plan, col_cta = st.columns(2)
                plan_idx = planes_db['nombre_plan'].tolist().index(datos['plan']) if is_edit and datos['plan'] in planes_db['nombre_plan'].tolist() else 0
                plan = col_plan.selectbox("Plan", planes_db['nombre_plan'].tolist(), index=plan_idx)
                
                cta_list = cuentas_dis['mail'].tolist()
                # Buscar el mail de la cuenta actual para el selector
                try:
                    curr_mail = pd.read_sql("SELECT mail FROM cuentas WHERE id = ?", conn, params=(datos.get('cuenta_id', 0),)).iloc[0][0]
                    cta_idx = cta_list.index(curr_mail)
                except: cta_idx = 0
                cta = col_cta.selectbox("Cuenta Mail", cta_list, index=cta_idx)

                if st.form_submit_button("Guardar Cambios" if is_edit else "Registrar"):
                    id_cta = int(cuentas_dis[cuentas_dis['mail'] == cta]['id'].values[0])
                    if is_edit:
                        c.execute('''UPDATE clientes SET nombre=?, zona=?, plan=?, costo=?, fecha_inst=?, 
                                     serie_antena=?, serie_router=?, cuenta_id=? WHERE id=?''',
                                  (nombre, zona, plan, costo, str(fecha), s_ant, s_rout, id_cta, datos['id']))
                        st.session_state['edit_client'] = None # Limpiamos modo edición
                    else:
                        c.execute('''INSERT INTO clientes (nombre, zona, plan, costo, fecha_inst, serie_antena, serie_router, cuenta_id) 
                                     VALUES (?,?,?,?,?,?,?,?)''', (nombre, zona, plan, costo, str(fecha), s_ant, s_rout, id_cta))
                    conn.commit()
                    st.success("¡Operación exitosa!")
                    st.rerun()
            
            if is_edit:
                if st.button("Cancelar Edición"):
                    st.session_state['edit_client'] = None
                    st.rerun()

    # --- CUENTAS, PLANES Y USUARIOS (SE MANTIENEN IGUAL) ---
    elif choice == "📧 Gestionar Cuentas":
        st.header("Cuentas")
        m = st.text_input("Nuevo Mail")
        if st.button("Agregar"):
            c.execute("INSERT INTO cuentas (mail) VALUES (?)", (m,)); conn.commit(); st.rerun()
        st.table(pd.read_sql("SELECT c.mail as 'Cuenta', COUNT(cl.id) as 'Ocupados' FROM cuentas c LEFT JOIN clientes cl ON c.id = cl.cuenta_id GROUP BY c.id", conn))

    elif choice == "⚙️ Configurar Planes":
        st.header("Planes")
        p = st.text_input("Nuevo Plan")
        if st.button("Añadir"):
            c.execute("INSERT INTO planes (nombre_plan) VALUES (?)", (p,)); conn.commit(); st.rerun()
        st.write(pd.read_sql("SELECT nombre_plan FROM planes", conn))

    elif choice == "👥 Gestionar Usuarios":
        st.header("Usuarios")
        with st.form("u"):
            un, pw, rl = st.text_input("Usuario"), st.text_input("Clave", type='password'), st.selectbox("Rol", ["Operador", "Administrador"])
            if st.form_submit_button("Crear"):
                try:
                    c.execute("INSERT INTO usuarios (username, password, rol) VALUES (?,?,?)", (un, make_hashes(pw), rl)); conn.commit(); st.success("Creado")
                except: st.error("Error")
        st.write(pd.read_sql("SELECT username, rol FROM usuarios", conn))
