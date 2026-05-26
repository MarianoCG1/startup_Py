from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.database import Database
from app.models import DishDemandForecast, IngredientAlert, ImportantDate, IngredientPurchaseRequirement

# Lista de fechas festivas importantes en Perú (2026)
PERUVIAN_HOLIDAYS = [
    {"date": "2026-05-01", "name": "Día del Trabajo", "multiplier": 1.4, "description": "Feriado nacional, incremento general de comensales."},
    {"date": "2026-06-07", "name": "Batalla de Arica / Día de la Bandera", "multiplier": 1.25, "description": "Día cívico, mayor concurrencia almuerzo."},
    {"date": "2026-06-28", "name": "Día Nacional del Ceviche", "multiplier": 1.8, "description": "Incremento masivo (+80%) en Ceviche Clásico y Mariscos en almuerzo."},
    {"date": "2026-06-29", "name": "San Pedro y San Pablo", "multiplier": 1.45, "description": "Feriado religioso y feriado de pescadores. Alta demanda de pescados."},
    {"date": "2026-07-28", "name": "Fiestas Patrias (Día 1)", "multiplier": 1.6, "description": "Celebración nacional de la Independencia. Turismo y salidas masivas."},
    {"date": "2026-07-29", "name": "Fiestas Patrias (Día 2)", "multiplier": 1.5, "description": "Gran parada militar, familias almuerzan fuera."},
    {"date": "2026-08-30", "name": "Santa Rosa de Lima", "multiplier": 1.5, "description": "Peregrinación y feriado religioso, familias completas saliendo a comer."},
    {"date": "2026-10-08", "name": "Combate de Angamos", "multiplier": 1.3, "description": "Feriado nacional por el almirante Grau."},
    {"date": "2026-11-01", "name": "Día de Todos los Santos", "multiplier": 1.35, "description": "Feriado religioso familiar."},
    {"date": "2026-12-08", "name": "Inmaculada Concepción", "multiplier": 1.4, "description": "Fin de semana largo y compras navideñas en marcha."},
    {"date": "2026-12-25", "name": "Navidad", "multiplier": 1.5, "description": "Almuerzo de Navidad familiar fuera de casa."}
]

def get_upcoming_holidays(days_ahead: int = 45) -> List[Dict[str, Any]]:
    """Obtiene los feriados próximos a partir del 26 de Mayo de 2026."""
    current_date = datetime.strptime("2026-05-26", "%Y-%m-%d")
    limit_date = current_date + timedelta(days=days_ahead)
    
    upcoming = []
    for h in PERUVIAN_HOLIDAYS:
        h_date = datetime.strptime(h["date"], "%Y-%m-%d")
        if current_date <= h_date <= limit_date:
            upcoming.append(h)
    return upcoming

