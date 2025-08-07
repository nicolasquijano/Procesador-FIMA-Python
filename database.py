"""
Gestor de base de datos SQLite con soporte para precisión decimal
"""
import sqlite3
import json
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from config import DB_PATH

class DecimalAdapter:
    """Adaptador para convertir Decimal a string en SQLite"""
    
    @staticmethod
    def adapt_decimal(decimal_obj):
        return str(decimal_obj)
    
    @staticmethod
    def convert_decimal(text):
        return Decimal(text.decode('utf-8'))

# Registrar adaptadores de Decimal
sqlite3.register_adapter(Decimal, DecimalAdapter.adapt_decimal)
sqlite3.register_converter("decimal", DecimalAdapter.convert_decimal)

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    def get_connection(self):
        """Obtener conexión con soporte para decimales"""
        return sqlite3.connect(
            self.db_path, 
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=30.0
        )
    
    def _init_database(self):
        """Inicializar estructura de base de datos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla de operaciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    fund_name TEXT NOT NULL,
                    fund_type TEXT,
                    quantity DECIMAL NOT NULL,
                    unit_value DECIMAL NOT NULL,
                    total_amount DECIMAL NOT NULL,
                    description TEXT,
                    pdf_source TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de posiciones actuales
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_name TEXT UNIQUE NOT NULL,
                    fund_type TEXT,
                    quantity DECIMAL NOT NULL,
                    unit_value DECIMAL NOT NULL,
                    total_value DECIMAL NOT NULL,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de configuración por fondo
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fund_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_name TEXT UNIQUE NOT NULL,
                    fund_type TEXT NOT NULL,
                    initial_balance DECIMAL DEFAULT 0,
                    active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def add_operation(self, operation_data: Dict) -> int:
        """Agregar nueva operación"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO operations 
                (date, operation_type, fund_name, fund_type, quantity, 
                 unit_value, total_amount, description, pdf_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operation_data['date'],
                operation_data['operation_type'],
                operation_data['fund_name'],
                operation_data.get('fund_type'),
                Decimal(str(operation_data['quantity'])),
                Decimal(str(operation_data['unit_value'])),
                Decimal(str(operation_data['total_amount'])),
                operation_data.get('description'),
                operation_data.get('pdf_source')
            ))
            return cursor.lastrowid
    
    def update_position(self, position_data: Dict):
        """Actualizar o insertar posición"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO positions
                (fund_name, fund_type, quantity, unit_value, total_value, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                position_data['fund_name'],
                position_data.get('fund_type'),
                Decimal(str(position_data['quantity'])),
                Decimal(str(position_data['unit_value'])),
                Decimal(str(position_data['total_value'])),
                datetime.now().isoformat()
            ))
            conn.commit()
    
    def get_operations(self, fund_type: str = None, 
                      date_from: str = None, date_to: str = None) -> List[Dict]:
        """Obtener operaciones con filtros opcionales"""
        with self.get_connection() as conn:
            query = "SELECT * FROM operations WHERE 1=1"
            params = []
            
            if fund_type:
                query += " AND fund_type = ?"
                params.append(fund_type)
            
            if date_from:
                query += " AND date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND date <= ?"
                params.append(date_to)
            
            query += " ORDER BY date DESC"
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_positions(self) -> List[Dict]:
        """Obtener todas las posiciones actuales"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions ORDER BY fund_name")
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def set_fund_config(self, fund_name: str, fund_type: str, 
                       initial_balance: Decimal = Decimal('0')):
        """Configurar fondo"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO fund_config
                (fund_name, fund_type, initial_balance)
                VALUES (?, ?, ?)
            ''', (fund_name, fund_type, initial_balance))
            conn.commit()
    
    def get_fund_configs(self) -> List[Dict]:
        """Obtener configuraciones de fondos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fund_config WHERE active = 1 ORDER BY fund_name")
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_fund_types(self) -> List[str]:
        """Obtener tipos de fondos únicos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT fund_type FROM operations WHERE fund_type IS NOT NULL")
            return [row[0] for row in cursor.fetchall()]
    
    def delete_operation(self, operation_id: int) -> bool:
        """Eliminar operación por ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM operations WHERE id = ?", (operation_id,))
            return cursor.rowcount > 0
    
    def get_database_stats(self) -> Dict:
        """Obtener estadísticas de la base de datos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Contar operaciones
            cursor.execute("SELECT COUNT(*) FROM operations")
            stats['total_operations'] = cursor.fetchone()[0]
            
            # Contar posiciones
            cursor.execute("SELECT COUNT(*) FROM positions")
            stats['total_positions'] = cursor.fetchone()[0]
            
            # Contar fondos configurados
            cursor.execute("SELECT COUNT(*) FROM fund_config WHERE active = 1")
            stats['configured_funds'] = cursor.fetchone()[0]
            
            # Valor total del portfolio
            cursor.execute("SELECT SUM(total_value) FROM positions")
            total_value = cursor.fetchone()[0]
            stats['total_portfolio_value'] = total_value if total_value else Decimal('0')
            
            return stats