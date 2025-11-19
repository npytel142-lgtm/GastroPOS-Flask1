import sqlite3
from datetime import datetime 

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
}

# --- BAZA DANYCH (FUNKCJE GLOBALNE) ---
DB_NAME = "db.sqlite"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            price REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tables_status (
            table_no INTEGER PRIMARY KEY,
            waiter_id TEXT 
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_no INTEGER,
            item TEXT,
            category TEXT,
            qty INTEGER,
            price REAL,
            discount_percent REAL DEFAULT 0.0,
            status TEXT,
            notes TEXT DEFAULT '',
            waiter_id TEXT DEFAULT '9998',
            finish_timestamp TEXT DEFAULT ''
        )
    """)
    
    # Sprawdzenie i dodanie brakujących kolumn
    try:
        c.execute("SELECT notes FROM orders LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE orders ADD COLUMN notes TEXT DEFAULT ''")
    
    try: 
        c.execute("SELECT waiter_id FROM orders LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE orders ADD COLUMN waiter_id TEXT DEFAULT '9998'")

    try: 
        c.execute("SELECT discount_percent FROM orders LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE orders ADD COLUMN discount_percent REAL DEFAULT 0.0")

    # Dodanie kolumny finish_timestamp
    try: 
        c.execute("SELECT finish_timestamp FROM orders LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE orders ADD COLUMN finish_timestamp TEXT DEFAULT ''")

    conn.commit()
    
    # Inicjalizacja stolików (9 pustych stolików)
    c.execute("SELECT COUNT(*) FROM tables_status")
    if c.fetchone()[0] == 0:
        for i in range(1, 10):
            c.execute("INSERT INTO tables_status (table_no, waiter_id) VALUES (?, ?)", (i, ''))
        conn.commit()
    
    # Inicjalizacja menu (tylko jeśli jest puste)
    c.execute("SELECT COUNT(*) FROM menu")
    if c.fetchone()[0] == 0:
        initial_menu = [
            ("Bruschetta z pomidorami", "PRZYSTAWKI", 18.00),
            ("Krewetki na maśle i czosnku", "PRZYSTAWKI", 35.00),
            ("Zupa Pomidorowa", "ZUPY", 15.00), 
            ("Stek z polędwicy (200g)", "DANIA GŁÓWNE", 79.00),
            ("Kotlet Schabowy", "DANIA GŁÓWNE", 38.00),
            ("Pizza Margherita", "PIZZA", 35.00), 
            ("Sałatka Cezar", "SAŁATKI", 38.00),
            ("Deser Tiramisu", "DESERY", 22.00),
            ("Kawa Espresso", "NAPOJE GORĄCE", 12.00), 
            ("Cola 0.5l", "NAPOJE ZIMNE", 8.00), 
            ("Piwo Żywiec", "ALKOHOLE", 15.00),
            ("Wino Czerwone (kieliszek)", "ALKOHOLE", 25.00),
            ("Wódka Wyborowa 50ml", "ALKOHOLE", 18.00),
        ]
        
        for name, category, price in initial_menu:
            c.execute("INSERT INTO menu (name, category, price) VALUES (?, ?, ?)", (name, category, price))
        conn.commit()
        
    conn.close()

# --- FUNKCJE ZARZĄDZANIA MENU ---
def get_all_menu_items():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, category, price FROM menu ORDER BY category, name")
    items = c.fetchall()
    conn.close()
    return items

def delete_menu_item_by_id(item_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM menu WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return c.rowcount

def add_menu_item(name, price, category):
    """Dodaje nową pozycję do menu."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", (name, price, category))
    conn.commit()
    conn.close()
    
