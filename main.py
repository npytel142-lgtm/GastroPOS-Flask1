import sys
import sqlite3
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QMessageBox, QInputDialog, QTableWidget, QTableWidgetItem,
    QGridLayout, QSizePolicy, QDialog, QListWidget, QListWidgetItem, QGroupBox, QScrollArea,
    QSpinBox, QMenu, QAction, QTabWidget, QSpacerItem, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, QSize, pyqtSignal 
from PyQt5.QtGui import QIntValidator, QDoubleValidator, QFont

# --- UŻYTKOWNICY I MENU ---
USERS = {
    "1234": "Basia",
    "4444": "Krystian",
    "5000": "Natalia",
    "5001": "Kuba",
    "5002": "Marlena",
    "5003": "Ilona",
    "5004": "Paulina",
    "9999": "ADMIN" # PIN dla administratora
}

# --- MAPOWANIE KATEGORII NA CENTRA REALIZACJI BONÓW ---
SERVICE_POINTS = {
    "PRZYSTAWKI": "KUCHNIA",
    "ZUPY": "KUCHNIA",
    "DANIA GŁÓWNE": "KUCHNIA",
    "PIZZA": "KUCHNIA",
    "SAŁATKI": "KUCHNIA",
    
    "NAPOJE GORĄCE": "BAR",
    "NAPOJE ZIMNE": "BAR",
    "DESERY": "BAR",
    "ALKOHOLE": "BAR", 
    "POZOSTAŁE": "INNE", 
}

# --- BAZA DANYCH (FUNKCJE GLOBALNE) ---
DB_NAME = "db.sqlite"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tabela menu
    c.execute("""
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL
        )
    """)
    
    # 2. Tabela stolików
    c.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            no INTEGER PRIMARY KEY,
            is_enabled BOOLEAN NOT NULL DEFAULT 1,
            owner_id TEXT 
        )
    """)

    # 3. Tabela zamówień
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            table_no INTEGER NOT NULL,
            waiter_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            service_point TEXT NOT NULL,
            discount_percent INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'nowe', -- 'nowe', 'w realizacji', 'gotowe', 'zakończone', 'archiwalne'
            order_timestamp DATETIME NOT NULL,
            finish_timestamp DATETIME 
        )
    """)

    # Sprawdzenie i wstawienie stolików
    for i in range(1, 13): # 12 stolików
        c.execute("INSERT OR IGNORE INTO tables (no) VALUES (?)", (i,))

    # Wstawienie przykładowych pozycji menu (jeśli pusta)
    c.execute("SELECT COUNT(*) FROM menu")
    if c.fetchone()[0] == 0:
        menu_items = [
            ("Rosół", 15.00, "ZUPY"),
            ("Pomidorowa", 18.00, "ZUPY"),
            ("Schabowy z ziemniakami", 35.00, "DANIA GŁÓWNE"),
            ("Filet z kurczaka", 32.00, "DANIA GŁÓWNE"),
            ("Pizza Margherita", 38.00, "PIZZA"),
            ("Coca-Cola", 8.00, "NAPOJE ZIMNE"),
            ("Herbata", 10.00, "NAPOJE GORĄCE"),
            ("Woda niegazowana", 7.00, "NAPOJE ZIMNE"),
            ("Lody waniliowe", 19.00, "DESERY"),
            ("Piwo 0.5L", 15.00, "ALKOHOLE"),
        ]
        for item in menu_items:
            c.execute("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", 
                      (item[0], item[1], item[2]))

    conn.commit()
    conn.close()

def get_menu():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name, price, category FROM menu ORDER BY category, name")
    menu_data = c.fetchall()
    conn.close()
    
    menu = {}
    for name, price, category in menu_data:
        if category not in menu:
            menu[category] = []
        menu[category].append((name, price))
    return menu

def get_all_tables_status():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT no, owner_id FROM tables WHERE is_enabled = 1 ORDER BY no")
    tables = []
    for no, owner_id in c.fetchall():
        status = 'free'
        if owner_id:
            # Sprawdzamy czy są jakieś aktywne (nie 'zakończone' i nie 'archiwalne') zamówienia
            c.execute("SELECT count(*) FROM orders WHERE table_no = ? AND status NOT IN ('zakończone', 'archiwalne')", (no,))
            if c.fetchone()[0] > 0:
                status = 'active'
        
        tables.append({'no': no, 'status': status, 'owner_id': owner_id})
    conn.close()
    return tables

def get_table_owner(table_no):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT owner_id FROM tables WHERE no = ?", (table_no,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def set_table_owner(table_no, waiter_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE tables SET owner_id = ? WHERE no = ?", (waiter_id, table_no))
    conn.commit()
    conn.close()

