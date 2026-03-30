from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
from database import Database
import io
import qrcode
import barcode
from barcode.writer import ImageWriter
from PIL import Image
import datetime
import hashlib

app = Flask(__name__)
app.secret_key = 'supersecretkey'
CORS(app)
db = Database()

# ---------- АВТОРИЗАЦИЯ ----------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    user = db.get_user(email, password)
    if user:
        session['user_id'] = user[0]
        session['user_email'] = user[1]
        session['user_role'] = user[2]
        return jsonify({'success': True, 'user': {'id': user[0], 'email': user[1], 'role': user[2]}})
    return jsonify({'success': False}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/current_user', methods=['GET'])
def current_user():
    if 'user_id' in session:
        return jsonify({'id': session['user_id'], 'email': session['user_email'], 'role': session['user_role']})
    return jsonify(None), 401

# ---------- ТОВАРЫ ----------
@app.route('/api/items', methods=['GET'])
def get_items():
    items = db.get_items()
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
def add_item():
    data = request.json
    barcodes = data.get('barcodes', [])
    price = float(data.get('price', 0))
    db.add_item(data['name'], data.get('params',''), data.get('serial_number',''),
                data.get('model',''), data.get('individual_code',''), data.get('ssuid',''),
                barcodes, price)
    return jsonify({'success': True})

@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    data = request.json
    db.update_item(item_id, data['name'], data.get('params',''), data.get('serial_number',''),
                   data.get('model',''), data.get('individual_code',''), data.get('ssuid',''),
                   float(data.get('price',0)))
    return jsonify({'success': True})

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    db.delete_item(item_id)
    return jsonify({'success': True})

# ---------- ГЕНЕРАЦИЯ QR / ШТРИХКОД ----------
@app.route('/api/generate/barcode/<code>')
def generate_barcode(code):
    try:
        bc_class = barcode.get_barcode_class('code128')
        bc = bc_class(code, writer=ImageWriter())
        buffer = io.BytesIO()
        bc.write(buffer)
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')
    except:
        return '', 400

@app.route('/api/generate/qrcode/<code>')
def generate_qrcode(code):
    img = qrcode.make(code)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png')

# ---------- ТРАНЗАКЦИИ АВИТО ----------
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    return jsonify(db.get_avito_transactions())

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    data = request.json
    success = db.add_avito_transaction(data['transaction_id'], data['type'], data['contact'],
                                       data['full_name'], session['user_id'], float(data['total_amount']))
    return jsonify({'success': success})

# ---------- ВЫСТАВКИ ----------
@app.route('/api/listings', methods=['GET'])
def get_listings():
    return jsonify(db.get_avito_listings())

@app.route('/api/listings', methods=['POST'])
def add_listing():
    data = request.json
    db.add_avito_listing(data['item_id'], data['status'], session['user_id'])
    return jsonify({'success': True})

@app.route('/api/listings/<int:listing_id>', methods=['PUT'])
def update_listing(listing_id):
    data = request.json
    db.update_avito_listing_status(listing_id, data['status'])
    return jsonify({'success': True})

# ---------- НАСТРОЙКИ ----------
@app.route('/api/settings', methods=['GET'])
def get_settings():
    keys = ['company_name', 'inn', 'tax_system', 'city_address', 'seller_position', 'seller_name', 'receipt_counter']
    settings = {k: db.get_setting(k, '') for k in keys}
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def set_settings():
    data = request.json
    for k, v in data.items():
        db.set_setting(k, v)
    return jsonify({'success': True})

# ---------- ПОЛЬЗОВАТЕЛИ (только админ) ----------
@app.route('/api/users', methods=['GET'])
def get_users():
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    users = db.get_all_users()
    return jsonify([{'id': u[0], 'email': u[1], 'role': u[2]} for u in users])

@app.route('/api/users', methods=['POST'])
def add_user():
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    data = request.json
    success = db.add_user(data['email'], data['password'], data['role'])
    return jsonify({'success': success})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    db.delete_user(user_id)
    return jsonify({'success': True})

@app.route('/api/users/<int:user_id>/role', methods=['PUT'])
def update_user_role(user_id):
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    data = request.json
    db.update_user_role(user_id, data['role'])
    return jsonify({'success': True})

# ---------- ЗАРПЛАТА (проценты) ----------
@app.route('/api/salary_percents', methods=['GET'])
def get_percents():
    percents = {}
    for role in ['admin', 'moderator', 'hr', 'watcher']:
        percents[role] = int(db.get_setting(f'percent_{role}', 20))
    return jsonify(percents)

@app.route('/api/salary_percents', methods=['POST'])
def set_percents():
    data = request.json
    for role, val in data.items():
        db.set_setting(f'percent_{role}', str(val))
    return jsonify({'success': True})

# ---------- ПИНПАД: QR со всеми товарами ----------
@app.route('/api/pinpad_qr')
def pinpad_qr():
    items = db.get_items()
    pinpad_id = request.args.get('pinpad_id', '000A')
    data = {"pinpad_id": pinpad_id, "items": items}
    import json
    json_str = json.dumps(data, ensure_ascii=False)
    img = qrcode.make(json_str)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png')

# ---------- ГЕНЕРАЦИЯ ЧЕКА (текст) ----------
@app.route('/api/receipt', methods=['POST'])
def generate_receipt():
    data = request.json
    transaction_id = data.get('transaction_id')
    item_id = data.get('item_id')
    payment_method = data.get('payment_method', 'Наличные')

    company_name = db.get_setting('company_name')
    inn = db.get_setting('inn')
    tax_system = db.get_setting('tax_system')
    city_address = db.get_setting('city_address')
    seller_position = db.get_setting('seller_position')
    seller_name = db.get_setting('seller_name')
    receipt_num = int(db.get_setting('receipt_counter', '1'))
    db.set_setting('receipt_counter', str(receipt_num+1))

    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    lines = [
        f"{'АВИТО ЧЕК':^50}",
        f"№ {receipt_num}",
        "="*50,
        f"Дата: {now}",
        f"Место: {city_address}",
        f"Организация: {company_name}",
        f"ИНН: {inn}",
        f"Система налогообложения: {tax_system}",
        "-"*50
    ]
    total = 0
    if transaction_id:
        trans = [t for t in db.get_avito_transactions() if t['transaction_id'] == transaction_id]
        if trans:
            t = trans[0]
            total = t['total_amount']
            lines.append(f"Транзакция: {t['transaction_id']}")
            lines.append(f"Покупатель: {t['full_name']}")
            lines.append(f"Сумма: {total:.2f} руб.")
    elif item_id:
        item = db.get_item_by_id(item_id)
        if item:
            total = item['price']
            lines.append(f"Товар: {item['name']}")
            lines.append(f"Цена: {total:.2f} руб.")
    lines.extend([
        "-"*50,
        f"Способ оплаты: {payment_method}",
        f"Продавец: {seller_position} {seller_name}",
        "="*50,
        "Спасибо за покупку!"
    ])
    receipt_text = "\n".join(lines)
    return jsonify({'receipt': receipt_text})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