def get_all_categories():
    """Pobiera listę unikalnych kategorii menu."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM menu ORDER BY category")
    categories = [row[0] for row in c.fetchall()]
    conn.close()
    return categories

# --- FUNKCJE BAZY DANYCH (Pozostałe) ---
def get_table_owner(table_no):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT waiter_id FROM tables_status WHERE table_no=?", (table_no,))
    owner = c.fetchone()
    conn.close()
    return owner[0] if owner else ''

def set_table_owner(table_no, waiter_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE tables_status SET waiter_id=? WHERE table_no=?", (waiter_id, table_no))
    conn.commit()
    conn.close()

def get_active_orders_count(table_no):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE table_no=? AND status IN ('nowe', 'wysłane')", (table_no,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_all_tables_status():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT table_no, waiter_id FROM tables_status ORDER BY table_no")
    statuses = c.fetchall()
    conn.close()
    return statuses

def get_menu():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name, category, price FROM menu ORDER BY category, name")
    raw_menu = c.fetchall()
    conn.close()
    
    grouped_menu = {}
    for name, category, price in raw_menu:
        key = category.upper() 
        if key not in grouped_menu:
            grouped_menu[key] = []
        grouped_menu[key].append((name, price))
        
    return grouped_menu

def add_menu_item_to_db(name, category, price):
    add_menu_item(name, price, category)

def get_orders(table_no, order_ids=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    base_query = """
        SELECT MIN(id) as id, item, category, SUM(qty) as total_qty, price, discount_percent, status, notes
        FROM orders
        WHERE table_no=? AND status IN ('nowe', 'wysłane')
    """
    params = [table_no]
    
    if order_ids is not None and order_ids:
        placeholders = ','.join('?' for _ in order_ids)
        base_query += f" AND id IN ({placeholders})"
        params.extend(order_ids)

    base_query += """
        GROUP BY item, category, price, discount_percent, status, notes
        ORDER BY status DESC, id
    """
    
    c.execute(base_query, tuple(params))
    orders = c.fetchall()
    conn.close()
    
    return orders

def group_or_add_order(table_no, item, category, price, waiter_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("""
        SELECT id, qty
        FROM orders
        WHERE table_no=? AND item=? AND status='nowe'
        AND waiter_id=? AND discount_percent=0.0 AND notes=''
    """, (table_no, item, waiter_id))
    
    existing_order = c.fetchone()
    
    if existing_order:
        order_id, current_qty = existing_order
        new_qty = current_qty + 1
        c.execute("UPDATE orders SET qty=? WHERE id=?", (new_qty, order_id))
        conn.commit()
    else:
        c.execute("INSERT INTO orders (table_no, item, category, qty, price, discount_percent, status, waiter_id) VALUES (?, ?, ?, ?, ?, 0.0, ?, ?)",
                  (table_no, item, category.upper(), 1, price, "nowe", waiter_id))
        conn.commit()
        
    conn.close()
    return True 

def set_orders_status(table_no, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE orders SET status=? WHERE table_no=? AND status='nowe'", (status, table_no))
    conn.commit()
    conn.close()

def finalize_bill_full(table_no, waiter_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
    
    c.execute("""
        SELECT id, qty
        FROM orders 
        WHERE table_no=? AND status IN ('nowe', 'wysłane')
    """, (table_no,))
    
    item_ids_to_finalize = [row[0] for row in c.fetchall()]
    
    if not item_ids_to_finalize:
        conn.close()
        return False
        
    placeholders = ','.join('?' for _ in item_ids_to_finalize)
    c.execute(f"""
        UPDATE orders SET status='zakończone', waiter_id=?, finish_timestamp=?
        WHERE id IN ({placeholders})
    """, (waiter_id, current_time, *item_ids_to_finalize))

    conn.commit()
    conn.close()
    
    if get_active_orders_count(table_no) == 0:
        set_table_owner(table_no, '')
        
    return True

# --- FUNKCJE RAPORTOWE ---

def get_waiter_summary(waiter_id, start_date, end_date):
    """Pobiera sumę sprzedaży i liczbę obsłużonych rachunków dla kelnera w danym zakresie dat."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Przekształcamy daty, aby obejmowały cały dzień (od 00:00:00 do 23:59:59)
    start_dt = f"{start_date} 00:00:00"
    end_dt = f"{end_date} 23:59:59"
    
    # Używamy finish_timestamp do zliczania unikalnych zamkniętych rachunków
    c.execute("""
        SELECT 
            COUNT(DISTINCT finish_timestamp), 
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

def get_all_waiter_summary(start_date, end_date):
    """Pobiera podsumowanie dla wszystkich kelnerów."""
    
    global USERS 
    
    summary = []
    # Wykluczamy ID ADMINA (9999) i domyślne ID (9998)
    waiter_ids = [k for k in USERS.keys() if k not in ('9999', '9998')] 

    for waiter_id in waiter_ids:
        orders_count, total_sales = get_waiter_summary(waiter_id, start_date, end_date)
        
        summary.append({
            'id': waiter_id,
            'name': USERS[waiter_id],
            'orders_count': orders_count if orders_count else 0,
            'total_sales': round(total_sales, 2)
        })
        
    return summary