def get_dish_weekly_forecast(location_id: int) -> List[DishDemandForecast]:
    """Predice la demanda de platos para la próxima semana (7 días) a partir de hoy (26 de Mayo de 2026)."""
    # Usamos el historial de ventas
    sales = Database.get_sales_history(location_id=location_id, limit=500)
    
    # Si no hay historial suficiente, usamos predicciones basadas en la semilla
    if not sales:
        return [
            DishDemandForecast(dish_name="Lomo Saltado", predicted_quantity=115, confidence_level="Alta"),
            DishDemandForecast(dish_name="Ceviche Clásico", predicted_quantity=140, confidence_level="Alta"),
            DishDemandForecast(dish_name="Ají de Gallina", predicted_quantity=95, confidence_level="Alta"),
            DishDemandForecast(dish_name="Arroz con Mariscos", predicted_quantity=110, confidence_level="Media"),
            DishDemandForecast(dish_name="Anticuchos de Corazón", predicted_quantity=125, confidence_level="Alta")
        ]
        
    # Organizar ventas por plato y día de la semana para promediar
    # Estructura: sales_by_dish[dish_name][weekday][shift] = List[quantity]
    sales_by_dish = {}
    for s in sales:
        plato = s["dish_name"]
        try:
            fecha_dt = datetime.strptime(s["sale_date"], "%Y-%m-%d")
            wday = fecha_dt.weekday()
        except ValueError:
            continue
        
        shift = s["shift"]
        qty = s["quantity_sold"]
        
        if plato not in sales_by_dish:
            sales_by_dish[plato] = {w: {"almuerzo": [], "cena": []} for w in range(7)}
        
        sales_by_dish[plato][wday][shift].append(qty)

    # Predecir cada día de la próxima semana
    # Asumimos que la semana de predicción comienza mañana, 27 de Mayo de 2026 (Miércoles)
    start_date = datetime.strptime("2026-05-27", "%Y-%m-%d")
    forecasts = {}
    
    for dish_name in sales_by_dish.keys():
        predicted_total = 0
        for d in range(7):
            pred_date = start_date + timedelta(days=d)
            pred_date_str = pred_date.strftime("%Y-%m-%d")
            wday = pred_date.weekday()
            
            # Revisar si es feriado
            multiplier = 1.0
            holiday_name = ""
            for h in PERUVIAN_HOLIDAYS:
                if h["date"] == pred_date_str:
                    multiplier = h["multiplier"]
                    holiday_name = h["name"]
                    break
            
            # Promedios históricos para este día y plato
            for shift in ["almuerzo", "cena"]:
                historical_vals = sales_by_dish[dish_name][wday][shift]
                if historical_vals:
                    avg_val = sum(historical_vals) / len(historical_vals)
                else:
                    # Fallback general
                    avg_val = 15.0 if wday >= 4 else 10.0
                
                # Ajustes específicos por plato si hay feriados especiales (ej. Día del Ceviche)
                current_mult = multiplier
                if holiday_name == "Día Nacional del Ceviche" and dish_name == "Ceviche Clásico" and shift == "almuerzo":
                    current_mult = 2.0  # Duplica la venta de ceviche
                elif holiday_name == "San Pedro y San Pablo" and dish_name in ["Ceviche Clásico", "Arroz con Mariscos"]:
                    current_mult = 1.6  # Feriado marítimo
                
                predicted_total += avg_val * current_mult
                
        forecasts[dish_name] = int(round(predicted_total))

    # Asegurarnos de que todos los platos base tengan predicción
    platos_base = ["Lomo Saltado", "Ceviche Clásico", "Ají de Gallina", "Arroz con Mariscos", "Anticuchos de Corazón"]
    for p in platos_base:
        if p not in forecasts:
            forecasts[p] = 100 # Fallback por defecto

    # Definir niveles de confianza en base al número de ventas analizadas
    results = []
    for dish, qty in forecasts.items():
        # Cuantas más ventas registradas, más confianza
        sales_count = sum(1 for s in sales if s["dish_name"] == dish)
        confidence = "Alta" if sales_count > 20 else ("Media" if sales_count > 5 else "Baja")
        results.append(DishDemandForecast(dish_name=dish, predicted_quantity=qty, confidence_level=confidence))
        
    return results

def get_weekly_purchase_requirements() -> List[IngredientPurchaseRequirement]:
    """Calcula los kilos agregados por ingrediente y local para la semana entrante."""
    recipes = Database.get_recipes()
    
    # Pronósticos para cada uno de los 3 locales
    forecasts = {
        1: get_dish_weekly_forecast(1), # Santa Anita
        2: get_dish_weekly_forecast(2), # Miraflores
        3: get_dish_weekly_forecast(3)  # Surco
    }
    
    ingredients_dict = {ing["name"]: ing for ing in Database.get_ingredients()}
    
    purchase_reqs = {}
    
    for loc_id, f_list in forecasts.items():
        for f in f_list:
            dish = f.dish_name
            qty_predicted = f.predicted_quantity
            
            if dish in recipes:
                for ing_item in recipes[dish]:
                    ing_name = ing_item["ingredient"]
                    qty_per_dish = ing_item["qty"]
                    
                    needed_kilos = qty_predicted * qty_per_dish
                    
                    if ing_name not in purchase_reqs:
                        purchase_reqs[ing_name] = {
                            1: 0.0,
                            2: 0.0,
                            3: 0.0,
                            "unit": ingredients_dict.get(ing_name, {}).get("unit", "kg")
                        }
                    purchase_reqs[ing_name][loc_id] += needed_kilos
                    
    results = []
    for ing_name, data in purchase_reqs.items():
        total = data[1] + data[2] + data[3]
        results.append(
            IngredientPurchaseRequirement(
                ingredient_name=ing_name,
                unit=data["unit"],
                kilos_santa_anita=round(data[1], 2),
                kilos_miraflores=round(data[2], 2),
                kilos_surco=round(data[3], 2),
                total_kilos=round(total, 2)
            )
        )
    # Ordenar por volumen total descendente
    results.sort(key=lambda x: x.total_kilos, reverse=True)
    return results

