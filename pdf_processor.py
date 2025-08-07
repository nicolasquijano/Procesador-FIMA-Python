"""
Procesador de PDFs financieros con múltiples engines y parseo inteligente
MEJORADO ESPECÍFICAMENTE PARA FIMA CON CÁLCULO PEPS
"""
import re
import os
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

# Importar librerías PDF
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from config import PDF_PATTERNS

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PEPSCalculator:
    """Calculadora de rentabilidad usando método PEPS (Primero En Entrar, Primero En Salir)"""
    
    def __init__(self):
        self.inventory = []  # Lista de compras/suscripciones
        
    def add_purchase(self, date: str, quantity: Decimal, unit_price: Decimal):
        """Agregar suscripción/compra al inventario PEPS"""
        self.inventory.append({
            'date': date,
            'quantity': quantity,
            'unit_price': unit_price,
            'remaining': quantity
        })
        
    def calculate_sale(self, date: str, quantity_sold: Decimal, sale_price: Decimal) -> Dict:
        """Calcular ganancia/pérdida de un rescate usando PEPS"""
        if not self.inventory:
            return {
                'gain_loss': Decimal('0'),
                'cost_basis': Decimal('0'),
                'sale_value': quantity_sold * sale_price,
                'error': 'No hay suscripciones previas para calcular PEPS'
            }
        
        total_cost = Decimal('0')
        remaining_to_sell = quantity_sold
        used_lots = []
        
        # Usar lotes en orden PEPS (primero en entrar, primero en salir)
        for lot in self.inventory:
            if remaining_to_sell <= 0:
                break
                
            if lot['remaining'] > 0:
                # Cantidad a usar de este lote
                qty_from_lot = min(lot['remaining'], remaining_to_sell)
                cost_from_lot = qty_from_lot * lot['unit_price']
                
                total_cost += cost_from_lot
                lot['remaining'] -= qty_from_lot
                remaining_to_sell -= qty_from_lot
                
                used_lots.append({
                    'date': lot['date'],
                    'quantity': qty_from_lot,
                    'unit_price': lot['unit_price'],
                    'cost': cost_from_lot
                })
        
        sale_value = quantity_sold * sale_price
        gain_loss = sale_value - total_cost
        
        return {
            'gain_loss': gain_loss,
            'cost_basis': total_cost,
            'sale_value': sale_value,
            'used_lots': used_lots,
            'error': None if remaining_to_sell <= 0 else f'Faltan {remaining_to_sell} cuotas en inventario'
        }
    
    def get_current_position(self) -> Dict:
        """Obtener posición actual según PEPS"""
        total_quantity = sum(lot['remaining'] for lot in self.inventory)
        total_cost = sum(lot['remaining'] * lot['unit_price'] for lot in self.inventory)
        avg_cost = total_cost / total_quantity if total_quantity > 0 else Decimal('0')
        
        return {
            'quantity': total_quantity,
            'total_cost': total_cost,
            'average_cost': avg_cost,
            'lots': [lot for lot in self.inventory if lot['remaining'] > 0]
        }

