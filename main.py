#!/usr/bin/env python3
"""
Procesador PDF Financiero - Punto de entrada principal
Aplicación para procesar extractos PDF de FIMA y gestionar operaciones financieras
"""
import sys
import os
import tkinter as tk
from tkinter import messagebox
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('financial_processor.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def check_dependencies():
    """Verificar que todas las dependencias estén instaladas"""
    missing_deps = []
    
    try:
        import PyPDF2
    except ImportError:
        missing_deps.append('PyPDF2')
    
    try:
        import pdfplumber
    except ImportError:
        missing_deps.append('pdfplumber')
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        missing_deps.append('PyMuPDF')
    
    try:
        import pandas
    except ImportError:
        missing_deps.append('pandas')
    
    try:
        import openpyxl
    except ImportError:
        missing_deps.append('openpyxl')
    
    if missing_deps:
        error_msg = f"""DEPENDENCIAS FALTANTES:

Las siguientes librerías no están instaladas:
{', '.join(missing_deps)}

Para instalarlas, ejecuta:
pip install {' '.join(missing_deps)}

O instala todas las dependencias con:
pip install -r requirements.txt"""
        
        logger.error(error_msg)
        
        # Mostrar error en GUI si es posible
        try:
            root = tk.Tk()
            root.withdraw()  # Ocultar ventana principal
            messagebox.showerror("Dependencias Faltantes", error_msg)
            root.destroy()
        except:
            print(error_msg)
        
        return False
    
    return True

def setup_directories():
    """Crear directorios necesarios si no existen"""
    try:
        from config import DATA_DIR, EXPORT_DIR
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(EXPORT_DIR, exist_ok=True)
        logger.info(f"Directorios configurados: {DATA_DIR}, {EXPORT_DIR}")
    except Exception as e:
        logger.error(f"Error configurando directorios: {e}")
        return False
    return True

def initialize_database():
    """Inicializar base de datos"""
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        logger.info("Base de datos inicializada correctamente")
        return True
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        return False

def main():
    """Función principal de la aplicación"""
    logger.info("=== INICIANDO PROCESADOR PDF FINANCIERO ===")
    
    # Verificar dependencias
    if not check_dependencies():
        logger.error("No se pueden cargar las dependencias necesarias")
        return 1
    
    # Configurar directorios
    if not setup_directories():
        logger.error("Error configurando directorios")
        return 1
    
    # Inicializar base de datos
    if not initialize_database():
        logger.error("Error inicializando base de datos")
        return 1
    
    try:
        # Importar y iniciar GUI
        from gui import FinancialProcessorGUI
        
        # Crear ventana principal
        root = tk.Tk()
        
        # Configurar manejo de errores no capturados
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            
            error_msg = f"Error no controlado: {exc_type.__name__}: {exc_value}"
            logger.error(error_msg, exc_info=(exc_type, exc_value, exc_traceback))
            
            messagebox.showerror("Error Inesperado", 
                               f"{error_msg}\n\nVer log para más detalles.")
        
        sys.excepthook = handle_exception
        
        # Inicializar aplicación
        app = FinancialProcessorGUI(root)
        
        logger.info("Aplicación iniciada correctamente")
        
        # Configurar cierre de aplicación
        def on_closing():
            logger.info("Cerrando aplicación...")
            root.quit()
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Iniciar loop principal
        root.mainloop()
        
        logger.info("=== APLICACIÓN CERRADA ===")
        return 0
        
    except ImportError as e:
        error_msg = f"Error importando módulos: {e}"
        logger.error(error_msg)
        
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error de Importación", error_msg)
            root.destroy()
        except:
            print(error_msg)
        
    except Exception as e:
        error_msg = f"Error crítico en la aplicación: {e}"
        logger.error(error_msg, exc_info=True)
        
        try:
            messagebox.showerror("Error Crítico", error_msg)
        except:
            print(error_msg)
        
        return 1

if __name__ == "__main__":
    sys.exit(main())