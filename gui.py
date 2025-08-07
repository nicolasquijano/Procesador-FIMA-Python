"""
Interfaz Gráfica Principal del Procesador PDF Financiero
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from datetime import datetime
import os

from database import DatabaseManager
from pdf_processor import PDFProcessor
from config import APP_CONFIG, FUND_TYPES

class FinancialProcessorGUI:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        
        # Inicializar componentes
        self.db = DatabaseManager()
        self.pdf_processor = PDFProcessor()
        
        # Variables de estado
        self.status_var = tk.StringVar()
        self.status_var.set("Listo")
        
        # Datos actuales
        self.current_operations = []
        self.current_positions = []
        self.current_configs = []
        self.peps_analysis_data = {}
        
        # Crear interface
        self.create_menu()
        self.create_notebook()
        self.create_status_bar()
        
        # Cargar datos iniciales
        self.refresh_data()
        
    def setup_window(self):
        """Configurar ventana principal"""
        self.root.title(f"{APP_CONFIG['app_name']} v{APP_CONFIG['version']}")
        self.root.geometry(APP_CONFIG['window_size'])
        
        # Configurar estilo
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configurar icono (opcional)
        try:
            self.root.iconbitmap('assets/icon.ico')
        except:
            pass
    
    def create_menu(self):
        """Crear barra de menú"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menú Archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Procesar PDF...", command=self.select_and_process_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Exportar Excel...", command=self.export_excel_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.root.quit)
        
        # Menú Herramientas
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Herramientas", menu=tools_menu)
        tools_menu.add_command(label="Actualizar datos", command=self.refresh_data)
        tools_menu.add_command(label="Ver estadísticas", command=self.show_stats)
        
        # Menú Ayuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de", command=self.show_about)
    
    def create_notebook(self):
        """Crear pestañas principales"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
        
        # Crear pestañas
        self.create_pdf_tab()
        self.create_operations_tab()
        self.create_positions_tab()
        self.create_config_tab()
        self.create_export_tab()
        self.create_peps_tab()
    
    def create_pdf_tab(self):
        """Pestaña de procesamiento PDF"""
        pdf_frame = ttk.Frame(self.notebook)
        self.notebook.add(pdf_frame, text="📄 Procesar PDF")
        
        # Frame superior para selección de archivo
        file_frame = ttk.LabelFrame(pdf_frame, text="Selección de Archivo")
        file_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.pdf_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.pdf_path_var, width=60).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(file_frame, text="Examinar...", command=self.browse_pdf).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Frame para configuración de procesamiento
        config_frame = ttk.LabelFrame(pdf_frame, text="Configuración")
        config_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(config_frame, text="Engine PDF:").pack(side=tk.LEFT, padx=5)
        self.pdf_engine_var = tk.StringVar(value='pdfplumber')
        engine_combo = ttk.Combobox(config_frame, textvariable=self.pdf_engine_var, 
                                   values=self.pdf_processor.available_engines, 
                                   state='readonly', width=15)
        engine_combo.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(config_frame, text="🔄 Procesar PDF", 
                  command=self.process_pdf_async).pack(side=tk.LEFT, padx=20, pady=5)
        
        # Frame para resultados
        results_frame = ttk.LabelFrame(pdf_frame, text="Resultados")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Área de texto con scroll
        text_frame = tk.Frame(results_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.pdf_results_text = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.pdf_results_text.yview)
        self.pdf_results_text.configure(yscrollcommand=scrollbar.set)
        
        self.pdf_results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_operations_tab(self):
        """Pestaña de operaciones"""
        ops_frame = ttk.Frame(self.notebook)
        self.notebook.add(ops_frame, text="📊 Operaciones")
        
        # Frame de filtros
        filter_frame = ttk.LabelFrame(ops_frame, text="Filtros")
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(filter_frame, text="Tipo de Fondo:").pack(side=tk.LEFT, padx=5)
        self.ops_filter_var = tk.StringVar(value="Todos")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.ops_filter_var,
                                   values=["Todos"] + FUND_TYPES, state='readonly', width=15)
        filter_combo.pack(side=tk.LEFT, padx=5, pady=5)
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_operations())
        
        ttk.Button(filter_frame, text="🔄 Actualizar", 
                  command=self.refresh_operations).pack(side=tk.LEFT, padx=20)
        
        # TreeView para operaciones
        tree_frame = ttk.Frame(ops_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ('ID', 'Fecha', 'Operación', 'Fondo', 'Cuotas', 'Valor Unit.', 'Total')
        self.operations_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        # Configurar columnas
        for col in columns:
            self.operations_tree.heading(col, text=col)
            if col == 'ID':
                self.operations_tree.column(col, width=50, anchor=tk.CENTER)
            elif col in ['Cuotas', 'Valor Unit.', 'Total']:
                self.operations_tree.column(col, width=120, anchor=tk.E)
            else:
                self.operations_tree.column(col, width=100)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.operations_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.operations_tree.xview)
        self.operations_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.operations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Menú contextual
        self.create_operations_context_menu()
    
    def create_positions_tab(self):
        """Pestaña de posiciones"""
        pos_frame = ttk.Frame(self.notebook)
        self.notebook.add(pos_frame, text="💼 Posiciones")
        
        # TreeView para posiciones
        columns = ('Fondo', 'Tipo', 'Cuotas', 'Valor Unit.', 'Valor Total')
        self.positions_tree = ttk.Treeview(pos_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.positions_tree.heading(col, text=col)
            if col in ['Cuotas', 'Valor Unit.', 'Valor Total']:
                self.positions_tree.column(col, width=150, anchor=tk.E)
            else:
                self.positions_tree.column(col, width=200)
        
        # Scrollbar
        pos_scrollbar = ttk.Scrollbar(pos_frame, orient=tk.VERTICAL, command=self.positions_tree.yview)
        self.positions_tree.configure(yscrollcommand=pos_scrollbar.set)
        
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        pos_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
    
    def create_config_tab(self):
        """Pestaña de configuración"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="⚙️ Configuración")
        
        # Frame para agregar fondo
        add_frame = ttk.LabelFrame(config_frame, text="Agregar Fondo")
        add_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Campos de entrada
        fields_frame = ttk.Frame(add_frame)
        fields_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(fields_frame, text="Nombre del Fondo:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.config_fund_name_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.config_fund_name_var, width=40).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(fields_frame, text="Tipo:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.config_fund_type_var = tk.StringVar(value=FUND_TYPES[0])
        ttk.Combobox(fields_frame, textvariable=self.config_fund_type_var, 
                    values=FUND_TYPES, state='readonly', width=37).grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(fields_frame, text="Saldo Inicial:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.config_initial_balance_var = tk.StringVar(value="0")
        ttk.Entry(fields_frame, textvariable=self.config_initial_balance_var, width=40).grid(row=2, column=1, padx=5, pady=2)
        
        ttk.Button(add_frame, text="➕ Agregar Fondo", 
                  command=self.add_fund_config).pack(pady=10)
        
        # TreeView para fondos configurados
        config_tree_frame = ttk.LabelFrame(config_frame, text="Fondos Configurados")
        config_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        config_columns = ('ID', 'Fondo', 'Tipo', 'Saldo Inicial')
        self.config_tree = ttk.Treeview(config_tree_frame, columns=config_columns, show='headings', height=10)
        
        for col in config_columns:
            self.config_tree.heading(col, text=col)
            if col == 'ID':
                self.config_tree.column(col, width=50, anchor=tk.CENTER)
            elif col == 'Saldo Inicial':
                self.config_tree.column(col, width=120, anchor=tk.E)
            else:
                self.config_tree.column(col, width=200)
        
        config_scrollbar = ttk.Scrollbar(config_tree_frame, orient=tk.VERTICAL, command=self.config_tree.yview)
        self.config_tree.configure(yscrollcommand=config_scrollbar.set)
        
        self.config_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        config_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    
    def create_export_tab(self):
        """Pestaña de exportación"""
        export_frame = ttk.Frame(self.notebook)
        self.notebook.add(export_frame, text="📤 Exportar")
        
        # Frame de opciones de exportación
        options_frame = ttk.LabelFrame(export_frame, text="Opciones de Exportación")
        options_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Filtro por tipo de fondo
        filter_frame = ttk.Frame(options_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Filtrar por tipo:").pack(side=tk.LEFT, padx=5)
        self.export_filter_var = tk.StringVar(value="Todos")
        ttk.Combobox(filter_frame, textvariable=self.export_filter_var,
                    values=["Todos"] + FUND_TYPES, state='readonly', width=15).pack(side=tk.LEFT, padx=5)
        
        # Formato de exportación
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(format_frame, text="Formato:").pack(side=tk.LEFT, padx=5)
        self.export_format_var = tk.StringVar(value="Excel")
        ttk.Radiobutton(format_frame, text="Excel (.xlsx)", variable=self.export_format_var, 
                       value="Excel").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(format_frame, text="CSV", variable=self.export_format_var, 
                       value="CSV").pack(side=tk.LEFT, padx=5)
        
        # Botones de exportación
        buttons_frame = ttk.Frame(export_frame)
        buttons_frame.pack(fill=tk.X, padx=10, pady=20)
        
        ttk.Button(buttons_frame, text="📊 Reporte Completo", 
                  command=self.export_complete_report).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="📄 Solo Operaciones", 
                  command=self.export_operations_only).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="💼 Solo Posiciones", 
                  command=self.export_positions_only).pack(side=tk.LEFT, padx=10)
        
        # Área de estado de exportación
        export_status_frame = ttk.LabelFrame(export_frame, text="Estado")
        export_status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.export_status_text = tk.Text(export_status_frame, height=10, wrap=tk.WORD)
        export_status_scrollbar = ttk.Scrollbar(export_status_frame, orient=tk.VERTICAL, 
                                               command=self.export_status_text.yview)
        self.export_status_text.configure(yscrollcommand=export_status_scrollbar.set)
        
        self.export_status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        export_status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    
    def create_peps_tab(self):
        """Pestaña de análisis PEPS"""
        peps_frame = ttk.Frame(self.notebook)
        self.notebook.add(peps_frame, text="📈 Análisis PEPS")
        
        # Frame de controles
        controls_frame = ttk.Frame(peps_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(controls_frame, text="🔄 Actualizar Análisis PEPS", 
                  command=self.refresh_peps_data).pack(side=tk.LEFT, padx=5)
        
        # Notebook para diferentes fondos
        self.peps_notebook = ttk.Notebook(peps_frame)
        self.peps_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Mensaje inicial
        initial_frame = ttk.Frame(self.peps_notebook)
        self.peps_notebook.add(initial_frame, text="📝 Información")
        
        info_text = """ANÁLISIS PEPS (Primero En Entrar, Primero En Salir)

Este análisis calcula las ganancias/pérdidas realizadas de cada fondo usando el método PEPS.

Para cada rescate se toma el costo de las cuotas más antiguas primero.

Procesa un PDF para generar el análisis PEPS correspondiente."""
        
        ttk.Label(initial_frame, text=info_text, justify=tk.LEFT, 
                 font=('Helvetica', 10)).pack(padx=20, pady=20)
    
    def create_status_bar(self):
        """Crear barra de estado"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Hora actual
        self.time_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.time_var).pack(side=tk.RIGHT, padx=10, pady=5)
        self.update_time()
    
    def create_operations_context_menu(self):
        """Crear menú contextual para operaciones"""
        self.ops_context_menu = tk.Menu(self.root, tearoff=0)
        self.ops_context_menu.add_command(label="Eliminar operación", command=self.delete_selected_operation)
        
        self.operations_tree.bind("<Button-3>", self.show_operations_context_menu)
    
    def show_operations_context_menu(self, event):
        """Mostrar menú contextual de operaciones"""
        item = self.operations_tree.selection()
        if item:
            self.ops_context_menu.post(event.x_root, event.y_root)
    
    def update_time(self):
        """Actualizar hora en la barra de estado"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_var.set(f"Hora: {current_time}")
        self.root.after(1000, self.update_time)
    
    # ====== MÉTODOS DE DATOS ======
    
    def refresh_data(self):
        """Actualizar todos los datos"""
        try:
            self.refresh_operations()
            self.refresh_positions()
            self.refresh_config()
            self.refresh_peps_data()
        except Exception as e:
            messagebox.showerror("Error", f"Error actualizando datos: {e}")
    
    def refresh_operations(self):
        """Actualizar vista de operaciones"""
        try:
            # Obtener filtro
            fund_type_filter = None if self.ops_filter_var.get() == "Todos" else self.ops_filter_var.get()
            
            # Cargar operaciones
            self.current_operations = self.db.get_operations(fund_type=fund_type_filter)
            
            # Limpiar TreeView
            for item in self.operations_tree.get_children():
                self.operations_tree.delete(item)
            
            # Poblar TreeView
            for op in self.current_operations:
                self.operations_tree.insert('', tk.END, values=(
                    op['id'],
                    op['date'],
                    op['operation_type'],
                    op['fund_name'],
                    f"{float(op['quantity']):,.8f}",
                    f"${float(op['unit_value']):,.8f}",
                    f"${float(op['total_amount']):,.2f}"
                ))
            
            self.status_var.set(f"Operaciones actualizadas: {len(self.current_operations)} registros")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error actualizando operaciones: {e}")
    
    def refresh_positions(self):
        """Actualizar vista de posiciones"""
        try:
            self.current_positions = self.db.get_positions()
            
            # Limpiar TreeView
            for item in self.positions_tree.get_children():
                self.positions_tree.delete(item)
            
            # Poblar TreeView
            total_value = 0
            for pos in self.current_positions:
                self.positions_tree.insert('', tk.END, values=(
                    pos['fund_name'],
                    pos.get('fund_type', 'N/A'),
                    f"{float(pos['quantity']):,.8f}",
                    f"${float(pos['unit_value']):,.8f}",
                    f"${float(pos['total_value']):,.2f}"
                ))
                total_value += float(pos['total_value'])
            
            self.status_var.set(f"Posiciones: {len(self.current_positions)} fondos, Valor total: ${total_value:,.2f}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error actualizando posiciones: {e}")
    
    def refresh_config(self):
        """Actualizar configuración"""
        try:
            self.current_configs = self.db.get_fund_configs()
            
            # Limpiar TreeView
            for item in self.config_tree.get_children():
                self.config_tree.delete(item)
            
            # Poblar TreeView
            for config in self.current_configs:
                self.config_tree.insert('', tk.END, values=(
                    config['id'],
                    config['fund_name'],
                    config['fund_type'],
                    f"${float(config['initial_balance']):,.2f}"
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Error actualizando configuración: {e}")
    
    def refresh_peps_data(self):
        """Actualizar análisis PEPS"""
        if not self.current_operations:
            return
        
        try:
            # Recalcular análisis PEPS
            self.peps_analysis_data = self.pdf_processor.calculate_peps_analysis(self.current_operations)
            
            # Limpiar pestañas anteriores (excepto la primera)
            for tab_id in self.peps_notebook.tabs()[1:]:
                self.peps_notebook.forget(tab_id)
            
            # Crear pestaña para cada fondo
            for fund_name, analysis in self.peps_analysis_data.items():
                self.create_fund_peps_tab(fund_name, analysis)
                
        except Exception as e:
            print(f"Error actualizando análisis PEPS: {e}")
    
    def create_fund_peps_tab(self, fund_name: str, analysis: dict):
        """Crear pestaña de análisis PEPS para un fondo específico"""
        fund_frame = ttk.Frame(self.peps_notebook)
        self.peps_notebook.add(fund_frame, text=fund_name[:15])
        
        # Frame de resumen
        summary_frame = ttk.LabelFrame(fund_frame, text=f"Resumen - {fund_name}")
        summary_frame.pack(fill=tk.X, padx=10, pady=10)
        
        summary_text = f"""Compras Totales: ${float(analysis['total_purchases']):,.2f}
Ventas Totales: ${float(analysis['total_sales']):,.2f}
Ganancia/Pérdida Total: ${float(analysis['total_gain_loss']):,.2f}

Posición Actual:
• Cuotas: {float(analysis['current_position']['quantity']):,.8f}
• Costo Promedio: ${float(analysis['current_position']['average_cost']):,.8f}
• Costo Total: ${float(analysis['current_position']['total_cost']):,.2f}"""
        
        ttk.Label(summary_frame, text=summary_text, justify=tk.LEFT, 
                 font=('Consolas', 10)).pack(padx=10, pady=10)
        
        # TreeView para detalle de operaciones
        detail_frame = ttk.LabelFrame(fund_frame, text="Detalle de Operaciones")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ('Fecha', 'Tipo', 'Cuotas', 'Precio', 'Total', 'Costo Base', 'G/P')
        peps_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            peps_tree.heading(col, text=col)
            if col in ['Cuotas', 'Precio', 'Total', 'Costo Base', 'G/P']:
                peps_tree.column(col, width=120, anchor=tk.E)
            else:
                peps_tree.column(col, width=100)
        
        # Poblar con datos
        for op_detail in analysis['operations_detail']:
            cost_base = op_detail.get('cost_basis', 0)
            gain_loss = op_detail.get('gain_loss', 0)
            
            values = [
                op_detail['date'],
                op_detail['type'],
                f"{float(op_detail['quantity']):,.8f}",
                f"${float(op_detail['unit_price']):,.8f}",
                f"${float(op_detail['total']):,.2f}",
                f"${float(cost_base):,.2f}" if cost_base else "N/A",
                f"${float(gain_loss):,.2f}" if gain_loss else "N/A"
            ]
            
            peps_tree.insert('', tk.END, values=values)
        
        peps_scrollbar = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=peps_tree.yview)
        peps_tree.configure(yscrollcommand=peps_scrollbar.set)
        
        peps_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        peps_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    
    # ====== MÉTODOS DE EVENTOS ======
    
    def browse_pdf(self):
        """Seleccionar archivo PDF"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo PDF",
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")]
        )
        if file_path:
            self.pdf_path_var.set(file_path)
    
    def select_and_process_pdf(self):
        """Seleccionar y procesar PDF desde menú"""
        self.browse_pdf()
        if self.pdf_path_var.get():
            self.process_pdf_async()
    
    def process_pdf_async(self):
        """Procesar PDF en hilo separado"""
        pdf_path = self.pdf_path_var.get()
        if not pdf_path:
            messagebox.showwarning("Advertencia", "Selecciona un archivo PDF primero")
            return
        
        if not os.path.exists(pdf_path):
            messagebox.showerror("Error", "El archivo PDF no existe")
            return
        
        # Cambiar cursor y deshabilitar botón
        self.root.config(cursor="wait")
        self.status_var.set("Procesando PDF...")
        
        # Procesar en hilo separado
        def process_thread():
            try:
                result = self.pdf_processor.process_pdf(pdf_path)
                # Llamar callback en hilo principal
                self.root.after(0, lambda: self._process_pdf_callback(result))
            except Exception as e:
                error_result = {
                    'success': False,
                    'error': str(e),
                    'operations': [],
                    'positions': [],
                    'peps_analysis': {}
                }
                self.root.after(0, lambda: self._process_pdf_callback(error_result))
        
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        thread.start()
    
    def _process_pdf_callback(self, result):
        """Callback después del procesamiento PDF"""
        self.root.config(cursor="")
        
        if result['success']:
            # Guardar operaciones en la base de datos
            saved_ops = 0
            for operation in result['operations']:
                try:
                    self.db.add_operation(operation)
                    saved_ops += 1
                except Exception as e:
                    print(f"Error guardando operación: {e}")
            
            # Guardar posiciones
            saved_pos = 0
            for position in result['positions']:
                try:
                    self.db.update_position(position)
                    saved_pos += 1
                except Exception as e:
                    print(f"Error guardando posición: {e}")
            
            # Mostrar resultados con análisis PEPS
            results_text = f"""PROCESAMIENTO COMPLETADO EXITOSAMENTE

📄 Archivo: {result['pdf_source']}
📊 Operaciones encontradas: {result['total_operations']}
💾 Operaciones guardadas: {saved_ops}
💼 Posiciones encontradas: {result['total_positions']}
💾 Posiciones guardadas: {saved_pos}

📈 ANÁLISIS PEPS DISPONIBLE:"""
            
            # Mostrar resumen PEPS por fondo
            peps_analysis = result.get('peps_analysis', {})
            for fund_name, fund_data in peps_analysis.items():
                results_text += f"""
═══════════════════════════════════════════
FONDO: {fund_name}
═══════════════════════════════════════════
• Total Suscripciones: ${float(fund_data['total_purchases']):,.2f}
• Total Rescates: ${float(fund_data['total_sales']):,.2f}
• Ganancia/Pérdida PEPS: ${float(fund_data['total_gain_loss']):,.2f}
• Cuotas Actuales: {float(fund_data['current_position']['quantity']):,.8f}
• Costo Promedio: ${float(fund_data['current_position']['average_cost']):,.8f}"""
            
            results_text += "\n\n📋 DETALLE DE OPERACIONES:\n"
            for i, op in enumerate(result['operations'], 1):
                results_text += f"\n{i}. {op['date']} - {op['operation_type']} - {op['fund_name']}"
                results_text += f"\n   Cuotas: {float(op['quantity']):,.8f} | Valor: ${float(op['unit_value']):,.8f} | Total: ${float(op['total_amount']):,.2f}"
            
            self.pdf_results_text.delete(1.0, tk.END)
            self.pdf_results_text.insert(1.0, results_text)
            
            # Refrescar datos incluyendo PEPS
            self.refresh_data()
            
            self.status_var.set(f'PDF procesado: {saved_ops} operaciones, {saved_pos} posiciones, análisis PEPS disponible')
            
        else:
            self.pdf_results_text.delete(1.0, tk.END)
            self.pdf_results_text.insert(1.0, f"ERROR: {result['error']}")
            self.status_var.set('Error procesando PDF')
    
    def add_fund_config(self):
        """Agregar configuración de fondo"""
        fund_name = self.config_fund_name_var.get().strip()
        fund_type = self.config_fund_type_var.get()
        initial_balance_str = self.config_initial_balance_var.get().strip()
        
        if not fund_name:
            messagebox.showwarning("Advertencia", "Ingresa el nombre del fondo")
            return
        
        try:
            from decimal import Decimal
            initial_balance = Decimal(initial_balance_str)
            
            self.db.set_fund_config(fund_name, fund_type, initial_balance)
            
            # Limpiar campos
            self.config_fund_name_var.set("")
            self.config_initial_balance_var.set("0")
            
            # Actualizar vista
            self.refresh_config()
            
            messagebox.showinfo("Éxito", f"Fondo '{fund_name}' configurado correctamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error configurando fondo: {e}")
    
    def delete_selected_operation(self):
        """Eliminar operación seleccionada"""
        selection = self.operations_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una operación para eliminar")
            return
        
        item = self.operations_tree.item(selection[0])
        operation_id = item['values'][0]
        fund_name = item['values'][3]
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar operación ID {operation_id} del fondo {fund_name}?"):
            try:
                if self.db.delete_operation(operation_id):
                    self.refresh_operations()
                    self.status_var.set(f"Operación {operation_id} eliminada")
                else:
                    messagebox.showerror("Error", "No se pudo eliminar la operación")
            except Exception as e:
                messagebox.showerror("Error", f"Error eliminando operación: {e}")
    
    # ====== MÉTODOS DE EXPORTACIÓN ======
    
    def export_excel_dialog(self):
        """Mostrar diálogo de exportación Excel"""
        self.notebook.select(4)  # Seleccionar pestaña de exportar
    
    def export_complete_report(self):
        """Exportar reporte completo"""
        try:
            from excel_exporter import ExcelExporter
            
            fund_type_filter = None if self.export_filter_var.get() == "Todos" else self.export_filter_var.get()
            format_type = self.export_format_var.get()
            
            exporter = ExcelExporter()
            
            if format_type == "Excel":
                file_path = exporter.export_complete_report(
                    operations=self.current_operations,
                    positions=self.current_positions,
                    fund_type_filter=fund_type_filter
                )
            else:  # CSV
                file_path = exporter.export_operations_csv(
                    operations=self.current_operations,
                    fund_type_filter=fund_type_filter
                )
            
            self.export_status_text.insert(tk.END, f"\n✅ Reporte exportado: {file_path}\n")
            self.export_status_text.see(tk.END)
            
            if messagebox.askyesno("Exportación Exitosa", 
                                  f"Reporte guardado en:\n{file_path}\n\n¿Abrir carpeta?"):
                import subprocess
                subprocess.run(['explorer', '/select,', file_path.replace('/', '\\')])
                
        except ImportError:
            messagebox.showerror("Error", "Módulo excel_exporter no encontrado")
        except Exception as e:
            self.export_status_text.insert(tk.END, f"\n❌ Error exportando: {e}\n")
            self.export_status_text.see(tk.END)
    
    def export_operations_only(self):
        """Exportar solo operaciones"""
        try:
            from excel_exporter import ExcelExporter
            
            fund_type_filter = None if self.export_filter_var.get() == "Todos" else self.export_filter_var.get()
            
            exporter = ExcelExporter()
            file_path = exporter.export_operations_csv(
                operations=self.current_operations,
                fund_type_filter=fund_type_filter
            )
            
            self.export_status_text.insert(tk.END, f"\n✅ Operaciones exportadas: {file_path}\n")
            self.export_status_text.see(tk.END)
            
        except ImportError:
            messagebox.showerror("Error", "Módulo excel_exporter no encontrado")
        except Exception as e:
            self.export_status_text.insert(tk.END, f"\n❌ Error exportando: {e}\n")
            self.export_status_text.see(tk.END)
    
    def export_positions_only(self):
        """Exportar solo posiciones"""
        try:
            from excel_exporter import ExcelExporter
            
            exporter = ExcelExporter()
            file_path = exporter.export_positions_csv(positions=self.current_positions)
            
            self.export_status_text.insert(tk.END, f"\n✅ Posiciones exportadas: {file_path}\n")
            self.export_status_text.see(tk.END)
            
        except ImportError:
            messagebox.showerror("Error", "Módulo excel_exporter no encontrado")
        except Exception as e:
            self.export_status_text.insert(tk.END, f"\n❌ Error exportando: {e}\n")
            self.export_status_text.see(tk.END)
    
    # ====== MÉTODOS DE UTILIDADES ======
    
    def show_stats(self):
        """Mostrar estadísticas de la base de datos"""
        try:
            stats = self.db.get_database_stats()
            
            stats_text = f"""📊 ESTADÍSTICAS DE LA BASE DE DATOS

📄 Total de operaciones: {stats['total_operations']}
💼 Total de posiciones: {stats['total_positions']}
⚙️ Fondos configurados: {stats['configured_funds']}
💰 Valor total del portfolio: ${float(stats['total_portfolio_value']):,.2f}

📈 Tipos de fondos disponibles:"""
            
            fund_types = self.db.get_fund_types()
            for fund_type in fund_types:
                stats_text += f"\n   • {fund_type}"
            
            messagebox.showinfo("Estadísticas", stats_text)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error obteniendo estadísticas: {e}")
    
    def show_about(self):
        """Mostrar información sobre la aplicación"""
        about_text = f"""{APP_CONFIG['app_name']}
Versión {APP_CONFIG['version']}

Aplicación profesional para procesar extractos PDF de FIMA
con análisis PEPS y gestión de operaciones financieras.

Desarrollado con Python y Tkinter
Motores PDF: {', '.join(self.pdf_processor.available_engines)}

© 2025 - Procesador Financiero"""
        
        messagebox.showinfo("Acerca de", about_text)
