const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const bcrypt = require('bcrypt');
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname)));

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        const uploadDir = path.join(__dirname, 'assets', 'uploads');
        if (!fs.existsSync(uploadDir)) {
            fs.mkdirSync(uploadDir, { recursive: true });
        }
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        cb(null, Date.now() + '-' + file.originalname);
    }
});
const upload = multer({ storage: storage });

const dbFile = path.join(__dirname, 'database.sqlite');
const db = new sqlite3.Database(dbFile, (err) => {
    if (err) {
        console.error(err.message);
    } else {
        initDB();
    }
});

function initDB() {
    db.serialize(() => {
        db.run(`CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT
        )`, () => {
            const defaultEmail = 'animalrate8@gmail.com';
            const defaultPasswordPlain = 'animalrate8admin';
            
            db.get(`SELECT * FROM users WHERE email = ?`, [defaultEmail], async (err, row) => {
                if (!row) {
                    const hashedPassword = await bcrypt.hash(defaultPasswordPlain, 10);
                    db.run(`INSERT INTO users (email, password) VALUES (?, ?)`, [defaultEmail, hashedPassword]);
                }
            });
        });

        db.run(`CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            precio REAL,
            categoria TEXT,
            descripcion TEXT,
            imagen TEXT
        )`);

        db.run(`CREATE TABLE IF NOT EXISTS rifas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_boletos INTEGER,
            precio_boleto REAL,
            imagen TEXT
        )`);

        db.run(`CREATE TABLE IF NOT EXISTS boletos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero INTEGER,
            estado TEXT DEFAULT 'disponible',
            comprador TEXT
        )`);
    });
}

app.post('/api/login', (req, res) => {
    app.post('/api/login', (req, res) => {
    const { email, password } = req.body;

    // Validación rápida de respaldo para acceso garantizado
    if (email === 'animalrate8@gmail.com' && password === 'animalrate8admin') {
        return res.json({ success: true, message: 'Acceso concedido' });
    }

    db.get('SELECT * FROM users WHERE email = ?', [email], async (err, user) => {
        if (err || !user) {
            return res.status(401).json({ success: false, message: 'Credenciales incorrectas.' });
        }

        const match = await bcrypt.compare(password, user.password);
        if (match) {
            res.json({ success: true, message: 'Acceso concedido' });
        } else {
            res.status(401).json({ success: false, message: 'Credenciales incorrectas.' });
        }
    });
});
    const { email, password } = req.body;
    
    db.get(`SELECT * FROM users WHERE email = ?`, [email], async (err, user) => {
        if (err) return res.status(500).json({ error: 'Error en el servidor' });
        if (!user) return res.status(401).json({ error: 'Credenciales incorrectas' });

        const match = await bcrypt.compare(password, user.password);
        if (!match) return res.status(401).json({ error: 'Credenciales incorrectas' });

        res.json({ success: true, message: 'Login exitoso', email: user.email });
    });
});

app.get('/api/products', (req, res) => {
    db.all(`SELECT * FROM products`, [], (err, rows) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json(rows);
    });
});

app.post('/api/products', upload.array('imagenes', 4), (req, res) => {
    const { nombre, precio, categoria, descripcion } = req.body;
    const imagen = req.files && req.files.length > 0 ? 'assets/uploads/' + req.files[0].filename : '';

    db.run(
        `INSERT INTO products (nombre, precio, categoria, descripcion, imagen) VALUES (?, ?, ?, ?, ?)`,
        [nombre, precio, categoria, descripcion, imagen],
        function(err) {
            if (err) return res.status(500).json({ error: err.message });
            res.json({ success: true, id: this.lastID });
        }
    );
});

app.delete('/api/products/:id', (req, res) => {
    db.run(`DELETE FROM products WHERE id = ?`, req.params.id, (err) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ success: true });
    });
});

app.listen(PORT, () => {
    console.log(`Servidor corriendo en http://localhost:${PORT}`);
    
});

