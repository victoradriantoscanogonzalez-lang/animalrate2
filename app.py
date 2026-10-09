import os
import sqlite3
import json
import math
import uuid
import hashlib
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')

# Configuration
DB_FILE = os.path.join(BASE_DIR, 'animalrate.db')
UPLOAD_URL_PREFIX = 'assets/images/uploads'
UPLOAD_FOLDER = os.path.join(BASE_DIR, UPLOAD_URL_PREFIX)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ADMIN_PASSWORD = 'animalrate8admin'
VALID_PASSWORDS = {'animalrate8admin', 'admin'}
VALID_PASSWORD_HASHES = {'089eb5bd0b392be01d4cb2af71e3809e6229f1c0716daaac8d3b2e91f7a1c2cd'}
ADMIN_EMAIL = 'animalrate8@gmail.com'
VALID_CATEGORIES = ['Camaleones', 'Serpientes', 'Geckos', 'Terrarios', 'Ranas', 'Otro']

def check_auth(req):
    password = None
    email = None
    if req.is_json:
        data = req.get_json(silent=True) or {}
        password = data.get('password')
        email = data.get('usuario') or data.get('email')
    else:
        password = req.form.get('password')
        email = req.form.get('usuario') or req.form.get('email')

    if not password:
        return False

    password_str = str(password).strip()
    pwd_sha256 = hashlib.sha256(password_str.encode('utf-8')).hexdigest()

    is_valid_pwd = (
        password_str in VALID_PASSWORDS or
        password_str.lower() in VALID_PASSWORD_HASHES or
        pwd_sha256 in VALID_PASSWORD_HASHES
    )

    if not is_valid_pwd:
        return False

    if not email or email.strip().lower() != ADMIN_EMAIL.lower():
        return False

    return True

def normalize_category_name(cat_str):
    if not cat_str:
        return None
    cat_clean = cat_str.strip()
    # Strip diacritics for comparison so "Camaleónes" still matches "Camaleones"
    import unicodedata
    def strip_accents(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                       if unicodedata.category(c) != 'Mn')
    cat_norm = strip_accents(cat_clean).lower()
    for valid in VALID_CATEGORIES:
        if cat_norm == strip_accents(valid).lower():
            return valid
    return None

# Initialize Database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            descripcion TEXT,
            categoria TEXT NOT NULL,
            imagenes TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS rifas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imagen TEXT NOT NULL,
            total_boletos INTEGER NOT NULL,
            precio_boleto REAL NOT NULL,
            activa INTEGER DEFAULT 1
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS boletos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rifa_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            estado TEXT DEFAULT 'disponible',
            comprador TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.after_request
def add_no_cache_headers(response):
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Root route
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

# Admin route
@app.route('/admin')
def admin():
    return send_from_directory(BASE_DIR, 'admin.html')

# API Endpoints

# --- PRODUCTS ---
@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
    conn.close()
    
    result = []
    for p in products:
        try:
            imgs = json.loads(p['imagenes']) if p['imagenes'] else []
        except Exception:
            imgs = [p['imagenes']] if p['imagenes'] else []
        result.append({
            'id': p['id'],
            'nombre': p['nombre'],
            'precio': p['precio'],
            'descripcion': p['descripcion'],
            'categoria': p['categoria'],
            'imagenes': imgs
        })
    return jsonify(result)

