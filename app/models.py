from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import date

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfile(BaseModel):
    id: str
    email: str
    role: str  # 'owner' or 'admin'
    location_id: Optional[int] = None
    location_name: Optional[str] = None

class DailySaleCreate(BaseModel):
    dish_name: str = Field(..., min_length=2)
    quantity_sold: int = Field(..., ge=0)
    shift: str = Field(..., pattern="^(almuerzo|cena)$")
    sale_date: date

class IngredientAlert(BaseModel):
    name: str
    category: str
    current_stock: float  # in kg
    weekly_needed: float  # in kg
    days_to_spoil: int
    status: str  # 'danger' (red), 'warning' (orange), 'ok' (green)
    message: str

class DishDemandForecast(BaseModel):
    dish_name: str
    predicted_quantity: int
    confidence_level: str  # 'Alta', 'Media', 'Baja'

class LocationDemandForecast(BaseModel):
    location_id: int
    location_name: str
    forecasts: List[DishDemandForecast]

class ImportantDate(BaseModel):
    date: str
    name: str
    demand_multiplier: float
    description: str

class IngredientPurchaseRequirement(BaseModel):
    ingredient_name: str
    unit: str
    kilos_santa_anita: float
    kilos_miraflores: float
    kilos_surco: float
    total_kilos: float