class PDFProcessor:
    """Procesador principal de PDFs financieros mejorado para FIMA"""
    
    def __init__(self):
        self.available_engines = self._check_available_engines()
        if not self.available_engines:
            raise ImportError("No hay librerías PDF disponibles. Instala PyPDF2, pdfplumber o PyMuPDF")
    
    def _check_available_engines(self) -> List[str]:
        """Verificar qué engines PDF están disponibles"""
        engines = []
        if PYPDF2_AVAILABLE:
            engines.append('pypdf2')
        if PDFPLUMBER_AVAILABLE:
            engines.append('pdfplumber')
        if PYMUPDF_AVAILABLE:
            engines.append('pymupdf')
        return engines
    
    def extract_text_pypdf2(self, pdf_path: str) -> str:
        """Extraer texto usando PyPDF2"""
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extrayendo con PyPDF2: {e}")
            return ""
    
    def extract_text_pdfplumber(self, pdf_path: str) -> str:
        """Extraer texto usando pdfplumber"""
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extrayendo con pdfplumber: {e}")
            return ""
    
    def extract_text_pymupdf(self, pdf_path: str) -> str:
        """Extraer texto usando PyMuPDF"""
        try:
            text = ""
            doc = fitz.open(pdf_path)
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text += page.get_text() + "\n"
            doc.close()
            return text
        except Exception as e:
            logger.error(f"Error extrayendo con PyMuPDF: {e}")
            return ""
    
    def extract_text(self, pdf_path: str, preferred_engine: str = 'pdfplumber') -> str:
        """Extraer texto del PDF usando el mejor engine disponible"""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")
        
        # Intentar con el engine preferido primero
        if preferred_engine in self.available_engines:
            if preferred_engine == 'pdfplumber' and PDFPLUMBER_AVAILABLE:
                text = self.extract_text_pdfplumber(pdf_path)
                if text.strip():
                    return text
            elif preferred_engine == 'pymupdf' and PYMUPDF_AVAILABLE:
                text = self.extract_text_pymupdf(pdf_path)
                if text.strip():
                    return text
            elif preferred_engine == 'pypdf2' and PYPDF2_AVAILABLE:
                text = self.extract_text_pypdf2(pdf_path)
                if text.strip():
                    return text
        
        # Fallback: intentar con otros engines
        for engine in self.available_engines:
            if engine != preferred_engine:
                try:
                    if engine == 'pdfplumber':
                        text = self.extract_text_pdfplumber(pdf_path)
                    elif engine == 'pymupdf':
                        text = self.extract_text_pymupdf(pdf_path)
                    elif engine == 'pypdf2':
                        text = self.extract_text_pypdf2(pdf_path)
                    
                    if text.strip():
                        logger.info(f"Texto extraído exitosamente con {engine}")
                        return text
                except Exception as e:
                    logger.warning(f"Engine {engine} falló: {e}")
                    continue
        
        raise Exception("No se pudo extraer texto del PDF con ningún engine")
    
    def clean_amount(self, amount_str: str) -> Decimal:
        """Limpiar y convertir string de monto a Decimal"""
        if not amount_str:
            return Decimal('0')
        
        # Remover caracteres no numéricos excepto puntos y comas
        cleaned = re.sub(r'[^\d,.-]', '', str(amount_str))
        
        # Manejar formato argentino (puntos para miles, comas para decimales)
        if ',' in cleaned and '.' in cleaned:
            # Si tiene ambos, asumir formato: 1.234.567,89
            parts = cleaned.split(',')
            if len(parts) == 2:
                integer_part = parts[0].replace('.', '')
                decimal_part = parts[1]
                cleaned = f"{integer_part}.{decimal_part}"
        elif ',' in cleaned:
            # Solo comas - podría ser decimal o miles
            comma_parts = cleaned.split(',')
            if len(comma_parts) == 2 and len(comma_parts[1]) <= 2:
                # Probablemente decimal
                cleaned = cleaned.replace(',', '.')
        
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            logger.warning(f"No se pudo convertir '{amount_str}' a Decimal")
            return Decimal('0')
    