def group_or_add_order(table_no, waiter_id, item_name, price, category, qty=1):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    service_point = SERVICE_POINTS.get(category, "INNE")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Sprawdź, czy pozycja już istnieje na rachunku w statusie 'nowe'
    c.execute("""
        SELECT id, qty FROM orders 
        WHERE table_no = ? AND item_name = ? AND status = 'nowe'
    """, (table_no, item_name))
    
    existing_item = c.fetchone()

    if existing_item:
        # 2. Jeśli istnieje, zwiększ ilość
        new_qty = existing_item[1] + qty
        c.execute("""
            UPDATE orders 
            SET qty = ? 
            WHERE id = ?
        """, (new_qty, existing_item[0]))
    else:
        # 3. Jeśli nie istnieje, dodaj nową pozycję
        c.execute("""
            INSERT INTO orders (table_no, waiter_id, item_name, qty, price, category, service_point, order_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (table_no, waiter_id, item_name, qty, price, category, service_point, current_time))
        
    # Ustaw kelnera jako właściciela stolika (jeśli nie jest)
    set_table_owner(table_no, waiter_id)
    
    conn.commit()
    conn.close()

def get_orders(table_no, status='aktywne'):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if status == 'aktywne':
        # Pobieramy zamówienia, które nie są 'zakończone' ani 'archiwalne'
        c.execute("""
            SELECT item_name, qty, price, category, status, order_timestamp, id, discount_percent
            FROM orders 
            WHERE table_no = ? AND status NOT IN ('zakończone', 'archiwalne') 
            ORDER BY order_timestamp
        """, (table_no,))
    elif status == 'wszystkie':
        c.execute("""
            SELECT item_name, qty, price, category, status, order_timestamp, id, discount_percent
            FROM orders 
            WHERE table_no = ?
            ORDER BY order_timestamp
        """, (table_no,))
    else: # np. 'kds' - dla kuchni
        c.execute("""
            SELECT item_name, qty, category, service_point, order_timestamp, table_no, id
            FROM orders
            WHERE status IN ('nowe', 'w realizacji') 
            ORDER BY order_timestamp
        """)
        orders = c.fetchall()
        conn.close()
        
        # Grupujemy dla KDS
        kds_groups = {}
        for name, qty, category, point, ts, table, id_ in orders:
            if point not in kds_groups:
                kds_groups[point] = []
            kds_groups[point].append({
                'id': id_,
                'item_name': name,
                'qty': qty,
                'category': category,
                'timestamp': ts,
                'table_no': table
            })
        return kds_groups


    orders = c.fetchall()
    conn.close()
    
    # Przetwarzanie dla widoku kelnera
    result = []
    for name, qty, price, category, item_status, ts, id_, discount in orders:
        total_price = qty * price * (1 - discount / 100)
        result.append({
            'id': id_,
            'item_name': name,
            'qty': qty,
            'price': price,
            'total_price': total_price,
            'category': category,
            'status': item_status,
            'timestamp': ts,
            'discount': discount
        })
    return result

def remove_order_item(order_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM orders WHERE id = ? AND status = 'nowe'", (order_id,))
    conn.commit()
    conn.close()
    return c.rowcount > 0

def update_order_status(order_id, new_status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if new_status == 'gotowe':
        # W widoku kelnera nie zmieniamy statusu, tylko w KDS
        c.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    elif new_status == 'w realizacji':
        c.execute("UPDATE orders SET status = ? WHERE id = ? AND status = 'nowe'", (new_status, order_id))
    else: # Dla innych statusów np. 'nowe'
         c.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))

    conn.commit()
    conn.close()

def send_orders(table_no):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Zmieniamy status wszystkich 'nowe' na 'w realizacji' dla danego stolika
    c.execute("UPDATE orders SET status = 'w realizacji' WHERE table_no = ? AND status = 'nowe'", (table_no,))
    conn.commit()
    conn.close()
    return c.rowcount > 0

def finalize_bill_full(table_no, waiter_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Zmień status wszystkich aktywnych zamówień na 'zakończone'
    c.execute("""
        UPDATE orders 
        SET status = 'zakończone', finish_timestamp = ? 
        WHERE table_no = ? AND status NOT IN ('zakończone', 'archiwalne')
    """, (current_time, table_no))
    
    # 2. Usuń właściciela stolika
    c.execute("UPDATE tables SET owner_id = NULL WHERE no = ?", (table_no,))
    
    conn.commit()
    conn.close()
    return True

def get_waiter_summary(waiter_id, start_date, end_date):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    start_dt = f"{start_date} 00:00:00"
    end_dt = f"{end_date} 23:59:59"
    
    # Używamy finish_timestamp do zliczania unikalnych zamkniętych rachunków
    c.execute("""
        SELECT 
            COUNT(DISTINCT table_no), 
            SUM(qty * price * (1 - discount_percent / 100))
        FROM orders
        WHERE waiter_id = ? 
        AND status IN ('zakończone', 'archiwalne') 
        AND finish_timestamp BETWEEN ? AND ?
    """, (waiter_id, start_dt, end_dt))
    
    result = c.fetchone()
    conn.close()
    
    # POPRAWKA BŁĘDU: Jeśli SUMA jest None (bo nie ma rekordów), ustawiamy ją na 0.0
    orders_count = result[0] if result and result[0] is not None else 0
    total_sales = result[1] if result and result[1] is not None else 0.0
    
    return (orders_count, total_sales)

def get_all_categories():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM menu ORDER BY category")
    categories = [row[0] for row in c.fetchall()]
    conn.close()
    return categories

def add_menu_item(name, price, category):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", (name, price, category))
    conn.commit()
    conn.close()

def toggle_table_enabled(table_no, is_enabled):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE tables SET is_enabled = ?, owner_id = NULL WHERE no = ?", (1 if is_enabled else 0, table_no))
    conn.commit()
    conn.close()

def get_all_tables_info():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT no, is_enabled, owner_id FROM tables ORDER BY no")
    tables = [{'no': no, 'is_enabled': is_enabled, 'owner_id': owner_id} for no, is_enabled, owner_id in c.fetchall()]
    conn.close()
    return tables

def apply_discount(order_id, discount_percent):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE orders SET discount_percent = ? WHERE id = ? AND status = 'nowe'", (discount_percent, order_id))
    conn.commit()
    conn.close()

# --- STYLIZACJA ---

def get_stylesheet():
    return """
        QWidget {
            background-color: #f0f0f0;
            color: #333;
            font-family: Arial, sans-serif;
            font-size: 12pt;
        }

        /* --- OKNO LOGOWANIA --- */
        QLineEdit {
            padding: 10px;
            border: 2px solid #008CBA;
            border-radius: 5px;
            background-color: white;
            font-size: 18pt;
        }

        QPushButton {
            padding: 15px;
            border: none;
            border-radius: 5px;
            font-weight: bold;
            cursor: pointer;
        }

        QPushButton[btn_type="numpad"] {
            background-color: #E0E0E0;
            color: #333;
        }
        QPushButton[btn_type="numpad"]:hover {
            background-color: #D5D5D5;
        }
        QPushButton[btn_type="numpad_clear"] {
            background-color: #F44336;
            color: white;
        }
        QPushButton[btn_type="numpad_clear"]:hover {
            background-color: #D32F2F;
        }

        QPushButton[btn_type="main_action"] {
            background-color: #4CAF50;
            color: white;
        }
        QPushButton[btn_type="main_action"]:hover {
            background-color: #388E3C;
        }
        
        QPushButton[btn_type="secondary"] {
            background-color: #008CBA;
            color: white;
        }
        QPushButton[btn_type="secondary"]:hover {
            background-color: #005f7d;
        }
        
        /* --- WIDOK STOLIKÓW --- */
        QPushButton[btn_type=\"table_free\"] {
            background-color: #E8F5E9;
            color: #4CAF50;
            border: 3px solid #4CAF50;
            font-size: 16pt;
            min-height: 100px;
        }

        QPushButton[btn_type=\"table_active\"] {
            background-color: #FFEBEE;
            color: #F44336;
            border: 3px solid #F44336;
            font-size: 16pt;
            min-height: 100px;
        }
        
        QPushButton[btn_type=\"table_mine\"] {
            background-color: #FFFDE7;
            color: #FFC107;
            border: 3px solid #FFC107;
            font-size: 16pt;
            min-height: 100px;
        }
        
        /* --- WIDOK ZAMÓWIENIA --- */
        QTableWidget {
            background-color: white;
            border: 1px solid #ddd;
            gridline-color: #eee;
        }
        QTableWidget::item {
            padding: 5px;
        }
        QHeaderView::section {
            background-color: #008CBA;
            color: white;
            padding: 5px;
            border: 1px solid #ddd;
        }
        
        /* --- PRZYCISKI MENU --- */
        QPushButton[btn_type="menu_category"] {
            background-color: #008CBA;
            color: white;
            min-height: 80px;
            font-size: 14pt;
        }
        QPushButton[btn_type="menu_item"] {
            background-color: #ffffff;
            color: #333;
            border: 1px solid #ddd;
            min-height: 80px;
            font-size: 11pt;
            text-align: left;
        }
        
        /* --- KDS WIDOK --- */
        QGroupBox[box_type="kds_group"] {
            border: 2px solid #008CBA;
            border-radius: 8px;
            margin-top: 20px;
            padding-top: 25px;
            font-size: 16pt;
            font-weight: bold;
            color: #008CBA;
            background-color: #e0f7fa;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            margin-left: 10px;
        }
        
        QListWidget[list_type="kds"] {
            border: none;
            background-color: #e0f7fa;
        }
        
        QListWidget[list_type="kds"]::item {
            border-bottom: 1px solid #B3E5FC;
            padding: 5px;
            background-color: white;
            margin-bottom: 5px;
            border-radius: 3px;
            color: #333;
        }
        
        QLabel[label_type="print_output"] {
            font-family: 'Courier New', monospace;
            white-space: pre;
            font-size: 10pt;
        }

    """
    
# --- KLASY OKIEN (DOPASOWANE DO TWOJEGO KODU) ---

class AdminPanelWindow(QWidget):
    closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowTitle("Panel Administratora")
        self.setFixedSize(1000, 700)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        self.tab_widget.addTab(self.create_billing_tab(), "Raporty Sprzedaży")
        self.tab_widget.addTab(self.create_menu_tab(), "Zarządzanie Menu")
        self.tab_widget.addTab(self.create_table_tab(), "Zarządzanie Stolikami")
        self.tab_widget.addTab(self.create_kds_tab(), "KDS/Kuchenny Widok") # Dodano KDS

        btn_back = QPushButton("Wróć do Logowania")
        btn_back.clicked.connect(self.close)
        main_layout.addWidget(btn_back)

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
        
    def create_billing_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Daty
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Od:"))
        self.start_date_input = QLineEdit(datetime.now().strftime("%Y-%m-%d"))
        date_layout.addWidget(self.start_date_input)
        date_layout.addWidget(QLabel("Do:"))
        self.end_date_input = QLineEdit(datetime.now().strftime("%Y-%m-%d"))
        date_layout.addWidget(self.end_date_input)
        
        btn_generate = QPushButton("Generuj Raport")
        btn_generate.clicked.connect(self.generate_report)
        date_layout.addWidget(btn_generate)
        
        layout.addLayout(date_layout)
        
        self.report_table = QTableWidget()
        self.report_table.setColumnCount(3)
        self.report_table.setHorizontalHeaderLabels(["Kelner", "Ilość Rachunków", "Suma Sprzedaży"])
        layout.addWidget(self.report_table)

        return widget

    def generate_report(self):
        start_date = self.start_date_input.text()
        end_date = self.end_date_input.text()
        
        summary = []
        for waiter_id, waiter_name in USERS.items():
            if waiter_id != '9999': # Pomiń admina w podsumowaniu sprzedaży
                count, sales = get_waiter_summary(waiter_id, start_date, end_date)
                summary.append((waiter_name, count, sales))
        
        self.report_table.setRowCount(len(summary))
        
        total_sales_all = 0.0
        total_orders_all = 0
        
        for row, data in enumerate(summary):
            waiter_name, count, sales = data
            total_orders_all += count
            total_sales_all += sales
            
            self.report_table.setItem(row, 0, QTableWidgetItem(waiter_name))
            self.report_table.setItem(row, 1, QTableWidgetItem(str(count)))
            self.report_table.setItem(row, 2, QTableWidgetItem(f"{sales:.2f} zł"))

        # Dodanie wiersza podsumowania
        current_row = len(summary)
        self.report_table.setRowCount(current_row + 1)
        
        self.report_table.setItem(current_row, 0, QTableWidgetItem("SUMA CAŁKOWITA"))
        self.report_table.setItem(current_row, 1, QTableWidgetItem(str(total_orders_all)))
        self.report_table.setItem(current_row, 2, QTableWidgetItem(f"{total_sales_all:.2f} zł"))
        
        # Styling podsumowania
        font = QFont()
        font.setBold(True)
        for col in range(3):
            item = self.report_table.item(current_row, col)
            if item:
                item.setFont(font)

        self.report_table.resizeColumnsToContents()

    def create_menu_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tabela menu
        self.menu_table = QTableWidget()
        self.menu_table.setColumnCount(3)
        self.menu_table.setHorizontalHeaderLabels(["Nazwa", "Cena (zł)", "Kategoria"])
        layout.addWidget(self.menu_table)
        
        # Formularz dodawania pozycji
        add_group = QGroupBox("Dodaj Nową Pozycję Menu")
        add_layout = QGridLayout(add_group)
        
        self.menu_name_input = QLineEdit()
        self.menu_price_input = QLineEdit()
        self.menu_price_input.setValidator(QDoubleValidator(0.0, 999.99, 2))
        self.menu_category_input = QLineEdit()
        
        add_layout.addWidget(QLabel("Nazwa:"), 0, 0)
        add_layout.addWidget(self.menu_name_input, 0, 1)
        add_layout.addWidget(QLabel("Cena:"), 1, 0)
        add_layout.addWidget(self.menu_price_input, 1, 1)
        add_layout.addWidget(QLabel("Kategoria:"), 2, 0)
        add_layout.addWidget(self.menu_category_input, 2, 1)
        
        btn_add_item = QPushButton("Dodaj Pozycję")
        btn_add_item.clicked.connect(self.add_menu_item_admin)
        add_layout.addWidget(btn_add_item, 3, 0, 1, 2)
        
        layout.addWidget(add_group)
        
        self.load_menu()
        return widget

    def load_menu(self):
        menu_data = get_menu()
        items = []
        for category, item_list in menu_data.items():
            for name, price in item_list:
                items.append((name, price, category))

        self.menu_table.setRowCount(len(items))
        for row, (name, price, category) in enumerate(items):
            self.menu_table.setItem(row, 0, QTableWidgetItem(name))
            self.menu_table.setItem(row, 1, QTableWidgetItem(f"{price:.2f}"))
            self.menu_table.setItem(row, 2, QTableWidgetItem(category))
        
        self.menu_table.resizeColumnsToContents()

    def add_menu_item_admin(self):
        name = self.menu_name_input.text().strip()
        price_str = self.menu_price_input.text().strip().replace(',', '.')
        category = self.menu_category_input.text().strip().upper()
        
        if not name or not price_str or not category:
            QMessageBox.warning(self, "Błąd", "Wszystkie pola muszą być wypełnione.")
            return

        try:
            price = float(price_str)
            add_menu_item(name, price, category)
            QMessageBox.information(self, "Sukces", f"Dodano: {name} ({category}) za {price:.2f} zł.")
            
            # Wyczyść pola
            self.menu_name_input.clear()
            self.menu_price_input.clear()
            self.menu_category_input.clear()
            
            self.load_menu() # Odśwież tabelę
        except ValueError:
            QMessageBox.critical(self, "Błąd Ceny", "Cena musi być poprawną liczbą.")
        except Exception as e:
            QMessageBox.critical(self, "Błąd Bazy Danych", f"Nie udało się dodać pozycji: {e}")

    def create_table_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.table_config_table = QTableWidget()
        self.table_config_table.setColumnCount(3)
        self.table_config_table.setHorizontalHeaderLabels(["Stolik", "Status", "Włącz/Wyłącz"])
        layout.addWidget(self.table_config_table)
        
        btn_refresh = QPushButton("Odśwież Listę")
        btn_refresh.clicked.connect(self.load_table_config)
        layout.addWidget(btn_refresh)
        
        self.load_table_config()
        return widget

    def load_table_config(self):
        tables = get_all_tables_info()
        self.table_config_table.setRowCount(len(tables))
        
        for row, table in enumerate(tables):
            # Numer stolika
            item_no = QTableWidgetItem(str(table['no']))
            item_no.setFlags(item_no.flags() & ~Qt.ItemIsEditable)
            self.table_config_table.setItem(row, 0, item_no)
            
            # Status
            status_text = "Włączony" if table['is_enabled'] else "Wyłączony"
            if table['owner_id']:
                status_text += f" (Zajęty przez: {USERS.get(table['owner_id'], 'Nieznany')})"
            item_status = QTableWidgetItem(status_text)
            item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
            self.table_config_table.setItem(row, 1, item_status)

            # Przycisk
            btn_toggle = QPushButton("Wyłącz" if table['is_enabled'] else "Włącz")
            btn_toggle.setProperty("btn_type", "main_action" if table['is_enabled'] else "numpad_clear")
            btn_toggle.clicked.connect(lambda _, no=table['no'], enabled=table['is_enabled']: self.toggle_table(no, not enabled))
            
            self.table_config_table.setCellWidget(row, 2, btn_toggle)
            
        self.table_config_table.resizeColumnsToContents()

    def toggle_table(self, table_no, enable):
        toggle_table_enabled(table_no, enable)
        self.load_table_config()
        QMessageBox.information(self, "Status Stolika", f"Stolik {table_no} został {'włączony' if enable else 'wyłączony'}.")

    def create_kds_tab(self):
        self.kds_widget = KDSWindow()
        return self.kds_widget

# KLASA KDS WIDOW (WIDOK KUCHENNY)

class KDSWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kitchen Display System (KDS)")
        self.main_layout = QHBoxLayout(self)
        self.service_points = SERVICE_POINTS.values()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_kds)
        self.timer.start(5000) # Odświeżaj co 5 sekund
        
        self.update_kds()

    def update_kds(self):
        orders_by_point = get_orders(None, status='kds')
        
        # Usuń stare grupy
        while self.main_layout.count():
            child = self.main_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Dodaj nowe grupy
        for point in sorted(set(self.service_points)):
            group = QGroupBox(point)
            group.setProperty("box_type", "kds_group")
            group_layout = QVBoxLayout(group)
            
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            list_widget = QListWidget()
            list_widget.setProperty("list_type", "kds")
            list_widget.setFont(QFont("Arial", 12))
            
            orders = orders_by_point.get(point, [])
            
            for order in orders:
                item_text = f"STÓŁ {order['table_no']} | {order['qty']}x {order['item_name']} ({order['category']})\n\n{order['timestamp']}"
                list_item = QListWidgetItem(item_text)
                
                # Dodajemy przycisk
                btn_done = QPushButton("GOTOWE")
                btn_done.setProperty("btn_type", "main_action")
                btn_done.clicked.connect(lambda _, id_=order['id']: self.mark_ready(id_))
                
                # Widget opakowujący
                widget_container = QWidget()
                h_layout = QVBoxLayout(widget_container)
                
                label_item = QLabel(item_text)
                label_item.setWordWrap(True)
                
                h_layout.addWidget(label_item)
                h_layout.addWidget(btn_done)
                h_layout.setContentsMargins(5, 5, 5, 5)

                list_item.setSizeHint(widget_container.sizeHint())
                list_widget.addItem(list_item)
                list_widget.setItemWidget(list_item, widget_container)


            scroll.setWidget(list_widget)
            group_layout.addWidget(scroll)
            self.main_layout.addWidget(group)

    def mark_ready(self, order_id):
        # Aktualizujemy status w bazie danych
        update_order_status(order_id, 'gotowe')
        # Odświeżamy widok
        self.update_kds()
        QMessageBox.information(self, "KDS", f"Zamówienie {order_id} oznaczono jako gotowe.")

# KLASA LoginWindow (POPRAWIONA)

class LoginWindow(QWidget):
    # Sygnał emitowany po pomyślnym zalogowaniu (z wyjątkiem ADMINA)
    logged_in = pyqtSignal(str) 

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logowanie")
        self.setFixedSize(400, 550) # Nieco większa wysokość
        
        self.waiter_id = None
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignCenter)
        
        # --- Etykieta i Pole PIN ---
        self.label = QLabel("Wprowadź PIN:")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Arial", 16))
        
        self.pin_input = QLineEdit()
        self.pin_input.setValidator(QIntValidator())
        self.pin_input.setMaxLength(4)
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setAlignment(Qt.AlignCenter)
        self.pin_input.setFont(QFont("Arial", 24))
        self.pin_input.setFixedSize(200, 50)
        self.pin_input.returnPressed.connect(self.check_login) # Logowanie po naciśnięciu Enter
        
        input_layout = QHBoxLayout()
        input_layout.addStretch(1)
        input_layout.addWidget(self.pin_input)
        input_layout.addStretch(1)
        
        self.main_layout.addWidget(self.label)
        self.main_layout.addLayout(input_layout)
        
        # --- Przyciski Numeryczne ---
        numpad_layout = QGridLayout()
        buttons = [
            ('1', 0, 0), ('2', 0, 1), ('3', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('7', 2, 0), ('8', 2, 1), ('9', 2, 2),
            ('C', 3, 0), ('0', 3, 1), ('OK', 3, 2) 
        ]
        
        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setFont(QFont("Arial", 18))
            btn.setFixedSize(80, 80)
            
            if text.isdigit():
                btn.clicked.connect(lambda _, t=text: self.append_pin(t))
                btn.setProperty("btn_type", "numpad")
            elif text == 'C':
                btn.clicked.connect(self.pin_input.clear)
                btn.setProperty("btn_type", "numpad_clear")
            elif text == 'OK':
                btn.clicked.connect(self.check_login)
                btn.setProperty("btn_type", "main_action")
                
            numpad_layout.addWidget(btn, row, col)

        self.main_layout.addLayout(numpad_layout)
        self.main_layout.addSpacing(20)

        # Usunięto/zakomentowano domyślny przycisk Admin Panel,
        # aby wymusić logowanie PINem w polu tekstowym.
        
    def append_pin(self, number):
        if len(self.pin_input.text()) < 4:
            self.pin_input.setText(self.pin_input.text() + number)

    def check_login(self, pin=None):
        pin_code = pin if pin else self.pin_input.text()
        
        if pin_code in USERS:
            self.waiter_id = pin_code
            self.pin_input.clear()
            
            if pin_code == '9999': # LOGOWANIE ADMINA
                self.hide()
                self.admin_window = AdminPanelWindow(self)
                self.admin_window.closed.connect(self.show)
                self.admin_window.show()
            else: # LOGOWANIE KELNERA (WIDOK STOLIKÓW)
                self.hide()
                self.logged_in.emit(self.waiter_id) # To uruchamia TablesWindow
        else:
            QMessageBox.warning(self, "Błąd Logowania", "Nieprawidłowy PIN.")
            self.pin_input.clear()

# KLASA TablesWindow

class TablesWindow(QWidget):
    closed = pyqtSignal()

    def __init__(self, waiter_id):
        super().__init__()
        self.waiter_id = waiter_id
        self.waiter_name = USERS.get(waiter_id, "Nieznany")
        self.setWindowTitle(f"Stoliki - Kelner: {self.waiter_name}")
        self.setFixedSize(800, 600)
        self.init_ui()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_tables)
        self.timer.start(5000) # Odświeżaj co 5 sekund

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Header (tytuł i wylogowanie)
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f"<h2>Witaj, {self.waiter_name}!</h2>"))
        
        # Przycisk Admin Panel (tylko dla admina)
        if self.waiter_id == '9999':
            btn_admin = QPushButton("Admin Panel")
            btn_admin.setProperty("btn_type", "secondary")
            btn_admin.clicked.connect(self.open_admin_panel)
            header_layout.addWidget(btn_admin)
            
        btn_logout = QPushButton("Wyloguj")
        btn_logout.setProperty("btn_type", "numpad_clear")
        btn_logout.clicked.connect(self.close)
        header_layout.addWidget(btn_logout)
        
        main_layout.addLayout(header_layout)
        
        # Widok stolików
        self.tables_grid = QGridLayout()
        main_layout.addLayout(self.tables_grid)
        main_layout.addStretch(1)
        
        self.load_tables()

    def open_admin_panel(self):
        self.timer.stop()
        self.hide()
        # AdminPanelWindow potrzebuje referencji do rodzica, by po zamknięciu powrócić
        self.admin_window = AdminPanelWindow(self) 
        self.admin_window.closed.connect(self.show_and_restart_timer)
        self.admin_window.show()

    def show_and_restart_timer(self):
        self.show()
        self.load_tables() # Odśwież po powrocie
        self.timer.start(5000) # Wznów odświeżanie

    def load_tables(self):
        tables = get_all_tables_status()
        
        # Wyczyść stary layout
        while self.tables_grid.count():
            item = self.tables_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # Uzupełnij nowy layout
        for i, table in enumerate(tables):
            row = i // 4
            col = i % 4
            
            btn = QPushButton(f"Stolik {table['no']}")
            btn.setFixedSize(150, 150)
            btn.setFont(QFont("Arial", 14))
            
            status = table['status']
            
            if status == 'free':
                btn.setProperty("btn_type", "table_free")
                btn.clicked.connect(lambda _, no=table['no']: self.open_order_view(no))
            elif status == 'active' and table['owner_id'] == self.waiter_id:
                btn.setProperty("btn_type", "table_mine")
                btn.setText(f"Stolik {table['no']}\n({self.waiter_name})")
                btn.clicked.connect(lambda _, no=table['no']: self.open_order_view(no))
            else: # active and owned by another waiter
                btn.setProperty("btn_type", "table_active")
                owner_name = USERS.get(table['owner_id'], 'Nieznany')
                btn.setText(f"Stolik {table['no']}\n({owner_name})")
                btn.setEnabled(False) # Nie można kliknąć stolika innego kelnera
                
            self.tables_grid.addWidget(btn, row, col)

    def open_order_view(self, table_no):
        self.timer.stop()
        self.hide()
        self.order_window = OrderWindow(table_no, self.waiter_id)
        self.order_window.closed.connect(self.show_and_restart_timer)
        self.order_window.show()

    def closeEvent(self, event):
        self.timer.stop()
        self.closed.emit()
        event.accept()

# KLASA OrderWindow

class OrderWindow(QWidget):
    closed = pyqtSignal()
    
    def __init__(self, table_no, waiter_id):
        super().__init__()
        self.table_no = table_no
        self.waiter_id = waiter_id
        self.waiter_name = USERS.get(waiter_id, "Nieznany")
        self.setWindowTitle(f"Stolik {table_no} - {self.waiter_name}")
        self.setFixedSize(1200, 800)
        self.menu_data = get_menu()
        self.current_category = None
        self.init_ui()
        self.load_orders()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # 1. Panel Menu (lewy)
        menu_panel = QWidget()
        menu_layout = QVBoxLayout(menu_panel)
        menu_panel.setFixedWidth(500)
        
        # Przyciski kategorii
        self.category_layout = QHBoxLayout()
        for category in self.menu_data.keys():
            btn = QPushButton(category)
            btn.setProperty("btn_type", "menu_category")
            btn.clicked.connect(lambda _, cat=category: self.display_menu_items(cat))
            self.category_layout.addWidget(btn)
            
        menu_layout.addLayout(self.category_layout)
        
        # Produkty w kategorii (Scroll Area)
        self.menu_items_area = QScrollArea()
        self.menu_items_area.setWidgetResizable(True)
        self.menu_items_widget = QWidget()
        self.menu_items_grid = QGridLayout(self.menu_items_widget)
        self.menu_items_area.setWidget(self.menu_items_widget)
        menu_layout.addWidget(self.menu_items_area)
        
        main_layout.addWidget(menu_panel)

        # 2. Panel Zamówienia (prawy)
        order_panel = QWidget()
        order_layout = QVBoxLayout(order_panel)
        order_layout.addWidget(QLabel(f"<h2>Rachunek - Stolik {self.table_no}</h2>"))
        
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(5)
        self.order_table.setHorizontalHeaderLabels(["Nazwa", "Ilość", "Cena jedn.", "Rabat (%)", "Suma"])
        self.order_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.order_table.customContextMenuRequested.connect(self.show_context_menu)
        order_layout.addWidget(self.order_table)
        
        # Podsumowanie i przyciski akcji
        self.summary_label = QLabel("Razem: 0.00 zł")
        self.summary_label.setFont(QFont("Arial", 16, QFont.Bold))
        order_layout.addWidget(self.summary_label)
        
        action_layout = QGridLayout()
        
        btn_send = QPushButton("Wyślij na Kuchnię")
        btn_send.setProperty("btn_type", "secondary")
        btn_send.clicked.connect(self.send_orders_to_kitchen)
        action_layout.addWidget(btn_send, 0, 0)

        btn_print = QPushButton("Drukuj Rachunek")
        btn_print.setProperty("btn_type", "secondary")
        btn_print.clicked.connect(self.print_bill)
        action_layout.addWidget(btn_print, 0, 1)

        btn_close = QPushButton("Zamknij Rachunek (PŁATNOŚĆ)")
        btn_close.setProperty("btn_type", "main_action")
        btn_close.clicked.connect(self.finalize_bill)
        action_layout.addWidget(btn_close, 1, 0, 1, 2)
        
        btn_back = QPushButton("Wróć do Stolików")
        btn_back.setProperty("btn_type", "numpad_clear")
        btn_back.clicked.connect(self.close)
        action_layout.addWidget(btn_back, 2, 0, 1, 2)
        
        order_layout.addLayout(action_layout)
        main_layout.addWidget(order_panel)
        
        # Ustaw domyślną kategorię
        if self.menu_data:
            first_category = next(iter(self.menu_data.keys()))
            self.display_menu_items(first_category)

    def display_menu_items(self, category):
        # Usuń stare przyciski
        while self.menu_items_grid.count():
            item = self.menu_items_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # Dodaj nowe
        items = self.menu_data.get(category, [])
        for i, (name, price) in enumerate(items):
            row = i // 2
            col = i % 2
            
            btn = QPushButton(f"{name}\n{price:.2f} zł")
            btn.setProperty("btn_type", "menu_item")
            btn.setFixedSize(220, 100)
            btn.clicked.connect(lambda _, n=name, p=price, c=category: self.add_item_to_order(n, p, c))
            self.menu_items_grid.addWidget(btn, row, col)

    def add_item_to_order(self, item_name, price, category):
        group_or_add_order(self.table_no, self.waiter_id, item_name, price, category)
        self.load_orders()

    def load_orders(self):
        orders = get_orders(self.table_no, status='aktywne')
        self.order_table.setRowCount(len(orders))
        
        total_sum = 0.0
        
        for row, order in enumerate(orders):
            total_sum += order['total_price']
            
            item_name = QTableWidgetItem(order['item_name'])
            # Wyróżnienie pozycji wysłanych/gotowych
            if order['status'] != 'nowe':
                item_name.setBackground(Qt.yellow if order['status'] == 'w realizacji' else Qt.green)
            
            self.order_table.setItem(row, 0, item_name)
            self.order_table.setItem(row, 1, QTableWidgetItem(str(order['qty'])))
            self.order_table.setItem(row, 2, QTableWidgetItem(f"{order['price']:.2f}"))
            self.order_table.setItem(row, 3, QTableWidgetItem(str(order['discount'])))
            self.order_table.setItem(row, 4, QTableWidgetItem(f"{order['total_price']:.2f}"))

        self.summary_label.setText(f"Razem: {total_sum:.2f} zł")
        self.order_table.resizeColumnsToContents()
        self.order_table.horizontalHeader().setStretchLastSection(True)

    def show_context_menu(self, pos):
        item = self.order_table.itemAt(pos)
        if item is None:
            return

        row = item.row()
        orders = get_orders(self.table_no, status='aktywne')
        order_id = orders[row]['id']
        order_status = orders[row]['status']

        menu = QMenu(self)
        
        # Opcja usunięcia (tylko dla statusu 'nowe')
        if order_status == 'nowe':
            action_remove = QAction("Usuń Pozycję", self)
            action_remove.triggered.connect(lambda: self.remove_item(order_id))
            menu.addAction(action_remove)
            
            action_discount = QAction("Dodaj Rabat (%)", self)
            action_discount.triggered.connect(lambda: self.apply_discount_dialog(order_id))
            menu.addAction(action_discount)

        # Opcja "W realizacji" (tylko dla statusu 'nowe') - opcjonalnie, zwykle używa się 'Wyślij na Kuchnię'
        # if order_status == 'nowe':
        #     action_send = QAction("Oznacz jako 'W realizacji'", self)
        #     action_send.triggered.connect(lambda: self.update_status(order_id, 'w realizacji'))
        #     menu.addAction(action_send)
            
        menu.exec_(self.order_table.mapToGlobal(pos))

    def remove_item(self, order_id):
        if QMessageBox.question(self, "Potwierdzenie", "Czy na pewno usunąć tę pozycję z zamówienia?", 
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if remove_order_item(order_id):
                self.load_orders()
            else:
                QMessageBox.warning(self, "Błąd", "Nie można usunąć pozycji, która została już wysłana do realizacji.")

    def apply_discount_dialog(self, order_id):
        orders = get_orders(self.table_no, status='aktywne')
        current_discount = next(o['discount'] for o in orders if o['id'] == order_id)
        
        discount, ok = QInputDialog.getInt(self, "Rabat", "Wprowadź procent rabatu (0-100):", current_discount, 0, 100)
        
        if ok:
            apply_discount(order_id, discount)
            self.load_orders()

    def send_orders_to_kitchen(self):
        if send_orders(self.table_no):
            QMessageBox.information(self, "Wysłano", "Nowe pozycje wysłano do realizacji.")
            self.load_orders()
        else:
            QMessageBox.warning(self, "Brak Nowych", "Brak nowych pozycji do wysłania.")

    def print_bill(self):
        # Generowanie widoku do druku
        orders = get_orders(self.table_no, status='aktywne')
        total_sum = sum(o['total_price'] for o in orders)
        
        output = PrintOutputWindow(self.table_no, self.waiter_name, orders, total_sum)
        output.exec_()
        
    def finalize_bill(self):
        if QMessageBox.question(self, "Zamknij Rachunek", "Czy na pewno chcesz zamknąć rachunek (płatność dokonana)?", 
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            finalize_bill_full(self.table_no, self.waiter_id)
            QMessageBox.information(self, "Rachunek Zamknięty", "Rachunek został zamknięty, stolik zwolniony.")
            self.close()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()

# KLASA PrintOutputWindow (PODGLĄD WYDRUKU)
class PrintOutputWindow(QDialog):
    def __init__(self, table_no, waiter_name, orders, total_sum):
        super().__init__()
        self.setWindowTitle("Podgląd Wydruku Rachunku")
        self.setFixedSize(400, 600)
        
        layout = QVBoxLayout(self)
        
        receipt_text = self.generate_receipt(table_no, waiter_name, orders, total_sum)
        
        self.label = QLabel(receipt_text)
        self.label.setProperty("label_type", "print_output")
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.label)
        layout.addWidget(scroll_area)
        
        btn_print = QPushButton("Drukuj (Symulacja)")
        btn_print.setProperty("btn_type", "main_action")
        btn_print.clicked.connect(self.accept)
        layout.addWidget(btn_print)

    def generate_receipt(self, table_no, waiter_name, orders, total_sum):
        # Formatowanie wydruku na wzór drukarki paragonowej
        lines = []
        lines.append("----------------------------------------")
        lines.append("         RESTAURACJA GASTRONOMA         ")
        lines.append("----------------------------------------")
        lines.append(f"STÓŁ: {table_no:<5} KELNER: {waiter_name:>18}")
        lines.append(f"DATA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<38}")
        lines.append("----------------------------------------")
        lines.append("NAZWA               QTY   CENA/JED.   SUMA")
        lines.append("----------------------------------------")

        for order in orders:
            price_unit = f"{order['price']:.2f}".replace('.', ',')
            qty = str(order['qty'])
            total_price = order['total_price']
            
            # Uwzględnij rabat w nazwie
            name = order['item_name']
            if order['discount'] > 0:
                name += f" (-{order['discount']}%)"
                
            name_short = name[:18].ljust(18)
            
            line = f"{name_short} {qty:>3} x {price_unit:>8} {total_price:6.2f}"
            line = line.replace('.', ',') # Lokalizacja
            lines.append(line)

        lines.append("----------------------------------------")
        lines.append(f"SUMA RAZEM: {total_sum:30.2f} ZŁ")
        lines.append("----------------------------------------")
        lines.append("            DZIĘKUJEMY!                 ")
        lines.append("----------------------------------------")
        
        return "\n".join(lines)

# --- START APLIKACJI ---
if __name__ == '__main__':
    # Upewnienie się, że baza danych jest zainicjowana
    init_db()
    
    app = QApplication(sys.argv)
    
    # 1. Ustawienie stylów
    app.setStyleSheet(get_stylesheet()) 
    
    # 2. Utworzenie głównego okna logowania
    login_window = LoginWindow()
    
    # 3. Definicja i połączenie akcji po pomyślnym zalogowaniu kelnera/admina
    def on_logged_in(waiter_id):
        # Jeśli to kelner (nie admin), otwieramy TablesWindow
        tables_window = TablesWindow(waiter_id)
        tables_window.closed.connect(login_window.show)
        tables_window.show()

    login_window.logged_in.connect(on_logged_in)
    
    # 4. WYŚWIETLENIE TYLKO OKNA LOGOWANIA!
    login_window.show() 
    
    # Uruchomienie pętli zdarzeń
    sys.exit(app.exec_())