# 📄 Procesador PDF Financiero

**Aplicación profesional para procesar extractos PDF de FIMA (Fondos de Inversión de Money Market Argentinos) con máxima precisión decimal y gestión completa de operaciones financieras.**

## 🚀 Características Principales

### ✅ Procesamiento PDF Avanzado
- **Múltiples engines**: PyPDF2, pdfplumber, PyMuPDF con fallback automático
- **Extracción inteligente** de operaciones y posiciones
- **Detección automática** de múltiples fondos en un mismo PDF
- **Precisión decimal** de 28 dígitos usando `Decimal`

### 💾 Base de Datos SQLite Integrada
- **Persistencia local** sin dependencias externas
- **Historial completo** de todas las operaciones
- **Posiciones actuales** del portfolio
- **Configuración personalizable** por fondo

### 📊 Exportación Excel Profesional
- **Reportes completos** con múltiples hojas
- **Resumen ejecutivo** con estadísticas
- **Formato profesional** con colores y estilos
- **Filtros por tipo** de fondo
- **Exportación CSV** alternativa

### 🖥️ Interfaz Gráfica Intuitiva
- **Diseño moderno** con pestañas organizadas
- **Vista en tiempo real** de datos
- **Procesamiento asíncrono** sin bloqueos
- **Vista previa** del contenido PDF

## 📁 Estructura del Proyecto

```
pdf-financial-processor-python/
├── 📄 main.py              # Punto de entrada principal
├── 🔍 pdf_processor.py     # Lógica de extracción PDF
├── 💾 database.py          # Gestor SQLite con precisión decimal
├── 📊 excel_exporter.py    # Exportación Excel profesional
├── 🖥️ gui.py               # Interfaz gráfica Tkinter
├── ⚙️ config.py           # Configuración global
├── 📋 requirements.txt     # Dependencias Python
├── 🔨 build.bat           # Script de compilación
├── 📚 README.md           # Esta documentación
└── 📁 data/               # Archivos generados
    ├── financial_data.db  # Base de datos SQLite
    └── exports/           # Archivos exportados
```

## 🛠️ Instalación y Configuración

### 1️⃣ Requisitos del Sistema
- **Python 3.8+** (recomendado 3.9 o superior)
- **Windows 10/11** (compatible con Linux/macOS)
- **4 GB RAM mínimo** (8 GB recomendado)
- **100 MB espacio libre** en disco

### 2️⃣ Instalación de Dependencias

```bash
# Clonar o descargar el proyecto
git clone <repositorio> pdf-financial-processor-python
cd pdf-financial-processor-python

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3️⃣ Verificación de Instalación

```bash
# Verificar que todas las librerías están disponibles
python -c "import PyPDF2, pdfplumber, fitz, pandas, openpyxl; print('✅ Todas las dependencias están instaladas')"
```

## 🚀 Uso de la Aplicación

### Modo Desarrollo
```bash
python main.py
```

### Modo Ejecutable
```bash
# Compilar ejecutable
build.bat