def parse_fima_operations(self, text: str, pdf_source: str = None) -> Dict:
    """Parsear operaciones específicamente para PDFs de FIMA MEJORADO"""
    operations = []
    positions = []
    lines = text.split('\n')
    
    current_fund = None
    parsing_operations = False
    parsing_positions = False
    
    # Patrones específicos mejorados para FIMA
    fund_pattern = r'FONDO - (.+?)(?:\s|$)'
    position_pattern = r'Posicion al (\d{2}/\d{2}/\d{4})'
    date_pattern = r'(\d{2}/\d{2}/\d{4})'
    
    logger.info(f"Iniciando parsing de PDF con {len(lines)} líneas")
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        logger.debug(f"Línea {i}: {line[:100]}...")  # Log primeros 100 caracteres
        
        # Detectar sección de posiciones
        if 'FIMA-FONDOS COMUNES DE INVERSION' in line or re.search(position_pattern, line):
            parsing_positions = True
            parsing_operations = False
            logger.info("Detectada sección de posiciones")
            continue
        
        # Detectar nuevo fondo en operaciones
        fund_match = re.search(fund_pattern, line)
        if fund_match:
            current_fund = fund_match.group(1).strip()
            parsing_operations = True
            parsing_positions = False
            logger.info(f"Detectado fondo: {current_fund}")
            continue
        
        # Parsear posiciones con patrón más específico
        if parsing_positions and not parsing_operations:
            if 'FIMA' in line and line.count('$') >= 2:
                try:
                    # Dividir por $ para obtener las partes
                    parts = [p.strip() for p in line.split('$') if p.strip()]
                    if len(parts) >= 3:
                        # Extraer nombre del fondo (antes del primer número)
                        fund_name_part = parts[0]
                        quantity_str = parts[1]
                        total_value_str = parts[2]

                        # Heurística para separar nombre de fondo y cantidad si vienen juntos
                        match = re.match(r'^(.*?)\s+([\d.,]+)', fund_name_part)
                        if match:
                            fund_name = match.group(1).strip()
                            # La cantidad ya la tenemos de la segunda parte del split
                        else:
                            fund_name = fund_name_part
                        
                        position = {
                            'fund_name': fund_name,
                            'fund_type': 'Money Market' if 'FIMA' in fund_name else 'Otro',
                            'quantity': self.clean_amount(quantity_str),
                            'unit_value': self.clean_amount(total_value_str) / self.clean_amount(quantity_str) if self.clean_amount(quantity_str) != 0 else Decimal(0),
                            'total_value': self.clean_amount(total_value_str)
                        }
                        positions.append(position)
                        logger.info(f"Posición parseada: {fund_name} - {quantity_str} cuotas")
                
                except Exception as e:
                    logger.warning(f"Error parseando posición en línea {i}: {e} - Línea: {line}")
                    continue
        
        # Parsear operaciones con lógica mejorada
        if parsing_operations and current_fund:
            # Verificar si la línea contiene una fecha al inicio
            date_match = re.match(r'^(\d{2}/\d{2}/\d{4})', line)
            if date_match:
                try:
                    parts = line.split()
                    
                    if len(parts) >= 4:
                        date = self._parse_date(parts[0])
                        operation_type = parts[1].upper()
                        
                        # Limpiar y unir las partes restantes para buscar los números
                        remaining_line = ' '.join(parts[2:])
                        
                        # Extraer todos los números de la línea
                        numbers = re.findall(r'[\d.,]+', remaining_line)
                        
                        if len(numbers) >= 3:
                            quantity = self.clean_amount(numbers[0])
                            unit_value = self.clean_amount(numbers[1])
                            total_amount = self.clean_amount(numbers[2])
                            
                            if quantity > 0 and unit_value > 0 and total_amount > 0:
                                operation = {
                                    'date': date,
                                    'operation_type': operation_type,
                                    'fund_name': current_fund,
                                    'fund_type': 'Money Market' if 'FIMA' in current_fund else 'Otro',
                                    'quantity': quantity,
                                    'unit_value': unit_value,
                                    'total_amount': total_amount,
                                    'description': f"{operation_type} - {current_fund}",
                                    'pdf_source': pdf_source
                                }
                                operations.append(operation)
                                logger.info(f"Operación parseada: {date} {operation_type} {quantity} cuotas a ${unit_value} = ${total_amount}")
                            else:
                                logger.warning(f"Valores inválidos en línea {i}: cantidad={quantity}, valor={unit_value}, total={total_amount}")
                        else:
                            logger.warning(f"Insuficientes valores numéricos en línea {i}: {numbers}")
                    else:
                        logger.warning(f"Línea con formato inesperado en línea {i}: {len(parts)} partes - {line}")
                
                except Exception as e:
                    logger.warning(f"Error parseando operación en línea {i}: {e} - Línea: {line}")
                    continue
    
    logger.info(f"Parsing completado: {len(operations)} operaciones, {len(positions)} posiciones")
    
    return {
        'operations': operations,
        'positions': positions
    }
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            } in line and line.count('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }) >= 2:
                    try:
                        # Dividir por $ para obtener las partes
                        parts = line.split('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            })
                        if len(parts) >= 3:
                            # Extraer nombre del fondo (antes del primer número)
                            fund_name_part = parts[0].strip()
                            # Remover números al final del nombre del fondo
                            fund_name_match = re.match(r'^(.+?)\s+([\d.,]+)
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, fund_name_part)
                            if fund_name_match:
                                fund_name = fund_name_match.group(1).strip()
                                quantity_str = fund_name_match.group(2).strip()
                            else:
                                # Fallback: usar todo como nombre del fondo
                                fund_name = fund_name_part
                                quantity_str = '0'
                            
                            # Extraer valor unitario y valor total
                            unit_value_str = parts[1].strip()
                            total_value_str = parts[2].strip()
                            
                            position = {
                                'fund_name': fund_name,
                                'fund_type': 'Money Market' if 'FIMA' in fund_name else 'Otro',
                                'quantity': self.clean_amount(quantity_str),
                                'unit_value': self.clean_amount(unit_value_str),
                                'total_value': self.clean_amount(total_value_str)
                            }
                            positions.append(position)
                            logger.info(f"Posición parseada: {fund_name} - {quantity_str} cuotas")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando posición en línea {i}: {e} - Línea: {line}")
                        continue
            
            # Parsear operaciones con lógica mejorada
            if parsing_operations and current_fund:
                # Verificar si la línea contiene una fecha al inicio
                date_match = re.match(r'^(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    try:
                        # Dividir la línea por espacios/tabulaciones, manteniendo los signos $
                        parts = line.split()
                        
                        if len(parts) >= 6:  # Necesitamos al menos fecha, tipo, cantidad, $, valor, $, monto, fecha
                            date = self._parse_date(parts[0])
                            operation_type = parts[1].upper()
                            
                            # Encontrar las partes numéricas (buscar patrones con $)
                            numeric_parts = []
                            for j, part in enumerate(parts[2:], 2):  # Empezar desde el índice 2
                                if '
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            } in part or re.match(r'^[\d.,]+
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, part):
                                    clean_part = part.replace('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, '').strip()
                                    if clean_part and clean_part != ',':
                                        numeric_parts.append(clean_part)
                            
                            # Necesitamos al menos 3 valores numéricos: cantidad, valor unitario, monto total
                            if len(numeric_parts) >= 3:
                                quantity = self.clean_amount(numeric_parts[0])
                                unit_value = self.clean_amount(numeric_parts[1])
                                total_amount = self.clean_amount(numeric_parts[2])
                                
                                # Validar que los valores sean razonables
                                if quantity > 0 and unit_value > 0 and total_amount > 0:
                                    operation = {
                                        'date': date,
                                        'operation_type': operation_type,
                                        'fund_name': current_fund,
                                        'fund_type': 'Money Market' if 'FIMA' in current_fund else 'Otro',
                                        'quantity': quantity,
                                        'unit_value': unit_value,
                                        'total_amount': total_amount,
                                        'description': f"{operation_type} - {current_fund}",
                                        'pdf_source': pdf_source
                                    }
                                    operations.append(operation)
                                    logger.info(f"Operación parseada: {date} {operation_type} {quantity} cuotas a ${unit_value} = ${total_amount}")
                                else:
                                    logger.warning(f"Valores inválidos en línea {i}: cantidad={quantity}, valor={unit_value}, total={total_amount}")
                            else:
                                logger.warning(f"Insuficientes valores numéricos en línea {i}: {numeric_parts}")
                        else:
                            logger.warning(f"Línea con formato inesperado en línea {i}: {len(parts)} partes - {line}")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando operación en línea {i}: {e} - Línea: {line}")
                        continue
        
        logger.info(f"Parsing completado: {len(operations)} operaciones, {len(positions)} posiciones")
        
        return {
            'operations': operations,
            'positions': positions
        }
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }) >= 2:
                    try:
                        # Dividir por $ para obtener las partes
                        parts = [p.strip() for p in line.split('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            } in line and line.count('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }) >= 2:
                    try:
                        # Dividir por $ para obtener las partes
                        parts = line.split('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            })
                        if len(parts) >= 3:
                            # Extraer nombre del fondo (antes del primer número)
                            fund_name_part = parts[0].strip()
                            # Remover números al final del nombre del fondo
                            fund_name_match = re.match(r'^(.+?)\s+([\d.,]+)
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, fund_name_part)
                            if fund_name_match:
                                fund_name = fund_name_match.group(1).strip()
                                quantity_str = fund_name_match.group(2).strip()
                            else:
                                # Fallback: usar todo como nombre del fondo
                                fund_name = fund_name_part
                                quantity_str = '0'
                            
                            # Extraer valor unitario y valor total
                            unit_value_str = parts[1].strip()
                            total_value_str = parts[2].strip()
                            
                            position = {
                                'fund_name': fund_name,
                                'fund_type': 'Money Market' if 'FIMA' in fund_name else 'Otro',
                                'quantity': self.clean_amount(quantity_str),
                                'unit_value': self.clean_amount(unit_value_str),
                                'total_value': self.clean_amount(total_value_str)
                            }
                            positions.append(position)
                            logger.info(f"Posición parseada: {fund_name} - {quantity_str} cuotas")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando posición en línea {i}: {e} - Línea: {line}")
                        continue
            
            # Parsear operaciones con lógica mejorada
            if parsing_operations and current_fund:
                # Verificar si la línea contiene una fecha al inicio
                date_match = re.match(r'^(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    try:
                        # Dividir la línea por espacios/tabulaciones, manteniendo los signos $
                        parts = line.split()
                        
                        if len(parts) >= 6:  # Necesitamos al menos fecha, tipo, cantidad, $, valor, $, monto, fecha
                            date = self._parse_date(parts[0])
                            operation_type = parts[1].upper()
                            
                            # Encontrar las partes numéricas (buscar patrones con $)
                            numeric_parts = []
                            for j, part in enumerate(parts[2:], 2):  # Empezar desde el índice 2
                                if '
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            } in part or re.match(r'^[\d.,]+
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, part):
                                    clean_part = part.replace('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, '').strip()
                                    if clean_part and clean_part != ',':
                                        numeric_parts.append(clean_part)
                            
                            # Necesitamos al menos 3 valores numéricos: cantidad, valor unitario, monto total
                            if len(numeric_parts) >= 3:
                                quantity = self.clean_amount(numeric_parts[0])
                                unit_value = self.clean_amount(numeric_parts[1])
                                total_amount = self.clean_amount(numeric_parts[2])
                                
                                # Validar que los valores sean razonables
                                if quantity > 0 and unit_value > 0 and total_amount > 0:
                                    operation = {
                                        'date': date,
                                        'operation_type': operation_type,
                                        'fund_name': current_fund,
                                        'fund_type': 'Money Market' if 'FIMA' in current_fund else 'Otro',
                                        'quantity': quantity,
                                        'unit_value': unit_value,
                                        'total_amount': total_amount,
                                        'description': f"{operation_type} - {current_fund}",
                                        'pdf_source': pdf_source
                                    }
                                    operations.append(operation)
                                    logger.info(f"Operación parseada: {date} {operation_type} {quantity} cuotas a ${unit_value} = ${total_amount}")
                                else:
                                    logger.warning(f"Valores inválidos en línea {i}: cantidad={quantity}, valor={unit_value}, total={total_amount}")
                            else:
                                logger.warning(f"Insuficientes valores numéricos en línea {i}: {numeric_parts}")
                        else:
                            logger.warning(f"Línea con formato inesperado en línea {i}: {len(parts)} partes - {line}")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando operación en línea {i}: {e} - Línea: {line}")
                        continue
        
        logger.info(f"Parsing completado: {len(operations)} operaciones, {len(positions)} posiciones")
        
        return {
            'operations': operations,
            'positions': positions
        }
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }) if p.strip()]
                        if len(parts) >= 3:
                            # Extraer nombre del fondo (antes del primer número)
                            fund_name_part = parts[0]
                            quantity_str = parts[1]
                            total_value_str = parts[2]

                            # Heurística para separar nombre de fondo y cantidad si vienen juntos
                            match = re.match(r'^(.*?)\s+([\d.,]+)
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            } in line and line.count('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }) >= 2:
                    try:
                        # Dividir por $ para obtener las partes
                        parts = line.split('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            })
                        if len(parts) >= 3:
                            # Extraer nombre del fondo (antes del primer número)
                            fund_name_part = parts[0].strip()
                            # Remover números al final del nombre del fondo
                            fund_name_match = re.match(r'^(.+?)\s+([\d.,]+)
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, fund_name_part)
                            if fund_name_match:
                                fund_name = fund_name_match.group(1).strip()
                                quantity_str = fund_name_match.group(2).strip()
                            else:
                                # Fallback: usar todo como nombre del fondo
                                fund_name = fund_name_part
                                quantity_str = '0'
                            
                            # Extraer valor unitario y valor total
                            unit_value_str = parts[1].strip()
                            total_value_str = parts[2].strip()
                            
                            position = {
                                'fund_name': fund_name,
                                'fund_type': 'Money Market' if 'FIMA' in fund_name else 'Otro',
                                'quantity': self.clean_amount(quantity_str),
                                'unit_value': self.clean_amount(unit_value_str),
                                'total_value': self.clean_amount(total_value_str)
                            }
                            positions.append(position)
                            logger.info(f"Posición parseada: {fund_name} - {quantity_str} cuotas")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando posición en línea {i}: {e} - Línea: {line}")
                        continue
            
            # Parsear operaciones con lógica mejorada
            if parsing_operations and current_fund:
                # Verificar si la línea contiene una fecha al inicio
                date_match = re.match(r'^(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    try:
                        # Dividir la línea por espacios/tabulaciones, manteniendo los signos $
                        parts = line.split()
                        
                        if len(parts) >= 6:  # Necesitamos al menos fecha, tipo, cantidad, $, valor, $, monto, fecha
                            date = self._parse_date(parts[0])
                            operation_type = parts[1].upper()
                            
                            # Encontrar las partes numéricas (buscar patrones con $)
                            numeric_parts = []
                            for j, part in enumerate(parts[2:], 2):  # Empezar desde el índice 2
                                if '
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            } in part or re.match(r'^[\d.,]+
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, part):
                                    clean_part = part.replace('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, '').strip()
                                    if clean_part and clean_part != ',':
                                        numeric_parts.append(clean_part)
                            
                            # Necesitamos al menos 3 valores numéricos: cantidad, valor unitario, monto total
                            if len(numeric_parts) >= 3:
                                quantity = self.clean_amount(numeric_parts[0])
                                unit_value = self.clean_amount(numeric_parts[1])
                                total_amount = self.clean_amount(numeric_parts[2])
                                
                                # Validar que los valores sean razonables
                                if quantity > 0 and unit_value > 0 and total_amount > 0:
                                    operation = {
                                        'date': date,
                                        'operation_type': operation_type,
                                        'fund_name': current_fund,
                                        'fund_type': 'Money Market' if 'FIMA' in current_fund else 'Otro',
                                        'quantity': quantity,
                                        'unit_value': unit_value,
                                        'total_amount': total_amount,
                                        'description': f"{operation_type} - {current_fund}",
                                        'pdf_source': pdf_source
                                    }
                                    operations.append(operation)
                                    logger.info(f"Operación parseada: {date} {operation_type} {quantity} cuotas a ${unit_value} = ${total_amount}")
                                else:
                                    logger.warning(f"Valores inválidos en línea {i}: cantidad={quantity}, valor={unit_value}, total={total_amount}")
                            else:
                                logger.warning(f"Insuficientes valores numéricos en línea {i}: {numeric_parts}")
                        else:
                            logger.warning(f"Línea con formato inesperado en línea {i}: {len(parts)} partes - {line}")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando operación en línea {i}: {e} - Línea: {line}")
                        continue
        
        logger.info(f"Parsing completado: {len(operations)} operaciones, {len(positions)} posiciones")
        
        return {
            'operations': operations,
            'positions': positions
        }
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, fund_name_part)
                            if match:
                                fund_name = match.group(1).strip()
                                # La cantidad ya la tenemos de la segunda parte del split
                            else:
                                fund_name = fund_name_part
                            
                            position = {
                                'fund_name': fund_name,
                                'fund_type': 'Money Market' if 'FIMA' in fund_name else 'Otro',
                                'quantity': self.clean_amount(quantity_str),
                                'unit_value': self.clean_amount(total_value_str) / self.clean_amount(quantity_str) if self.clean_amount(quantity_str) != 0 else Decimal(0),
                                'total_value': self.clean_amount(total_value_str)
                            }
                            positions.append(position)
                            logger.info(f"Posición parseada: {fund_name} - {quantity_str} cuotas")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando posición en línea {i}: {e} - Línea: {line}")
                        continue
            
            # Parsear operaciones con lógica mejorada
            if parsing_operations and current_fund:
                # Verificar si la línea contiene una fecha al inicio
                date_match = re.match(r'^(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    try:
                        parts = line.split()
                        
                        if len(parts) >= 4:
                            date = self._parse_date(parts[0])
                            operation_type = parts[1].upper()
                            
                            # Limpiar y unir las partes restantes para buscar los números
                            remaining_line = ' '.join(parts[2:])
                            
                            # Extraer todos los números de la línea
                            numbers = re.findall(r'[\d.,]+', remaining_line)
                            
                            if len(numbers) >= 3:
                                quantity = self.clean_amount(numbers[0])
                                unit_value = self.clean_amount(numbers[1])
                                total_amount = self.clean_amount(numbers[2])
                                
                                if quantity > 0 and unit_value > 0 and total_amount > 0:
                                    operation = {
                                        'date': date,
                                        'operation_type': operation_type,
                                        'fund_name': current_fund,
                                        'fund_type': 'Money Market' if 'FIMA' in current_fund else 'Otro',
                                        'quantity': quantity,
                                        'unit_value': unit_value,
                                        'total_amount': total_amount,
                                        'description': f"{operation_type} - {current_fund}",
                                        'pdf_source': pdf_source
                                    }
                                    operations.append(operation)
                                    logger.info(f"Operación parseada: {date} {operation_type} {quantity} cuotas a ${unit_value} = ${total_amount}")
                                else:
                                    logger.warning(f"Valores inválidos en línea {i}: cantidad={quantity}, valor={unit_value}, total={total_amount}")
                            else:
                                logger.warning(f"Insuficientes valores numéricos en línea {i}: {numbers}")
                        else:
                            logger.warning(f"Línea con formato inesperado en línea {i}: {len(parts)} partes - {line}")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando operación en línea {i}: {e} - Línea: {line}")
                        continue
        
        logger.info(f"Parsing completado: {len(operations)} operaciones, {len(positions)} posiciones")
        
        return {
            'operations': operations,
            'positions': positions
        }
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            } in line and line.count('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }) >= 2:
                    try:
                        # Dividir por $ para obtener las partes
                        parts = line.split('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            })
                        if len(parts) >= 3:
                            # Extraer nombre del fondo (antes del primer número)
                            fund_name_part = parts[0].strip()
                            # Remover números al final del nombre del fondo
                            fund_name_match = re.match(r'^(.+?)\s+([\d.,]+)
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, fund_name_part)
                            if fund_name_match:
                                fund_name = fund_name_match.group(1).strip()
                                quantity_str = fund_name_match.group(2).strip()
                            else:
                                # Fallback: usar todo como nombre del fondo
                                fund_name = fund_name_part
                                quantity_str = '0'
                            
                            # Extraer valor unitario y valor total
                            unit_value_str = parts[1].strip()
                            total_value_str = parts[2].strip()
                            
                            position = {
                                'fund_name': fund_name,
                                'fund_type': 'Money Market' if 'FIMA' in fund_name else 'Otro',
                                'quantity': self.clean_amount(quantity_str),
                                'unit_value': self.clean_amount(unit_value_str),
                                'total_value': self.clean_amount(total_value_str)
                            }
                            positions.append(position)
                            logger.info(f"Posición parseada: {fund_name} - {quantity_str} cuotas")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando posición en línea {i}: {e} - Línea: {line}")
                        continue
            
            # Parsear operaciones con lógica mejorada
            if parsing_operations and current_fund:
                # Verificar si la línea contiene una fecha al inicio
                date_match = re.match(r'^(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    try:
                        # Dividir la línea por espacios/tabulaciones, manteniendo los signos $
                        parts = line.split()
                        
                        if len(parts) >= 6:  # Necesitamos al menos fecha, tipo, cantidad, $, valor, $, monto, fecha
                            date = self._parse_date(parts[0])
                            operation_type = parts[1].upper()
                            
                            # Encontrar las partes numéricas (buscar patrones con $)
                            numeric_parts = []
                            for j, part in enumerate(parts[2:], 2):  # Empezar desde el índice 2
                                if '
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            } in part or re.match(r'^[\d.,]+
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, part):
                                    clean_part = part.replace('
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }, '').strip()
                                    if clean_part and clean_part != ',':
                                        numeric_parts.append(clean_part)
                            
                            # Necesitamos al menos 3 valores numéricos: cantidad, valor unitario, monto total
                            if len(numeric_parts) >= 3:
                                quantity = self.clean_amount(numeric_parts[0])
                                unit_value = self.clean_amount(numeric_parts[1])
                                total_amount = self.clean_amount(numeric_parts[2])
                                
                                # Validar que los valores sean razonables
                                if quantity > 0 and unit_value > 0 and total_amount > 0:
                                    operation = {
                                        'date': date,
                                        'operation_type': operation_type,
                                        'fund_name': current_fund,
                                        'fund_type': 'Money Market' if 'FIMA' in current_fund else 'Otro',
                                        'quantity': quantity,
                                        'unit_value': unit_value,
                                        'total_amount': total_amount,
                                        'description': f"{operation_type} - {current_fund}",
                                        'pdf_source': pdf_source
                                    }
                                    operations.append(operation)
                                    logger.info(f"Operación parseada: {date} {operation_type} {quantity} cuotas a ${unit_value} = ${total_amount}")
                                else:
                                    logger.warning(f"Valores inválidos en línea {i}: cantidad={quantity}, valor={unit_value}, total={total_amount}")
                            else:
                                logger.warning(f"Insuficientes valores numéricos en línea {i}: {numeric_parts}")
                        else:
                            logger.warning(f"Línea con formato inesperado en línea {i}: {len(parts)} partes - {line}")
                    
                    except Exception as e:
                        logger.warning(f"Error parseando operación en línea {i}: {e} - Línea: {line}")
                        continue
        
        logger.info(f"Parsing completado: {len(operations)} operaciones, {len(positions)} posiciones")
        
        return {
            'operations': operations,
            'positions': positions
        }
    
    def calculate_peps_analysis(self, operations: List[Dict]) -> Dict:
        """Calcular análisis PEPS para cada fondo"""
        funds_analysis = {}
        
        # Agrupar operaciones por fondo
        funds_operations = {}
        for op in operations:
            fund_name = op['fund_name']
            if fund_name not in funds_operations:
                funds_operations[fund_name] = []
            funds_operations[fund_name].append(op)
        
        # Calcular PEPS para cada fondo
        for fund_name, fund_ops in funds_operations.items():
            # Ordenar operaciones por fecha
            fund_ops.sort(key=lambda x: x['date'])
            
            peps_calc = PEPSCalculator()
            fund_analysis = {
                'fund_name': fund_name,
                'total_purchases': Decimal('0'),
                'total_sales': Decimal('0'),
                'total_gain_loss': Decimal('0'),
                'operations_detail': [],
                'current_position': {}
            }
            
            for op in fund_ops:
                if op['operation_type'] in ['SUSCRIPCION', 'COMPRA']:
                    # Agregar compra al PEPS
                    peps_calc.add_purchase(op['date'], op['quantity'], op['unit_value'])
                    fund_analysis['total_purchases'] += op['total_amount']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'COMPRA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount']
                    })
                    
                elif op['operation_type'] in ['RESCATE', 'VENTA']:
                    # Calcular venta con PEPS
                    peps_result = peps_calc.calculate_sale(
                        op['date'], op['quantity'], op['unit_value']
                    )
                    
                    fund_analysis['total_sales'] += op['total_amount']
                    fund_analysis['total_gain_loss'] += peps_result['gain_loss']
                    
                    fund_analysis['operations_detail'].append({
                        'date': op['date'],
                        'type': 'VENTA',
                        'quantity': op['quantity'],
                        'unit_price': op['unit_value'],
                        'total': op['total_amount'],
                        'cost_basis': peps_result['cost_basis'],
                        'gain_loss': peps_result['gain_loss'],
                        'used_lots': peps_result.get('used_lots', [])
                    })
            
            # Posición actual
            fund_analysis['current_position'] = peps_calc.get_current_position()
            funds_analysis[fund_name] = fund_analysis
        
        return funds_analysis
    
    def _parse_date(self, date_str: str) -> str:
        """Convertir fecha a formato ISO"""
        try:
            # Intentar formato DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validar año
                    if len(year) == 2:
                        year = '20' + year if int(year) < 50 else '19' + year
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        
        return date_str
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Procesar PDF completo y retornar operaciones, posiciones y análisis PEPS"""
        try:
            text = self.extract_text(pdf_path)
            if not text.strip():
                raise Exception("No se pudo extraer texto del PDF")
            
            # Parsear con método específico para FIMA
            parsed_data = self.parse_fima_operations(text, os.path.basename(pdf_path))
            operations = parsed_data['operations']
            positions = parsed_data['positions']
            
            # Calcular análisis PEPS
            peps_analysis = self.calculate_peps_analysis(operations)
            
            return {
                'success': True,
                'operations': operations,
                'positions': positions,
                'peps_analysis': peps_analysis,
                'total_operations': len(operations),
                'total_positions': len(positions),
                'pdf_source': os.path.basename(pdf_path)
            }
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations': [],
                'positions': [],
                'peps_analysis': {}
            }