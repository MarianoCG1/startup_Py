import os
import asyncio
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import datetime

from app.database import Database
from app.auth import get_current_user, require_user, RoleChecker, create_access_token
from app.prediction import (
    get_dish_weekly_forecast,
    get_weekly_purchase_requirements,
    get_perishable_alerts,
    get_upcoming_holidays
)

app = FastAPI(title="DemandaRest - MVP")

# Asegurar directorios estáticos
os.makedirs("app/static/css", exist_ok=True)
os.makedirs("app/static/js", exist_ok=True)

# Escribir archivos estáticos plantilla por compatibilidad
with open("app/static/css/styles.css", "w") as f:
    f.write("/* Custom Stylesheet for DemandaRest */\n")
with open("app/static/js/dashboard.js", "w") as f:
    f.write("// Custom Client-side Utilities\n")

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configurar plantillas Jinja2
templates = Jinja2Templates(directory="app/templates")

# Inyectar el usuario actual en el contexto de todas las plantillas renderizadas por Jinja2
@app.middleware("http")
async def add_current_user_to_templates(request: Request, call_next):
    user = await get_current_user(request)
    request.state.user = user
    response = await call_next(request)
    return response

# Helper para renderizar plantillas con variables globales
def render_template(template_name: str, request: Request, context: dict = {}):
    # Inyectar datos de sesión comunes en el contexto
    context["request"] = request
    context["current_user"] = request.state.user
    return templates.TemplateResponse(request=request, name=template_name, context=context)

# =====================================================================
# RUTAS DE AUTENTICACIÓN Y ENRUTAMIENTO PRINCIPAL
# =====================================================================

