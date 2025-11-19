from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response 
from datetime import datetime
from fpdf import FPDF 
from db_functions import (
    init_db, USERS, get_all_tables_status, set_table_owner, get_table_owner, get_menu, 
    group_or_add_order, get_orders, get_active_orders_count, set_orders_status, 
    finalize_bill_full, get_all_waiter_summary, get_all_categories, add_menu_item 
)

# Inicjalizacja aplikacji Flask
app = Flask(__name__)
# WAŻNE! ZMIEŃ NA UNIKATOWY, TAJNY KLUCZ!
app.secret_key = 'twoj_bardzo_tajny_klucz_dla_sesji' 
app.config['DEBUG'] = True 

# Uruchomienie inicjalizacji bazy danych przy starcie
init_db()

@app.before_request
def make_session_permanent():
    """Ustawia sesję na stałą."""
    session.permanent = True

# --- LOGOWANIE ---
@app.route('/', methods=['GET', 'POST'])
def login():
    """Obsługa logowania PIN-em."""
    if request.method == 'POST':
        pin = request.form.get('pin')
        
        if pin in USERS:
            session['logged_in'] = True
            session['waiter_id'] = pin
            session['waiter_name'] = USERS[pin]
            
            if pin == "9999":
                # Przekierowanie admina do panelu
                return redirect(url_for('admin_panel')) 
            else:
                return redirect(url_for('tables')) 
        else:
            return render_template('login.html', error="Nieprawidłowy PIN.")
    
    if session.get('logged_in'):
        if session.get('waiter_id') == "9999":
            return redirect(url_for('admin_panel'))
        return redirect(url_for('tables'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Wylogowanie kelnera."""
    session.pop('logged_in', None)
    session.pop('waiter_id', None)
    session.pop('waiter_name', None)
    return redirect(url_for('login'))

# --- WIDOK STOLIKÓW ---
@app.route('/tables')
def tables():
    """Widok stolików."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    waiter_id = session['waiter_id']
    waiter_name = session['waiter_name']
    
    # Sprawdzenie, czy to ADMIN, jeśli tak, przekierowanie
    if waiter_id == '9999':
        return redirect(url_for('admin_panel'))
        
    table_statuses = get_all_tables_status() 
    
    tables_data = []
    for table_no, current_waiter_id in table_statuses: 
        
        has_active_orders = get_active_orders_count(table_no) > 0 
        owner_name = USERS.get(current_waiter_id, "Wolny")
        
        # Logika zwalniania stolika
        if current_waiter_id != '' and not has_active_orders:
             set_table_owner(table_no, '')
             current_waiter_id = ''
             owner_name = "Wolny"
             
        table_state = "free"
        is_enabled = True
        
        if current_waiter_id != '':
            table_state = "active"
            if current_waiter_id == waiter_id:
                table_state = "my_active"
            else:
                is_enabled = False 
                
        tables_data.append({
            'no': table_no,
            'owner': owner_name,
            'status': table_state,
            'is_enabled': is_enabled
        })

    return render_template('tables.html', 
                           waiter_name=waiter_name, 
                           waiter_id=waiter_id,
                           tables=tables_data)

# --- WIDOK ZAMÓWIENIA ---
@app.route('/table/<int:table_no>')
def order_view(table_no):
    """Widok do składania zamówień dla wybranego stolika."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    waiter_id = session['waiter_id']
    waiter_name = session['waiter_name']
    current_owner = get_table_owner(table_no)
    
    if current_owner == '' or current_owner == waiter_id:
        if current_owner == '':
            set_table_owner(table_no, waiter_id)
    else:
        return redirect(url_for('tables')) 
        
    menu_data = get_menu()
    orders_data = get_orders(table_no)
    
    total_bill = 0.0
    for _, _, _, total_qty, price, discount, _, _ in orders_data:
        price_val = price if price is not None else 0.0
        total_bill += total_qty * price_val * (1 - (discount if discount is not None else 0) / 100)
    
    default_category = next(iter(menu_data), "BRAK MENU")
        
    return render_template('order.html',
                           table_no=table_no,
                           waiter_name=waiter_name,
                           menu_data=menu_data,
                           orders=orders_data,
                           total_bill=total_bill,
                           default_category=default_category)

# --- API DODAWANIA POZYCJI ---
@app.route('/api/add_item', methods=['POST'])
def api_add_item():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Niezalogowany'}), 401
    
    data = request.get_json()
    table_no = data.get('table_no')
    item_name = data.get('item_name')
    category = data.get('category')
    price = data.get('price')
    waiter_id = session['waiter_id']
    
    if not all([table_no, item_name, category, price]):
        return jsonify({'success': False, 'message': 'Brak danych zamówienia'}), 400

    try:
        group_or_add_order(int(table_no), item_name, category, float(price), waiter_id)
        
        updated_orders = get_orders(int(table_no))
        total_bill = 0.0
        for _, _, _, total_qty, price, discount, _, _ in updated_orders:
            price_val = price if price is not None else 0.0
            total_bill += total_qty * price_val * (1 - (discount if discount is not None else 0) / 100)
            
        return jsonify({
            'success': True, 
            'message': 'Dodano pozycję', 
            'orders': updated_orders, 
            'total': f"{total_bill:.2f}"
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Błąd bazy danych: {e}'}), 500

# --- API WYSYŁANIA BONU ---
@app.route('/api/send_order', methods=['POST'])
def api_send_order():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Niezalogowany'}), 401
    
    data = request.get_json()
    table_no = data.get('table_no')
    
    if not table_no:
        return jsonify({'success': False, 'message': 'Brak numeru stolika'}), 400
    
    try:
        set_orders_status(int(table_no), 'wysłane')
        return jsonify({
            'success': True, 
            'message': 'Bon wysłany pomyślnie. Wróć do stolików.', 
            'redirect_url': url_for('tables')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Błąd bazy danych przy wysyłaniu bonu: {e}'}), 500


# --- API ZAMYKANIA RACHUNKU ---
@app.route('/api/finalize_bill', methods=['POST'])
def api_finalize_bill():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Niezalogowany'}), 401
    
    data = request.get_json()
    table_no = data.get('table_no')
    waiter_id = session['waiter_id']
    
    if not table_no:
        return jsonify({'success': False, 'message': 'Brak numeru stolika'}), 400

    try:
        if finalize_bill_full(int(table_no), waiter_id):
            return jsonify({
                'success': True, 
                'message': 'Rachunek zamknięty pomyślnie. Stolik wolny.', 
                'redirect_url': url_for('tables')
            })
        else:
            return jsonify({'success': False, 'message': 'Brak aktywnych zamówień do zamknięcia.'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Błąd bazy danych przy zamykaniu rachunku: {e}'}), 500

# --- WIDOK ADMINISTRATORA ---
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    """Główny panel administracyjny (wymagane ID 9999)."""
    if not session.get('logged_in') or session['waiter_id'] != '9999':
        return redirect(url_for('login'))
        
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # Pobieramy daty z formularza GET
    start_date = request.args.get('start_date', today_str)
    end_date = request.args.get('end_date', today_str)

    waiter_summary = get_all_waiter_summary(start_date, end_date)
    menu_categories = get_all_categories()

    return render_template('admin.html', 
                           waiter_summary=waiter_summary,
                           menu_categories=menu_categories,
                           start_date=start_date,
                           end_date=end_date)


# --- NOWA TRASA: GENEROWANIE RAPORTU PDF PRZEZ FPDF2 ---
@app.route('/admin/generate_report_pdf', methods=['GET'])
def api_generate_pdf():
    """Generuje raport sprzedaży kelnerów w formacie PDF używając FPDF2."""
    if not session.get('logged_in') or session['waiter_id'] != '9999':
        return redirect(url_for('login'))

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return "Brak podanych dat.", 400

    summary = get_all_waiter_summary(start_date, end_date)

    # -------------------- LOGIKA GENEROWANIA PDF (FPDF2) --------------------
    
    class PDF(FPDF):
        def __init__(self, orientation='P', unit='mm', format='A4'):
            super().__init__(orientation, unit, format)
            # KLUCZOWA POPRAWKA: Ustawienie kodowania na CP1250 dla obsługi polskich znaków
            self.set_doc_option('core_fonts_encoding', 'cp1250')

        def header(self):
            # Tytuł - używamy Arial, który teraz obsługuje CP1250
            self.set_font("Arial", "B", 16)
            self.cell(0, 10, "RAPORT SPRZEDAŻY KELNERÓW", 0, 1, "C") 
            self.set_font("Arial", "", 12)
            self.cell(0, 5, f"Okres: {start_date} do {end_date}", 0, 1, "C")
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font("Arial", "I", 8)
            self.cell(0, 10, f"Strona {self.page_no()}/{{nb}}", 0, 0, "C")
            
        def print_table(self, data):
            col_widths = [40, 50, 50, 50]
            
            # Nagłówek tabeli - używamy Arial
            self.set_font("Arial", 'B', 10)
            self.set_fill_color(0, 140, 186) 
            self.set_text_color(255, 255, 255)
            self.cell(col_widths[0], 7, "ID", 1, 0, 'C', True)
            self.cell(col_widths[1], 7, "Kelner", 1, 0, 'C', True)
            self.cell(col_widths[2], 7, "Rachunki", 1, 0, 'C', True)
            self.cell(col_widths[3], 7, "Sprzedaż (PLN)", 1, 1, 'C', True)

            # Wiersze danych - używamy Arial
            self.set_font("Arial", size=10)
            self.set_text_color(0, 0, 0)
            total_sales_sum = 0
            
            for waiter in data:
                sales = waiter['total_sales']
                total_sales_sum += sales
                
                self.cell(col_widths[0], 6, str(waiter['id']), 1, 0, 'C')
                self.cell(col_widths[1], 6, waiter['name'], 1, 0)
                self.cell(col_widths[2], 6, str(waiter['orders_count']), 1, 0, 'R')
                self.cell(col_widths[3], 6, f"{sales:.2f} zł", 1, 1, 'R')
                
            # Suma końcowa - używamy Arial
            self.set_font("Arial", 'B', 10)
            self.set_fill_color(220, 220, 220)
            self.cell(sum(col_widths[:-1]), 7, "SUMA CAŁKOWITA:", 1, 0, 'R', True)
            self.cell(col_widths[3], 7, f"{total_sales_sum:.2f} zł", 1, 1, 'R', True)

    pdf = PDF('P', 'mm', 'A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.print_table(summary)
    
    # Przygotowanie odpowiedzi HTTP
    response = make_response(pdf.output(dest='S'))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=raport_sprzedazy_{start_date}_do_{end_date}.pdf'
    return response


# --- API DODAWANIA POZYCJI MENU ---
@app.route('/api/add_item_admin', methods=['POST'])
def api_add_item_admin():
    """API do dodawania nowej pozycji menu (tylko ADMIN)."""
    if not session.get('logged_in') or session['waiter_id'] != '9999':
        return jsonify({'success': False, 'message': 'Brak dostępu'}), 403
        
    data = request.form
    
    name = data.get('name')
    price_str = data.get('price')
    category = data.get('category')
    
    if not name or not price_str or not category:
        return jsonify({'success': False, 'message': 'Brak wszystkich danych.'}), 400
        
    try:
        price = float(price_str.replace(',', '.'))
        add_menu_item(name, price, category.upper())
        return jsonify({'success': True, 'message': f'Dodano: {name} ({price:.2f} zł) do {category}'})
    except ValueError:
        return jsonify({'success': False, 'message': 'Nieprawidłowy format ceny.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Błąd bazy danych: {e}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)