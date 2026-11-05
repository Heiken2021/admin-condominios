import os, hmac, hashlib, secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pandas as pd
import streamlit as st
from db import execute, fetch_all, fetch_one, init_schema

st.set_page_config(page_title="Condominio PostgreSQL", page_icon="🏢", layout="wide")
init_schema()

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 250000).hex()
    return salt, digest

def verify_password(password, salt, digest):
    return hmac.compare_digest(hash_password(password, salt)[1], digest)

def audit(action, detail=""):
    u=st.session_state.get("user", {})
    execute("INSERT INTO auditoria(usuario_id,username,accion,detalle) VALUES(%s,%s,%s,%s)",
            (u.get("id"),u.get("username","sistema"),action,detail))

def bootstrap_admin():
    if fetch_one("SELECT id FROM usuarios LIMIT 1"): return
    try: password=st.secrets["ADMIN_INITIAL_PASSWORD"]
    except Exception: password=os.getenv("ADMIN_INITIAL_PASSWORD")
    if not password: return
    salt,digest=hash_password(password)
    execute("INSERT INTO usuarios(username,nombre,rol,salt,password_hash) VALUES(%s,%s,'admin',%s,%s) ON CONFLICT(username) DO NOTHING",
            ("admin","Administrador",salt,digest))
bootstrap_admin()

def money(v): return f"${Decimal(v or 0):,.2f}"
def frame(sql,params=()): return pd.DataFrame(fetch_all(sql,params))
def units(scoped=False):
    user=st.session_state.get("user",{})
    if scoped and user.get("rol")!="admin" and user.get("unidad_id"):
        return frame("SELECT * FROM unidades WHERE activo=TRUE AND id=%s ORDER BY unidad",(user["unidad_id"],))
    return frame("SELECT * FROM unidades WHERE activo=TRUE ORDER BY unidad")

def login():
    st.title("🏢 Administración de Condominio")
    with st.form("login"):
        username=st.text_input("Usuario"); password=st.text_input("Contraseña",type="password")
        if st.form_submit_button("Entrar",type="primary"):
            row=fetch_one("SELECT * FROM usuarios WHERE username=%s AND activo=TRUE",(username,))
            if row and verify_password(password,row["salt"],row["password_hash"]):
                st.session_state.user=dict(row); audit("LOGIN"); st.rerun()
            st.error("Credenciales incorrectas")
    with st.expander("Restablecer contraseña con token"):
        with st.form("reset"):
            u=st.text_input("Usuario",key="reset_u"); token=st.text_input("Token"); new=st.text_input("Nueva contraseña",type="password")
            if st.form_submit_button("Cambiar contraseña"):
                r=fetch_one("SELECT * FROM usuarios WHERE username=%s AND reset_expira>NOW()",(u,))
                token_hash=hashlib.sha256(token.encode()).hexdigest()
                if r and r["reset_token_hash"] and hmac.compare_digest(token_hash,r["reset_token_hash"]) and len(new)>=10:
                    s,h=hash_password(new); execute("UPDATE usuarios SET salt=%s,password_hash=%s,reset_token_hash=NULL,reset_expira=NULL WHERE id=%s",(s,h,r["id"])); st.success("Contraseña actualizada")
                else: st.error("Token inválido, vencido o contraseña insuficiente")
if "user" not in st.session_state: login(); st.stop()

user=st.session_state.user; admin=user["rol"]=="admin"
st.sidebar.write(f"**{user['nombre']}**\n\nRol: {user['rol']}")
if st.sidebar.button("Cerrar sesión"): audit("LOGOUT"); del st.session_state.user; st.rerun()
pages=["Dashboard","Estados de cuenta"]+(["Unidades","Cargos","Pagos","Gastos","Usuarios","Auditoría"] if admin else [])
page=st.sidebar.radio("Navegación",pages)
st.title("🏢 Administración de Condominio")