@app.get("/")
async def root(request: Request):
    user = request.state.user
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    if user["role"] == "owner":
        return RedirectResponse(url="/dashboard/owner", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return RedirectResponse(url="/dashboard/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, error: Optional[str] = None):
    # Si ya tiene sesión activa, redirigir
    if request.state.user:
        return RedirectResponse(url="/")
    
    error_msg = None
    if error == "Unauthorized":
        error_msg = "Acceso no autorizado. Por favor inicie sesión con el rol correspondiente."
    elif error:
        error_msg = error
        
    return render_template("login.html", request, {"error": error_msg})

@app.post("/login")
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    user = Database.get_user_by_email(email)
    if not user or not Database.get_conn():
        # Fallback local o Supabase error
        return render_template("login.html", request, {"error": "Credenciales incorrectas o servidor no disponible."})
        
    # Verificar contraseña (en el MVP soporta la contraseña del SQLite local)
    from app.database import verify_password
    if not verify_password(password, user["password_hash"]):
        return render_template("login.html", request, {"error": "Correo o contraseña incorrectos."})

    # Generar JWT e iniciar sesión configurando la cookie
    access_token = create_access_token(data={"email": user["email"], "role": user["role"]})
    
    # Redirección en base al rol
    target_url = "/dashboard/owner" if user["role"] == "owner" else "/dashboard/admin"
    response = RedirectResponse(url=target_url, status_code=status.HTTP_303_SEE_OTHER)
    
    # Cookie expira en 7 días
    response.set_cookie(
        key="session_token",
        value=access_token,
        httponly=True,
        max_age=604800,
        expires=604800,
        samesite="lax"
    )
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    return response

# =====================================================================
# DASHBOARD DE DUEÑO (OWNER)
# =====================================================================

@app.get("/dashboard/owner", response_class=HTMLResponse)
async def owner_dashboard(
    request: Request,
    user: dict = Depends(RoleChecker(allowed_roles=["owner"]))
):
    # Obtener el total consolidado de kilos a comprar
    reqs = get_weekly_purchase_requirements()
    total_kilos = sum(r.total_kilos for r in reqs)
    
    # Feriados peruanos en los próximos 45 días
    holidays = get_upcoming_holidays(days_ahead=45)
    
    return render_template("owner.html", request, {
        "active_page": "owner_dashboard",
        "total_kilos": round(total_kilos, 1),
        "holidays": holidays
    })

# =====================================================================
# DASHBOARD DE ADMINISTRADOR (ADMIN)
# =====================================================================

@app.get("/dashboard/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: dict = Depends(RoleChecker(allowed_roles=["admin"]))
):
    location_id = user.get("location_id")
    if not location_id:
        raise HTTPException(status_code=400, detail="Administrador no tiene un local asignado.")
        
    # Obtener pronósticos de platos
    forecasts = get_dish_weekly_forecast(location_id)
    
    return render_template("admin.html", request, {
        "active_page": "admin_dashboard",
        "forecasts": forecasts
    })

@app.get("/perishables", response_class=HTMLResponse)
async def perishables_partial(
    request: Request,
    user: dict = Depends(require_user)
):
    """Retorna el fragmento HTML con las alertas de ingredientes perecederos."""
    location_id = user.get("location_id")
    # Para el dueño (owner) mostramos Santa Anita por defecto si visualiza esta sección
    if user["role"] == "owner":
        location_id = 1
        
    alerts = get_perishable_alerts(location_id)
    return render_template("partials/perishable_alerts.html", request, {"alerts": alerts})

@app.post("/sales")
async def record_sale_post(
    request: Request,
    dish_name: str = Form(...),
    quantity_sold: int = Form(...),
    shift: str = Form(...),
    sale_date: str = Form(...),
    user: dict = Depends(RoleChecker(allowed_roles=["admin"]))
):
    """Registra una venta e indica a HTMX que debe actualizar las alertas mediante cabecera HTTP."""
    location_id = user.get("location_id")
    
    # Registrar la venta en la base de datos
    success = Database.record_sale(
        location_id=location_id,
        sale_date=sale_date,
        shift=shift,
        dish_name=dish_name,
        quantity_sold=quantity_sold
    )
    
    # Crear la respuesta HTML parcial
    response = render_template("partials/sales_feedback.html", request, {
        "success": success,
        "dish_name": dish_name,
        "quantity": quantity_sold,
        "shift": shift,
        "error_message": "No se pudo registrar la venta en la base de datos." if not success else None
    })
    
    if success:
        # Añadir cabecera HX-Trigger para forzar al frontend a recargar el componente de alertas perecederas
        response.headers["HX-Trigger"] = "updatePerishables"
        
    return response

# =====================================================================
# REPORTE DE COMPRAS Y GENERACIÓN DE ÓRDENES
# =====================================================================

@app.get("/purchase-report", response_class=HTMLResponse)
async def purchase_report(
    request: Request,
    user: dict = Depends(require_user)
):
    requirements = get_weekly_purchase_requirements()
    return render_template("report.html", request, {
        "active_page": "purchase_report",
        "requirements": requirements
    })

@app.get("/purchase-report/generate", response_class=HTMLResponse)
async def generate_purchase_list(
    request: Request,
    user: dict = Depends(require_user)
):
    """Endpoint HTMX con retraso artificial para simular procesamiento y mostrar indicador de carga."""
    # Retraso simulado de 1.2 segundos para demostrar la carga animada
    await asyncio.sleep(1.2)
    
    # Filtrar insumos específicos del local de Santa Anita
    requirements = get_weekly_purchase_requirements()
    
    # Mapear a estructura simplificada de compras para Santa Anita
    purchase_items = []
    for req in requirements:
        if req.kilos_santa_anita > 0:
            # Clasificar
            category = "perishable" if req.ingredient_name in [
                "Pescado Fresco", "Tomate", "Cebolla Roja", "Limón Ácido", 
                "Choclo Desgranado", "Pechuga de Pollo", "Ají Amarillo", 
                "Pan Molde", "Mixtura de Mariscos", "Arvejas", "Corazón de Res"
            ] else "non-perishable"
            
            purchase_items.append({
                "name": req.ingredient_name,
                "quantity": req.kilos_santa_anita,
                "unit": req.unit,
                "category": category
            })
            
    return render_template("partials/purchase_list.html", request, {"items": purchase_items})

# =====================================================================
# API JSON DE GRÁFICOS (CHART.JS)
# =====================================================================

@app.get("/api/charts/demand")
async def chart_demand_data(user: dict = Depends(require_user)):
    """Retorna datos agregados de pronóstico en formato compatible con Chart.js."""
    platos = ["Lomo Saltado", "Ceviche Clásico", "Ají de Gallina", "Arroz con Mariscos", "Anticuchos de Corazón"]
    
    # Pronósticos para los 3 locales
    sa_forecasts = {f.dish_name: f.predicted_quantity for f in get_dish_weekly_forecast(1)}
    mf_forecasts = {f.dish_name: f.predicted_quantity for f in get_dish_weekly_forecast(2)}
    su_forecasts = {f.dish_name: f.predicted_quantity for f in get_dish_weekly_forecast(3)}
    
    # Estructura del dataset
    datasets = [
        {
            "label": "Santa Anita",
            "data": [sa_forecasts.get(p, 0) for p in platos],
            "backgroundColor": "rgba(20, 83, 45, 0.8)", # Greenwood 900
            "borderColor": "rgba(20, 83, 45, 1)",
            "borderWidth": 1.5,
            "borderRadius": 6
        },
        {
            "label": "Miraflores",
            "data": [mf_forecasts.get(p, 0) for p in platos],
            "backgroundColor": "rgba(217, 119, 6, 0.85)", # Peru 500
            "borderColor": "rgba(217, 119, 6, 1)",
            "borderWidth": 1.5,
            "borderRadius": 6
        },
        {
            "label": "Surco",
            "data": [su_forecasts.get(p, 0) for p in platos],
            "backgroundColor": "rgba(133, 77, 14, 0.75)", # Peru 800
            "borderColor": "rgba(133, 77, 14, 1)",
            "borderWidth": 1.5,
            "borderRadius": 6
        }
    ]
    
    return {
        "labels": platos,
        "datasets": datasets
    }
