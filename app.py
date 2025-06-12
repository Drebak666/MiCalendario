from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

db_path = 'tareas.db'

def init_db():
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tarea (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                texto TEXT NOT NULL
            )
        ''')

@app.route('/')
def index():
    from datetime import datetime
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    return render_template('index.html', fecha_actual=fecha_actual)

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/api/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json()
    fecha = data.get('fecha')
    texto = data.get('texto')
    if not fecha or not texto:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute('INSERT INTO tarea (fecha, texto) VALUES (?, ?)', (fecha, texto))
        tarea_id = cur.lastrowid
    return jsonify({"id": tarea_id, "fecha": fecha, "texto": texto}), 201

@app.route('/api/tareas/<fecha>', methods=['GET'])
def tareas_por_fecha(fecha):
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute('SELECT id, texto FROM tarea WHERE fecha = ?', (fecha,))
        filas = cur.fetchall()
    tareas = [{"id": f[0], "texto": f[1]} for f in filas]
    return jsonify(tareas)

@app.route('/api/tareas/<int:tarea_id>', methods=['DELETE'])
def borrar_tarea(tarea_id):
    with sqlite3.connect(db_path) as conn:
        conn.execute('DELETE FROM tarea WHERE id = ?', (tarea_id,))
    return jsonify({"status": "ok"})

@app.route('/api/tareas-mes/<mes>', methods=['GET'])
def tareas_por_mes(mes):
    try:
        datetime.strptime(mes + '-01', '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de mes inválido. Use YYYY-MM"}), 400

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute('SELECT DISTINCT fecha FROM tarea WHERE fecha LIKE ?', (mes + '%',))
        filas = cur.fetchall()
    fechas = [f[0] for f in filas]
    return jsonify(fechas)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