@app.route('/api/products/<int:id>', methods=['GET'])
def get_single_product(id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    conn.close()
    if not product:
        return jsonify({'error': 'Producto no encontrado'}), 404
    try:
        imgs = json.loads(product['imagenes']) if product['imagenes'] else []
    except Exception:
        imgs = [product['imagenes']] if product['imagenes'] else []
    return jsonify({
        'id': product['id'],
        'nombre': product['nombre'],
        'precio': product['precio'],
        'descripcion': product['descripcion'],
        'categoria': product['categoria'],
        'imagenes': imgs
    })

@app.route('/api/products', methods=['POST'])
def add_product():
    if not check_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
        
    nombre = (request.form.get('nombre') or '').strip()
    precio_value = request.form.get('precio')
    descripcion = request.form.get('descripcion')
    categoria_raw = (request.form.get('categoria') or '').strip()

    try:
        precio = float(precio_value)
    except (TypeError, ValueError):
        return jsonify({'error': 'El precio debe ser un número válido'}), 400

    categoria = normalize_category_name(categoria_raw)
    if not nombre or not categoria or not math.isfinite(precio) or precio < 0:
        return jsonify({'error': 'Nombre, categoría válida y un precio válido son requeridos'}), 400
        
    imagenes = []
    files = request.files.getlist('imagenes')
    files = [file for file in files if file and file.filename]
    if not files or len(files) > 4:
        return jsonify({'error': 'Se requiere de 1 a 4 imágenes'}), 400

    for file in files:
        filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
        if not filename:
            return jsonify({'error': 'El nombre de una imagen no es válido'}), 400
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        imagenes.append(f"{UPLOAD_URL_PREFIX}/{filename}")
            
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO products (nombre, precio, descripcion, categoria, imagenes)
        VALUES (?, ?, ?, ?, ?)
    ''', (nombre, precio, descripcion, categoria, json.dumps(imagenes)))
    conn.commit()
    product_id = cursor.lastrowid
    conn.close()
    
    return jsonify({'success': True, 'id': product_id, 'categoria': categoria})

@app.route('/api/products/<int:id>', methods=['PUT', 'POST'])
def update_product(id):
    if not check_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    if not product:
        conn.close()
        return jsonify({'error': 'Producto no encontrado'}), 404

    if request.is_json:
        data = request.get_json(silent=True) or {}
        nombre = (data.get('nombre') or '').strip()
        precio_val = data.get('precio')
        descripcion = data.get('descripcion', '')
        categoria_raw = (data.get('categoria') or '').strip()
        imagenes = data.get('imagenes', None)
    else:
        nombre = (request.form.get('nombre') or '').strip()
        precio_val = request.form.get('precio')
        descripcion = request.form.get('descripcion', '')
        categoria_raw = (request.form.get('categoria') or '').strip()
        imagenes = None

        files = request.files.getlist('imagenes')
        files = [f for f in files if f and f.filename]
        if files:
            imagenes = []
            for file in files[:4]:
                filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                imagenes.append(f"{UPLOAD_URL_PREFIX}/{filename}")

    try:
        precio = float(precio_val)
    except (TypeError, ValueError):
        conn.close()
        return jsonify({'error': 'El precio debe ser un número válido'}), 400

    categoria = normalize_category_name(categoria_raw)
    if not nombre or not categoria or not math.isfinite(precio) or precio < 0:
        conn.close()
        return jsonify({'error': 'Nombre, categoría válida y un precio válido son requeridos'}), 400

    if imagenes is None:
        imagenes_json = product['imagenes']
    else:
        imagenes_json = json.dumps(imagenes)

    conn.execute('''
        UPDATE products
        SET nombre = ?, precio = ?, descripcion = ?, categoria = ?, imagenes = ?
        WHERE id = ?
    ''', (nombre, precio, descripcion, categoria, imagenes_json, id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': id, 'categoria': categoria})

@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    if not check_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
        
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# --- RIFAS ---
@app.route('/api/rifas/active', methods=['GET'])
def get_active_rifa():
    conn = get_db_connection()
    rifa = conn.execute('SELECT * FROM rifas WHERE activa = 1 ORDER BY id DESC LIMIT 1').fetchone()
    
    if not rifa:
        conn.close()
        return jsonify(None)
        
    boletos = conn.execute('SELECT * FROM boletos WHERE rifa_id = ? ORDER BY numero ASC', (rifa['id'],)).fetchall()
    conn.close()
    
    result = {
        'id': rifa['id'],
        'imagen': rifa['imagen'],
        'total_boletos': rifa['total_boletos'],
        'precio_boleto': rifa['precio_boleto'],
        'boletos': [{'numero': b['numero'], 'estado': b['estado'], 'comprador': b['comprador']} for b in boletos]
    }
    return jsonify(result)

@app.route('/api/rifas', methods=['POST'])
def create_rifa():
    if not check_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
        
    total_boletos = int(request.form.get('total_boletos', 0))
    precio_boleto = float(request.form.get('precio_boleto', 0))
    
    file = request.files.get('imagen')
    if not file or not file.filename:
        return jsonify({'error': 'Imagen es requerida'}), 400
        
    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    imagen_url = f"{UPLOAD_URL_PREFIX}/{filename}"
    
    conn = get_db_connection()
    conn.execute('UPDATE rifas SET activa = 0')
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO rifas (imagen, total_boletos, precio_boleto, activa)
        VALUES (?, ?, ?, 1)
    ''', (imagen_url, total_boletos, precio_boleto))
    rifa_id = cursor.lastrowid
    
    boletos_data = [(rifa_id, i, 'disponible', '') for i in range(1, total_boletos + 1)]
    cursor.executemany('''
        INSERT INTO boletos (rifa_id, numero, estado, comprador)
        VALUES (?, ?, ?, ?)
    ''', boletos_data)
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'id': rifa_id})

@app.route('/api/rifas/active', methods=['DELETE'])
def delete_active_rifa():
    if not check_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
        
    conn = get_db_connection()
    conn.execute('UPDATE rifas SET activa = 0 WHERE activa = 1')
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/rifas/boletos', methods=['PUT'])
def update_boletos():
    if not check_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json() or {}
    rifa_id = data.get('rifa_id')
    numeros = data.get('numeros', [])
    estado = data.get('estado', 'ocupado')
    comprador = data.get('comprador', '')
    
    if not rifa_id or not numeros:
        return jsonify({'error': 'Missing data'}), 400
        
    conn = get_db_connection()
    placeholders = ','.join('?' * len(numeros))
    query = f'''
        UPDATE boletos 
        SET estado = ?, comprador = ? 
        WHERE rifa_id = ? AND numero IN ({placeholders})
    '''
    params = [estado, comprador, rifa_id] + numeros
    conn.execute(query, params)
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/admin/login', methods=['POST'])
def login():
    if check_auth(request):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Credenciales incorrectas'}), 401

if __name__ == '__main__':
    app.run(port=3000, debug=True)