if page=="Dashboard":
    scope=""; params=()
    if not admin and user.get("unidad_id"): scope=" WHERE unidad_id=%s"; params=(user["unidad_id"],)
    cargos=fetch_one("SELECT COALESCE(SUM(monto+recargo),0) total FROM cargos"+scope,params)["total"]
    pagos=fetch_one("SELECT COALESCE(SUM(monto),0) total FROM pagos"+scope,params)["total"]
    gastos=fetch_one("SELECT COALESCE(SUM(monto),0) total FROM gastos")["total"] if admin else 0
    data=[("Cargos",cargos),("Cobrado",pagos),("Pendiente",max(cargos-pagos,0))]+([("Gastos",gastos),("Saldo",pagos-gastos)] if admin else [])
    for col,(label,value) in zip(st.columns(len(data)),data): col.metric(label,money(value))
    u=units(True); rows=[]
    for _,r in u.iterrows():
        c=fetch_one("SELECT COALESCE(SUM(monto+recargo),0) x FROM cargos WHERE unidad_id=%s",(int(r.id),))["x"]
        p=fetch_one("SELECT COALESCE(SUM(monto),0) x FROM pagos WHERE unidad_id=%s",(int(r.id),))["x"]
        d=max(c-p,0); rows.append(["🟢 Al corriente" if d==0 else "🔴 Pendiente",r.unidad,r.inquilino or r.propietario,c,p,d])
    st.dataframe(pd.DataFrame(rows,columns=["Estado","Unidad","Responsable","Cargos","Pagos","Adeudo"]),hide_index=True,use_container_width=True)

elif page=="Unidades":
    with st.form("unidad",clear_on_submit=True):
        a,b,c=st.columns(3); unidad=a.text_input("Unidad"); propietario=b.text_input("Propietario"); inquilino=c.text_input("Inquilino")
        a,b,c=st.columns(3); email=a.text_input("Email"); cuota=b.number_input("Cuota base",0.0); recargo=c.number_input("Recargo %",0.0,100.0)
        if st.form_submit_button("Guardar",type="primary"):
            execute("INSERT INTO unidades(unidad,propietario,inquilino,email,cuota_base,recargo_pct) VALUES(%s,%s,%s,%s,%s,%s)",(unidad,propietario,inquilino,email,cuota,recargo)); audit("CREAR_UNIDAD",unidad); st.rerun()
    st.dataframe(frame("SELECT * FROM unidades ORDER BY unidad"),hide_index=True,use_container_width=True)

elif page=="Cargos":
    u=units()
    with st.form("cargo"):
        target=st.selectbox("Aplicar a",["Todas"]+u.unidad.tolist()); periodo=st.text_input("Periodo",date.today().strftime("%Y-%m")); concepto=st.text_input("Concepto","Cuota de mantenimiento"); venc=st.date_input("Vencimiento")
        if st.form_submit_button("Generar"):
            rows=u if target=="Todas" else u[u.unidad==target]
            for _,r in rows.iterrows():
                execute("INSERT INTO cargos(unidad_id,periodo,concepto,monto,vencimiento) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(unidad_id,periodo,concepto) DO NOTHING",(int(r.id),periodo,concepto,r.cuota_base,venc))
            audit("GENERAR_CARGOS",f"{target} {periodo}"); st.rerun()
    if st.button("Aplicar recargos vencidos"):
        execute("""UPDATE cargos c SET recargo=ROUND(c.monto*u.recargo_pct/100,2) FROM unidades u WHERE u.id=c.unidad_id AND c.vencimiento<CURRENT_DATE AND c.recargo=0"""); audit("APLICAR_RECARGOS"); st.rerun()
    st.dataframe(frame("SELECT c.*,u.unidad,c.monto+c.recargo total FROM cargos c JOIN unidades u ON u.id=c.unidad_id ORDER BY periodo DESC,unidad"),hide_index=True,use_container_width=True)

