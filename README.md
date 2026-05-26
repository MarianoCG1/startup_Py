# DemandaRest - Panel de Predicción de Demanda e Inventario

DemandaRest es una aplicación web móvil-first diseñada para cadenas de restaurantes peruanos. Permite a los propietarios y administradores predecir la demanda de platos típicos (como Lomo Saltado, Ceviche Clásico y Ají de Gallina), calcular el volumen de insumos en kilogramos y recibir alertas tempranas de desperdicio de insumos perecederos.

Este sistema utiliza **FastAPI (Python)** para el backend con renderizado de plantillas **Jinja2**, **HTMX** para solicitudes asíncronas dinámicas, y **Tailwind CSS** para un diseño moderno y cálido.

---

## Características de la Aplicación

1. **Dashboard de Propietario (Owner Dashboard):**
   - Vista semanal consolidada de la demanda proyectada por plato en las 3 ubicaciones (Santa Anita, Miraflores, Surco) usando **Chart.js**.
   - Cálculo agregado de insumos a comprar en kilogramos.
   - Calendario de fechas festivas peruanas (Feriados) que impactan en la demanda (+50% de incremento proyectado).

2. **Dashboard de Administrador (Admin Dashboard):**
   - Panel de control enfocado en el local asignado (ej. Santa Anita).
   - **Formulario de Registro de Ventas Diarias:** Con validación nativa HTML5 y envío mediante HTMX, actualizando el estado de la base de datos sin recargar la página.
   - **Alertas de Ingredientes Perecederos:** Semáforo de advertencia (Rojo/Naranja/Verde) con Jinja2 y Tailwind CSS. El cálculo analiza si el stock actual durará menos del consumo diario estimado (desabastecimiento) o si excede la vida útil útil antes de consumirse (desperdicio).

3. **Reporte de Compras y Generador de Órdenes:**
   - Tabla de ingredientes totales por local y consolidada.
   - **CTA HTMX ("Generar lista de compra para Santa Anita"):** Simula procesamiento con indicador de carga HTMX (`hx-indicator`) y renderiza una lista de compras interactiva para que el personal tache los insumos adquiridos y la envíe al proveedor.

---

## Cuentas de Demostración (Demo Accounts)

Inicie sesión con los siguientes perfiles de prueba:

* **Dueño (Owner - Acceso Total):**
  - **Correo:** `owner@demandarest.com`
  - **Contraseña:** `admin123`

* **Administrador (Santa Anita):**
  - **Correo:** `admin.santaanita@demandarest.com`
  - **Contraseña:** `admin123`

* **Administrador (Miraflores):**
  - **Correo:** `admin.miraflores@demandarest.com`
  - **Contraseña:** `admin123`

* **Administrador (Surco):**
  - **Correo:** `admin.surco@demandarest.com`
  - **Contraseña:** `admin123`

---

## Instrucciones de Instalación y Ejecución

### 1. Requisitos Previos
Asegúrese de tener instalado Python 3.10 o superior en su equipo.

### 2. Configurar el Entorno Virtual
Abra una terminal en la raíz del proyecto y ejecute:

```bash
# Crear entorno virtual
python -m venv venv

# Activar el entorno virtual (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activar el entorno virtual (Windows CMD)
.\venv\Scripts\activate.bat

# Activar el entorno virtual (Linux/macOS)
source venv/bin/activate
```

### 3. Instalar Dependencias
Instale los paquetes necesarios listados en `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno
El proyecto cuenta con un archivo `.env` configurado.
* **Modo Local (SQLite):** Si los campos `SUPABASE_URL` y `SUPABASE_KEY` se dejan en blanco, la aplicación se iniciará de forma **100% autónoma** creando un archivo de base de datos local `demandarest.db` precargado con historial de ventas de 14 días, recetas, locales y stock de inventario.
* **Modo Supabase:** Si desea utilizar su base de datos Supabase, edite el archivo `.env` con las credenciales de su proyecto:
  ```env
  PORT=8000
  SECRET_KEY=clave_secreta_jwt_de_ejemplo
  SUPABASE_URL=https://tu-proyecto.supabase.co
  SUPABASE_KEY=tu-anon-key-de-supabase
  ```

### 5. Iniciar la Aplicación
Ejecute el servidor de desarrollo Uvicorn:

```bash
uvicorn app.main:app --reload --port 8000
```

Abra su navegador y acceda a [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## Configuración de Supabase (SQL Editor)

Si opta por conectar la aplicación a un proyecto real de Supabase, ejecute el siguiente script SQL en el **SQL Editor** de su consola de Supabase para inicializar la estructura de datos:

```sql
-- 1. Crear tabla de Locales
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    address TEXT
);

-- Insertar Locales de Prueba
INSERT INTO locations (name, address) VALUES 
('Santa Anita', 'Av. Metropolitana 1245, Santa Anita'),
('Miraflores', 'Av. Larco 782, Miraflores'),
('Surco', 'Av. Caminos del Inca 345, Santiago de Surco');

-- 2. Crear Tabla de Perfiles de Usuario (Roles)
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    role TEXT CHECK (role IN ('owner', 'admin')) NOT NULL,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL
);

-- 3. Crear Tabla de Ingredientes
CREATE TABLE ingredients (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    unit TEXT NOT NULL,
    category TEXT CHECK (category IN ('perishable', 'non-perishable')) NOT NULL,
    avg_days_to_spoil INTEGER NOT NULL
);

-- 4. Crear Tabla de Recetas (Insumos por Plato)
CREATE TABLE dish_recipes (
    id SERIAL PRIMARY KEY,
    dish_name TEXT NOT NULL,
    ingredient_name TEXT REFERENCES ingredients(name) ON DELETE CASCADE,
    quantity_per_dish DOUBLE PRECISION NOT NULL
);

-- 5. Crear Tabla de Ventas Diarias
CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    sale_date DATE NOT NULL,
    shift TEXT CHECK (shift IN ('almuerzo', 'cena')) NOT NULL,
    dish_name TEXT NOT NULL,
    quantity_sold INTEGER NOT NULL
);

-- 6. Crear Tabla de Inventario de Stock
CREATE TABLE inventory_stock (
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    ingredient_name TEXT REFERENCES ingredients(name) ON DELETE CASCADE,
    current_stock DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (location_id, ingredient_name)
);
```