# Ejecutar
dist/ProcesadorPDF_Financiero.exe
```

## 📖 Guía de Usuario

### 1. **Procesar PDF**
1. Ir a la pestaña "📄 Procesar PDF"
2. Hacer clic en "Examinar..." y seleccionar archivo PDF
3. Elegir engine PDF (recomendado: pdfplumber)
4. Hacer clic en "🔄 Procesar PDF"
5. Revisar resultados en el área de texto

### 2. **Gestionar Operaciones**
1. Ir a "📊 Operaciones"
2. Filtrar por tipo de fondo si es necesario
3. Ver historial completo de operaciones
4. Eliminar operaciones erróneas si es necesario

### 3. **Ver Posiciones**
1. Ir a "💼 Posiciones"
2. Ver resumen del portfolio
3. Analizar posiciones actuales por fondo

### 4. **Configurar Fondos**
1. Ir a "⚙️ Configuración"
2. Agregar nuevos fondos con saldos iniciales
3. Clasificar por tipo de fondo
4. Ver fondos configurados

### 5. **Exportar Datos**
1. Ir a "📤 Exportar"
2. Seleccionar filtros (tipo de fondo, formato)
3. Elegir "📊 Reporte Completo" o "📄 Solo Operaciones"
4. El archivo se guarda automáticamente

## ⚙️ Configuración Avanzada

### Tipos de Fondos Soportados
- **Renta Fija**: Bonos, obligaciones negociables
- **Renta Variable**: Acciones, equity funds
- **Mixto**: Fondos balanceados
- **Money Market**: Liquidez, pesos
- **Obligaciones Negociables**: ONs corporativas
- **Otros**: Clasificación personalizada

### Precisión Decimal
La aplicación usa `Decimal` con 28 dígitos de precisión para:
- ✅ Cálculos financieros exactos
- ✅ Sin errores de redondeo de floating point
- ✅ Compatibilidad con sistemas contables

### Patrones de Reconocimiento
El sistema reconoce automáticamente:
- **Fechas**: DD/MM/YYYY, DD/MM/YY
- **Operaciones**: Suscripción, Rescate, Transferencia
- **Montos**: Formato argentino (1.234.567,89)
- **Fondos**: Por palabras clave (FIMA, FCI, FCIC)

## 🔧 Compilación de Ejecutable

### Usando build.bat (Windows)
```cmd
build.bat
```

### Manual con PyInstaller
```bash
pyinstaller --onefile --windowed \
    --name="ProcesadorPDF_Financiero" \
    --hidden-import=PyPDF2 \
    --hidden-import=pdfplumber \
    --hidden-import=fitz \
    --hidden-import=pandas \
    --hidden-import=openpyxl \
    --exclude-module=matplotlib \
    --clean \
    main.py
```

### Optimizaciones del Ejecutable
- **--onefile**: Ejecutable único sin carpetas
- **--windowed**: Sin consola DOS
- **--exclude-module**: Reduce tamaño eliminando módulos innecesarios
- **Tamaño esperado**: 15-25 MB

## 🧪 Testing y Validación

### Datos de Prueba
Crea PDFs de prueba con:
- Operaciones de suscripción y rescate
- Múltiples fondos en un mismo documento
- Diferentes formatos de fecha y números
- Caracteres especiales

### Validación de Precisión
```python
from decimal import Decimal
# Verificar que los cálculos son exactos
cantidad = Decimal('1234.56789012')
valor = Decimal('987.65432101')
total = cantidad * valor
print(f"Total exacto: {total}")  # Sin errores de redondeo
```

## 📝 Logs y Debugging

### Archivo de Log
- **Ubicación**: `financial_processor.log`
- **Nivel**: INFO por defecto
- **Contenido**: Errores, operaciones exitosas, estadísticas

### Debug Mode
```python
# En config.py, cambiar nivel de logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Solución de Problemas Comunes

### ❌ "Error: No se pudo extraer texto del PDF"
**Solución**: 
- Verificar que el PDF no esté protegido
- Probar con diferentes engines PDF
- Algunos PDFs escaneados necesitan OCR

### ❌ "Error: Dependencias faltantes"
**Solución**:
```bash
pip install --upgrade PyPDF2 pdfplumber pymupdf pandas openpyxl
```

### ❌ "Error: No se pueden guardar operaciones"
**Solución**: 
- Verificar permisos de escritura en carpeta `data/`
- Eliminar `financial_data.db` para recrear la base

### ❌ "Ejecutable muy lento al iniciar"
**Normal**: La primera ejecución puede tardar 10-30 segundos mientras descomprime las librerías.

## 🎯 Roadmap y Mejoras Futuras

### v1.1.0 (Planeado)
- [ ] Soporte para OCR (PDFs escaneados)
- [ ] Importación de múltiples PDFs batch
- [ ] Dashboard con gráficos
- [ ] API REST opcional

### v1.2.0 (Planeado)
- [ ] Detección automática de fondos por IA
- [ ] Exportación a otros formatos (JSON, XML)
- [ ] Sincronización con servicios en la nube
- [ ] Modo portable sin instalación

## 📄 Licencia

Este proyecto está bajo una licencia de uso interno. No redistribuir sin autorización.

---

## 🆘 Soporte

Para reportar bugs o solicitar funcionalidades:

1. **Verificar logs**: Revisar `financial_processor.log`
2. **Reproducir error**: Documentar pasos exactos
3. **Información del sistema**: SO, versión Python, archivo PDF problema
4. **Contacto**: [Información de contacto del desarrollador]

---

**💡 ¡Procesa tus PDFs financieros con confianza y precisión profesional!**