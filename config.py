"""
Configuración global del procesador PDF financiero
"""
import os
from decimal import Decimal, getcontext

# Configurar precisión decimal global
getcontext().prec = 28

# Rutas del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'financial_data.db')
EXPORT_DIR = os.path.join(DATA_DIR, 'exports')

# Crear directorios si no existen
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# Configuración de la aplicación
APP_CONFIG = {
    'app_name': 'Procesador PDF Financiero',
    'version': '1.0.0',
    'window_size': '1200x800',
    'decimal_places': 8
}

# Tipos de fondos FIMA comunes
FUND_TYPES = [
    'Renta Fija',
    'Renta Variable', 
    'Mixto',
    'Money Market',
    'Obligaciones Negociables',
    'Acciones',
    'Otro'
]

# Patrones de regex para parsing PDF
PDF_PATTERNS = {
    'operation_date': r'\d{2}/\d{2}/\d{4}',
    'fund_name': r'[A-Z][A-Za-z\s]+(?:FIMA|FCI|FCIC)',
    'amount': r'\$?\s*[\d,]+\.?\d*',
    'quantity': r'[\d,]+\.?\d+',
    'unit_value': r'[\d,]+\.\d+'
}