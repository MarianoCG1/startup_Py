import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
import random
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DB_NAME = "demandarest.db"

# Utilidad para hash de contraseñas (simple y libre de dependencias nativas en Windows)
def hash_password(password: str) -> str:
    salt = b"demandarest_salt_2026_secured"
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

# Determinar si se usará Supabase
USING_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL.strip() and SUPABASE_KEY.strip())
supabase_client = None

if USING_SUPABASE:
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Connected to Supabase successfully.")
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}. Falling back to SQLite.")
        USING_SUPABASE = False

# Inicializar y seedear base de datos SQLite local
def init_local_db():
    if USING_SUPABASE:
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Crear tablas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        address TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL, -- 'owner', 'admin'
        location_id INTEGER,
        FOREIGN KEY(location_id) REFERENCES locations(id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        unit TEXT NOT NULL,
        category TEXT NOT NULL, -- 'perishable', 'non-perishable'
        avg_days_to_spoil INTEGER NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dish_recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dish_name TEXT NOT NULL,
        ingredient_name TEXT NOT NULL,
        quantity_per_dish REAL NOT NULL, -- en kg
        FOREIGN KEY(ingredient_name) REFERENCES ingredients(name)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_id INTEGER NOT NULL,
        sale_date TEXT NOT NULL, -- YYYY-MM-DD
        shift TEXT NOT NULL, -- 'almuerzo', 'cena'
        dish_name TEXT NOT NULL,
        quantity_sold INTEGER NOT NULL,
        FOREIGN KEY(location_id) REFERENCES locations(id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_stock (
        location_id INTEGER NOT NULL,
        ingredient_name TEXT NOT NULL,
        current_stock REAL NOT NULL, -- en kg
        PRIMARY KEY(location_id, ingredient_name),
        FOREIGN KEY(location_id) REFERENCES locations(id),
        FOREIGN KEY(ingredient_name) REFERENCES ingredients(name)
    )
    """)
    
    # Comprobar si ya existen datos sembrados
    cursor.execute("SELECT COUNT(*) FROM locations")
    if cursor.fetchone()[0] == 0:
        print("Seeding local database with realistic Peruvian restaurant data...")
        
        # 1. Sembrar Locales
        locales = [
            (1, "Santa Anita", "Av. Metropolitana 1245, Santa Anita"),
            (2, "Miraflores", "Av. Larco 782, Miraflores"),
            (3, "Surco", "Av. Caminos del Inca 345, Santiago de Surco")
        ]
        cursor.executemany("INSERT INTO locations (id, name, address) VALUES (?, ?, ?)", locales)
        
        # 2. Sembrar Usuarios
        usuarios = [
            ("user_owner", "owner@demandarest.com", hash_password("admin123"), "owner", None),
            ("user_admin_sa", "admin.santaanita@demandarest.com", hash_password("admin123"), "admin", 1),
            ("user_admin_mf", "admin.miraflores@demandarest.com", hash_password("admin123"), "admin", 2),
            ("user_admin_su", "admin.surco@demandarest.com", hash_password("admin123"), "admin", 3)
        ]
        cursor.executemany("INSERT INTO users (id, email, password_hash, role, location_id) VALUES (?, ?, ?, ?, ?)", usuarios)
        
        # 3. Sembrar Ingredientes
        ingredientes = [
            ("Carne de Res (Lomo)", "kg", "perishable", 4),
            ("Cebolla Roja", "kg", "perishable", 7),
            ("Tomate", "kg", "perishable", 4),
            ("Papa Amarilla", "kg", "non-perishable", 14),
            ("Arroz", "kg", "non-perishable", 90),
            ("Pescado Fresco", "kg", "perishable", 2),
            ("Limón Ácido", "kg", "perishable", 10),
            ("Camote", "kg", "non-perishable", 14),
            ("Choclo Desgranado", "kg", "perishable", 5),
            ("Pechuga de Pollo", "kg", "perishable", 3),
            ("Ají Amarillo", "kg", "perishable", 7),
            ("Leche Evaporada", "kg", "non-perishable", 60),
            ("Pan Molde", "kg", "perishable", 6),
            ("Mixtura de Mariscos", "kg", "perishable", 2),
            ("Ají Panca", "kg", "non-perishable", 30),
            ("Arvejas", "kg", "perishable", 5),
            ("Corazón de Res", "kg", "perishable", 3)
        ]
        cursor.executemany("INSERT INTO ingredients (name, unit, category, avg_days_to_spoil) VALUES (?, ?, ?, ?)", ingredientes)
        
        # 4. Sembrar Recetas
        recetas = [
            # Lomo Saltado
            ("Lomo Saltado", "Carne de Res (Lomo)", 0.200),
            ("Lomo Saltado", "Cebolla Roja", 0.100),
            ("Lomo Saltado", "Tomate", 0.100),
            ("Lomo Saltado", "Papa Amarilla", 0.150),
            ("Lomo Saltado", "Arroz", 0.100),
            # Ceviche Clásico
            ("Ceviche Clásico", "Pescado Fresco", 0.200),
            ("Ceviche Clásico", "Limón Ácido", 0.080),
            ("Ceviche Clásico", "Cebolla Roja", 0.050),
            ("Ceviche Clásico", "Camote", 0.100),
            ("Ceviche Clásico", "Choclo Desgranado", 0.050),
            # Ají de Gallina
            ("Ají de Gallina", "Pechuga de Pollo", 0.150),
            ("Ají de Gallina", "Ají Amarillo", 0.050),
            ("Ají de Gallina", "Leche Evaporada", 0.050),
            ("Ají de Gallina", "Pan Molde", 0.040),
            ("Ají de Gallina", "Papa Amarilla", 0.100),
            # Arroz con Mariscos
            ("Arroz con Mariscos", "Mixtura de Mariscos", 0.180),
            ("Arroz con Mariscos", "Arroz", 0.120),
            ("Arroz con Mariscos", "Ají Panca", 0.030),
            ("Arroz con Mariscos", "Arvejas", 0.020),
            # Anticuchos de Corazón
            ("Anticuchos de Corazón", "Corazón de Res", 0.250),
            ("Anticuchos de Corazón", "Ají Panca", 0.050),
            ("Anticuchos de Corazón", "Papa Amarilla", 0.100),
            ("Anticuchos de Corazón", "Choclo Desgranado", 0.080)
        ]
        cursor.executemany("INSERT INTO dish_recipes (dish_name, ingredient_name, quantity_per_dish) VALUES (?, ?, ?)", recetas)
        
        # 5. Sembrar Ventas Históricas (Últimos 14 días)
        # Para hacer que la predicción parezca inteligente, daremos a cada día de la semana un patrón,
        # y añadiremos un pico de ventas el último fin de semana y feriados.
        today = datetime.now()
        historial_ventas = []
        platos = ["Lomo Saltado", "Ceviche Clásico", "Ají de Gallina", "Arroz con Mariscos", "Anticuchos de Corazón"]
        
        for loc_id in [1, 2, 3]:
            for d in range(14, 0, -1):
                fecha_venta = (today - timedelta(days=d)).strftime("%Y-%m-%d")
                weekday = (today - timedelta(days=d)).weekday() # 0 = Lunes, 6 = Domingo
                
                for shift in ["almuerzo", "cena"]:
                    # Multiplicadores según día y turno
                    # Ceviche se vende más en almuerzo. Anticuchos se vende más en cena.
                    for plato in platos:
                        base_qty = 10
                        if weekday in [4, 5, 6]: # Fin de semana
                            base_qty = 18
                        
                        if plato == "Ceviche Clásico":
                            qty = base_qty + (8 if shift == "almuerzo" else -6)
                        elif plato == "Anticuchos de Corazón":
                            qty = base_qty + (-5 if shift == "almuerzo" else 10)
                        elif plato == "Lomo Saltado":
                            qty = base_qty + random.randint(2, 8)
                        else:
                            qty = base_qty + random.randint(-2, 4)
                        
                        # Agregar un poco de aleatoriedad
                        qty = max(2, qty + random.randint(-3, 3))
                        
                        historial_ventas.append((loc_id, fecha_venta, shift, plato, qty))
        
        cursor.executemany("INSERT INTO sales (location_id, sale_date, shift, dish_name, quantity_sold) VALUES (?, ?, ?, ?, ?)", historial_ventas)
        
        # 6. Sembrar Stock de Inventario
        # Inicialmente ponemos stock suficiente pero crítico para algunos ingredientes en el local 1 (Santa Anita)
        # para detonar las alertas de perecederos.
        # Por ejemplo: Pescado Fresco con 2.5 kg (cuando la demanda semanal estimada es mucho más alta),
        # Tomate con 3.0 kg, Carne de Res con 25 kg.
        stock_inicial = []
        for loc_id in [1, 2, 3]:
            for ing_nombre, _, cat, _ in ingredientes:
                # Stock base aleatorio
                if cat == "perishable":
                    if ing_nombre == "Pescado Fresco" and loc_id == 1:
                        stock = 2.5  # Muy crítico
                    elif ing_nombre == "Tomate" and loc_id == 1:
                        stock = 4.0  # Alerta media
                    elif ing_nombre == "Cebolla Roja" and loc_id == 1:
                        stock = 15.0 # Suficiente
                    else:
                        stock = round(random.uniform(5.0, 20.0), 1)
                else:
                    stock = round(random.uniform(30.0, 100.0), 1)
                
                stock_inicial.append((loc_id, ing_nombre, stock))
        
        cursor.executemany("INSERT INTO inventory_stock (location_id, ingredient_name, current_stock) VALUES (?, ?, ?)", stock_inicial)
        
    conn.commit()
    conn.close()

# Llamar a inicialización al cargar el módulo
init_local_db()

# =====================================================================
# INTERFAZ DE BASE DE DATOS COMPATIBLE PARA SUPABASE Y SQLITE LOCAL
# =====================================================================

class Database:
    @staticmethod
    def get_conn():
        return sqlite3.connect(DB_NAME)

    @classmethod
    def get_user_by_email(cls, email: str):
        if USING_SUPABASE:
            try:
                # Usar Supabase auth / perfiles
                res = supabase_client.table("profiles").select("id, email, role, location_id").eq("email", email).execute()
                if res.data:
                    profile = res.data[0]
                    # Nota: La contraseña en Supabase se maneja por su Auth, esto es solo para el perfil
                    return profile
            except Exception as e:
                print(f"Supabase user profile fetch error: {e}")
        
        # Fallback local
        conn = cls.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.email, u.password_hash, u.role, u.location_id, l.name 
            FROM users u
            LEFT JOIN locations l ON u.location_id = l.id
            WHERE u.email = ?
        """, (email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "email": row[1],
                "password_hash": row[2],
                "role": row[3],
                "location_id": row[4],
                "location_name": row[5]
            }
        return None

    @classmethod
    def register_user(cls, uid: str, email: str, role: str, location_id: Optional[int] = None):
        # Para Supabase, el registro suele ser a través de Auth + Trigger.
        # Aquí proveemos la inserción en el fallback local
        if not USING_SUPABASE:
            conn = cls.get_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (id, email, password_hash, role, location_id) VALUES (?, ?, ?, ?, ?)",
                    (uid, email, hash_password("admin123"), role, location_id)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass
            finally:
                conn.close()

    @classmethod
    def get_locations(cls):
        if USING_SUPABASE:
            try:
                res = supabase_client.table("locations").select("*").execute()
                return res.data
            except Exception as e:
                print(f"Supabase get_locations error: {e}")
                
        conn = cls.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, address FROM locations")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "name": r[1], "address": r[2]} for r in rows]

    @classmethod
    def get_location_name(cls, location_id: int) -> str:
        if USING_SUPABASE:
            try:
                res = supabase_client.table("locations").select("name").eq("id", location_id).single().execute()
                if res.data:
                    return res.data["name"]
            except Exception as e:
                print(f"Supabase get_location_name error: {e}")
                
        conn = cls.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else "Desconocido"

    @classmethod
    def get_sales_history(cls, location_id: Optional[int] = None, limit: int = 100):
        if USING_SUPABASE:
            try:
                query = supabase_client.table("sales").select("*, locations(name)")
                if location_id:
                    query = query.eq("location_id", location_id)
                res = query.order("sale_date", desc=True).limit(limit).execute()
                return res.data
            except Exception as e:
                print(f"Supabase get_sales_history error: {e}")
                
        conn = cls.get_conn()
        cursor = conn.cursor()
        if location_id:
            cursor.execute("""
                SELECT s.id, s.location_id, l.name, s.sale_date, s.shift, s.dish_name, s.quantity_sold
                FROM sales s
                JOIN locations l ON s.location_id = l.id
                WHERE s.location_id = ?
                ORDER BY s.sale_date DESC, s.shift DESC
                LIMIT ?
            """, (location_id, limit))
        else:
            cursor.execute("""
                SELECT s.id, s.location_id, l.name, s.sale_date, s.shift, s.dish_name, s.quantity_sold
                FROM sales s
                JOIN locations l ON s.location_id = l.id
                ORDER BY s.sale_date DESC, s.shift DESC
                LIMIT ?
            """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "location_id": r[1],
                "location_name": r[2],
                "sale_date": r[3],
                "shift": r[4],
                "dish_name": r[5],
                "quantity_sold": r[6]
            } for r in rows
        ]

    @classmethod
    def record_sale(cls, location_id: int, sale_date: str, shift: str, dish_name: str, quantity_sold: int):
        if USING_SUPABASE:
            try:
                data = {
                    "location_id": location_id,
                    "sale_date": sale_date,
                    "shift": shift,
                    "dish_name": dish_name,
                    "quantity_sold": quantity_sold
                }
                res = supabase_client.table("sales").insert(data).execute()
                
                # Descontar stock del inventario para los ingredientes de esta receta
                # (Simulado o real, aquí actualizamos localmente el inventario)
                cls._consume_stock_for_sale(location_id, dish_name, quantity_sold)
                return res.data
            except Exception as e:
                print(f"Supabase record_sale error: {e}")
                
        conn = cls.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sales (location_id, sale_date, shift, dish_name, quantity_sold)
            VALUES (?, ?, ?, ?, ?)
        """, (location_id, sale_date, shift, dish_name, quantity_sold))
        conn.commit()
        conn.close()
        
        # Descontar stock
        cls._consume_stock_for_sale(location_id, dish_name, quantity_sold)
        return True

    @classmethod
    def _consume_stock_for_sale(cls, location_id: int, dish_name: str, quantity_sold: int):
        conn = cls.get_conn()
        cursor = conn.cursor()
        
        # Obtener los ingredientes y cantidades por plato
        cursor.execute("""
            SELECT ingredient_name, quantity_per_dish
            FROM dish_recipes
            WHERE dish_name = ?
        """, (dish_name,))
        ingredients_needed = cursor.fetchall()
        
        for ing_name, qty_per_dish in ingredients_needed:
            qty_to_consume = qty_per_dish * quantity_sold
            cursor.execute("""
                UPDATE inventory_stock
                SET current_stock = MAX(0, current_stock - ?)
                WHERE location_id = ? AND ingredient_name = ?
            """, (qty_to_consume, location_id, ing_name))
            
        conn.commit()
        conn.close()

    @classmethod
    def get_ingredients(cls):
        if USING_SUPABASE:
            try:
                res = supabase_client.table("ingredients").select("*").execute()
                return res.data
            except Exception as e:
                print(f"Supabase get_ingredients error: {e}")
                
        conn = cls.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, unit, category, avg_days_to_spoil FROM ingredients")
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "name": r[1],
                "unit": r[2],
                "category": r[3],
                "avg_days_to_spoil": r[4]
            } for r in rows
        ]

    @classmethod
    def get_inventory_stock(cls, location_id: int):
        if USING_SUPABASE:
            try:
                res = supabase_client.table("inventory_stock").select("*, ingredients(*)").eq("location_id", location_id).execute()
                return res.data
            except Exception as e:
                print(f"Supabase get_inventory_stock error: {e}")
                
        conn = cls.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT i.name, i.unit, i.category, i.avg_days_to_spoil, s.current_stock
            FROM inventory_stock s
            JOIN ingredients i ON s.ingredient_name = i.name
            WHERE s.location_id = ?
        """, (location_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "ingredient_name": r[0],
                "unit": r[1],
                "category": r[2],
                "avg_days_to_spoil": r[3],
                "current_stock": r[4]
            } for r in rows
        ]

    @classmethod
    def get_recipes(cls):
        conn = cls.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT dish_name, ingredient_name, quantity_per_dish FROM dish_recipes")
        rows = cursor.fetchall()
        conn.close()
        
        recipes = {}
        for dish, ing, qty in rows:
            if dish not in recipes:
                recipes[dish] = []
            recipes[dish].append({"ingredient": ing, "qty": qty})
        return recipes