elif page=="Pagos":
    u=units()
    with st.form("pago",clear_on_submit=True):
        a,b,c=st.columns(3); unidad=a.selectbox("Unidad",u.unidad); periodo=b.text_input("Periodo",date.today().strftime("%Y-%m")); fecha=c.date_input("Fecha")
        a,b,c=st.columns(3); monto=a.number_input("Monto",0.01); metodo=b.selectbox("Método",["Transferencia","Efectivo","Depósito","Tarjeta","Otro"]); ref=c.text_input("Referencia"); notas=st.text_area("Notas"); url=st.text_input("URL segura del comprobante")
        if st.form_submit_button("Registrar"):
            uid=int(u[u.unidad==unidad].iloc[0].id); execute("INSERT INTO pagos(unidad_id,periodo,fecha,monto,metodo,referencia,notas,comprobante_url,creado_por) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(uid,periodo,fecha,monto,metodo,ref,notas,url or None,user["id"])); audit("REGISTRAR_PAGO",f"{unidad} {money(monto)}"); st.rerun()
    st.dataframe(frame("SELECT p.*,u.unidad FROM pagos p JOIN unidades u ON u.id=p.unidad_id ORDER BY fecha DESC,p.id DESC"),hide_index=True,use_container_width=True)

elif page=="Gastos":
    with st.form("gasto",clear_on_submit=True):
        a,b,c=st.columns(3); fecha=a.date_input("Fecha"); categoria=b.text_input("Categoría"); concepto=c.text_input("Concepto")
        a,b,c=st.columns(3); proveedor=a.text_input("Proveedor"); monto=b.number_input("Monto",0.01); ref=c.text_input("Referencia"); notas=st.text_area("Notas"); url=st.text_input("URL segura del comprobante")
        if st.form_submit_button("Registrar"):
            execute("INSERT INTO gastos(fecha,categoria,concepto,proveedor,monto,referencia,notas,comprobante_url,creado_por) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(fecha,categoria,concepto,proveedor,monto,ref,notas,url or None,user["id"])); audit("REGISTRAR_GASTO",f"{concepto} {money(monto)}"); st.rerun()
    st.dataframe(frame("SELECT * FROM gastos ORDER BY fecha DESC,id DESC"),hide_index=True,use_container_width=True)

elif page=="Estados de cuenta":
    u=units(True); unidad=st.selectbox("Unidad",u.unidad); uid=int(u[u.unidad==unidad].iloc[0].id); events=[]
    for r in fetch_all("SELECT periodo,concepto,monto+recargo monto FROM cargos WHERE unidad_id=%s",(uid,)): events.append([r["periodo"]+"-01","Cargo",r["concepto"],r["monto"],0])
    for r in fetch_all("SELECT fecha,referencia,monto FROM pagos WHERE unidad_id=%s",(uid,)): events.append([str(r["fecha"]),"Pago",r["referencia"] or "Pago",0,r["monto"]])
    d=pd.DataFrame(events,columns=["Fecha","Tipo","Concepto","Cargo","Pago"]).sort_values("Fecha") if events else pd.DataFrame(columns=["Fecha","Tipo","Concepto","Cargo","Pago"])
    d["Balance"]=(d.Cargo-d.Pago).cumsum() if len(d) else []; st.dataframe(d,hide_index=True,use_container_width=True); st.download_button("Descargar CSV",d.to_csv(index=False).encode("utf-8-sig"),f"estado_{unidad}.csv")

elif page=="Usuarios":
    u=units()
    with st.form("usuario",clear_on_submit=True):
        a,b,c=st.columns(3); username=a.text_input("Usuario"); nombre=b.text_input("Nombre"); email=c.text_input("Email")
        a,b,c=st.columns(3); rol=a.selectbox("Rol",["residente","admin"]); unidad=b.selectbox("Unidad",["Sin unidad"]+u.unidad.tolist()); password=c.text_input("Contraseña inicial",type="password")
        if st.form_submit_button("Crear usuario"):
            uid=None if unidad=="Sin unidad" else int(u[u.unidad==unidad].iloc[0].id); s,h=hash_password(password); execute("INSERT INTO usuarios(username,nombre,email,rol,unidad_id,salt,password_hash) VALUES(%s,%s,%s,%s,%s,%s,%s)",(username,nombre,email,rol,uid,s,h)); audit("CREAR_USUARIO",username); st.rerun()
    users=frame("SELECT id,username,nombre,email,rol,unidad_id,activo,creado_en FROM usuarios ORDER BY id"); st.dataframe(users,hide_index=True,use_container_width=True)
    target=st.selectbox("Generar token para",users.username)
    if st.button("Generar token de recuperación"):
        token=secrets.token_urlsafe(24); token_hash=hashlib.sha256(token.encode()).hexdigest(); execute("UPDATE usuarios SET reset_token_hash=%s,reset_expira=%s WHERE username=%s",(token_hash,datetime.now(timezone.utc)+timedelta(minutes=30),target)); audit("TOKEN_RESET",target); st.code(token); st.warning("El token se muestra una sola vez y vence en 30 minutos.")

else:
    st.dataframe(frame("SELECT * FROM auditoria ORDER BY fecha DESC LIMIT 1000"),hide_index=True,use_container_width=True)