def get_perishable_alerts(location_id: int) -> List[IngredientAlert]:
    """Calcula el riesgo de descomposición y desabastecimiento de ingredientes perecederos en un local."""
    inventory = Database.get_inventory_stock(location_id)
    recipes = Database.get_recipes()
    forecast = get_dish_weekly_forecast(location_id)
    
    # Mapear predicciones
    forecast_dict = {f.dish_name: f.predicted_quantity for f in forecast}
    
    # Calcular consumo semanal estimado por ingrediente
    weekly_consumption = {}
    for dish, ing_list in recipes.items():
        qty_pred = forecast_dict.get(dish, 0)
        for ing in ing_list:
            name = ing["ingredient"]
            qty = ing["qty"]
            weekly_consumption[name] = weekly_consumption.get(name, 0.0) + (qty_pred * qty)
            
    alerts = []
    for item in inventory:
        # Analizar solo ingredientes perecederos
        if item["category"] != "perishable":
            continue
            
        name = item["ingredient_name"]
        stock = item["current_stock"]
        days_to_spoil = item["avg_days_to_spoil"]
        
        needed = weekly_consumption.get(name, 0.0)
        daily_needed = needed / 7.0
        
        # 1. Riesgo de Desabastecimiento (Bajo Stock)
        # Si el stock dura menos de 2 días de consumo estimado
        if daily_needed > 0:
            days_stock_lasts = stock / daily_needed
        else:
            days_stock_lasts = 999.0
            
        status = "ok"
        message = "Stock saludable para cubrir la demanda."
        
        # Evaluar desabastecimiento
        if days_stock_lasts < 1.0:
            status = "danger"
            message = f"Desabastecimiento crítico. El stock dura menos de 1 día ({round(days_stock_lasts, 1)} días restantes)."
        elif days_stock_lasts < 2.5:
            status = "warning"
            message = f"Stock bajo. Se requiere reabastecer pronto ({round(days_stock_lasts, 1)} días restantes)."
            
        # 2. Riesgo de Desperdicio / Descomposición (Sobrestock en relación a su vida útil)
        # Si el stock actual es mayor a lo que consumimos antes de que se descomponga
        if stock > (daily_needed * days_to_spoil) and stock > 2.0:
            # Ejemplo: Pescado fresco dura 2 días. Si tenemos 10kg y consumimos 2kg por día,
            # en 2 días consumimos 4kg y 6kg se pudrirán.
            spoiled_qty = stock - (daily_needed * days_to_spoil)
            if spoiled_qty > 1.0: # Sólo alertar por desperdicios significativos
                status = "danger"
                message = f"¡Alto riesgo de merma! Se estima que se desperdiciarán {round(spoiled_qty, 1)} kg de {name} antes de vencer."
                
        # Casos especiales de negocio simulados si el stock está por debajo del umbral mínimo de seguridad:
        if name == "Pescado Fresco" and stock < 3.0:
            status = "danger"
            message = f"Alerta crítica: Solo {stock} kg de Pescado Fresco disponible. Riesgo inminente de detener ventas de Ceviche."
        elif name == "Tomate" and stock < 5.0:
            status = "warning"
            message = f"Alerta de inventario: Stock de Tomate bajo ({stock} kg). Consumo acelerado por alta demanda de Lomo Saltado."

        alerts.append(
            IngredientAlert(
                name=name,
                category=item["category"],
                current_stock=round(stock, 2),
                weekly_needed=round(needed, 2),
                days_to_spoil=days_to_spoil,
                status=status,
                message=message
            )
        )
        
    # Ordenar las alertas: peligro primero, advertencias después, luego saludables
    status_order = {"danger": 0, "warning": 1, "ok": 2}
    alerts.sort(key=lambda x: status_order[x.status])
    return alerts
