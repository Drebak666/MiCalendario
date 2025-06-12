from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os # Importar el módulo os para rutas absolutas

app = Flask(__name__)
CORS(app)

# Definir la ruta de la base de datos de forma más robusta
# Usamos os.path.join para construir la ruta de manera compatible con diferentes sistemas operativos
# y os.path.abspath para obtener la ruta absoluta
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'tareas.db')
print(f"La base de datos se creará/usará en: {db_path}") # Esto es útil para depurar

def init_db():
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tarea (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    texto TEXT NOT NULL
                )
            ''')
        print("Base de datos inicializada correctamente.")
    except sqlite3.Error as e:
        print(f"Error al inicializar la base de datos: {e}")

@app.route('/')
def index():
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    return render_template('index.html', fecha_actual=fecha_actual)

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/api/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json()
    print(f"Datos recibidos para crear_tarea: {data}") # Depuración: Imprime los datos recibidos

    fecha = data.get('fecha')
    texto = data.get('texto')

    if not fecha or not texto:
        print("Error: Faltan datos (fecha o texto)")
        return jsonify({"error": "Faltan datos (fecha o texto)"}), 400

    try:
        # Validar el formato de la fecha antes de intentar insertar
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        print(f"Error: Formato de fecha inválido para {fecha}. Se esperaba YYYY-MM-DD")
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute('INSERT INTO tarea (fecha, texto) VALUES (?, ?)', (fecha, texto))
            conn.commit() # ¡Importante! Asegúrate de hacer commit para guardar los cambios
            tarea_id = cur.lastrowid
            print(f"Tarea '{texto}' guardada con ID: {tarea_id} para la fecha: {fecha}")
        return jsonify({"id": tarea_id, "fecha": fecha, "texto": texto}), 201
    except sqlite3.Error as e:
        print(f"Error al insertar la tarea en la base de datos: {e}")
        return jsonify({"error": f"Error al guardar la tarea: {e}"}), 500

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
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute('DELETE FROM tarea WHERE id = ?', (tarea_id,))
            conn.commit()
        print(f"Tarea con ID {tarea_id} eliminada.")
        return jsonify({"status": "ok"})
    except sqlite3.Error as e:
        print(f"Error al borrar la tarea: {e}")
        return jsonify({"error": f"Error al borrar la tarea: {e}"}), 500


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
