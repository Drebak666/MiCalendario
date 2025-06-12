from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
# ELIMINA ESTA LÍNEA: import sqlite3
from datetime import datetime
import os

# AÑADE ESTAS LÍNEAS:
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
CORS(app)

# ELIMINA ESTAS 2 LÍNEAS (porque ya no usaremos el archivo local db_path para la base de datos):
# db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'tareas.db')
# print(f"La base de datos se creará/usará en: {db_path}")

# AÑADE ESTAS 3 LÍNEAS para configurar la conexión a Supabase (usará DATABASE_URL de Render)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///tareas.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) # Inicializamos SQLAlchemy

# AÑADE ESTA CLASE para definir tu tabla 'tarea' para SQLAlchemy
class Tarea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Text, nullable=False)
    texto = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Tarea {self.id}: {self.fecha} - {self.texto}>'

def init_db():
    try:
        # CAMBIA ESTO:
        # with sqlite3.connect(db_path) as conn:
        #     conn.execute('''
        #         CREATE TABLE IF NOT EXISTS tarea (
        #             id INTEGER PRIMARY KEY AUTOINCREMENT,
        #             fecha TEXT NOT NULL,
        #             texto TEXT NOT NULL
        #         )
        #     ''')
        # A ESTO (para que SQLAlchemy cree las tablas en Supabase):
        with app.app_context():
            db.create_all()
        print("Base de datos inicializada correctamente.")
    except Exception as e: # Cambiado a Exception para capturar errores de SQLAlchemy
        print(f"Error al inicializar la base de datos: {e}")

@app.route('/')
def index():
    # from datetime import datetime # Ya está importado arriba, puedes quitarlo si quieres
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    return render_template('index.html', fecha_actual=fecha_actual)

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/api/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json()
    print(f"Datos recibidos para crear_tarea: {data}")

    fecha = data.get('fecha')
    texto = data.get('texto')

    if not fecha or not texto:
        print("Error: Faltan datos (fecha o texto)")
        return jsonify({"error": "Faltan datos (fecha o texto)"}), 400

    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        print(f"Error: Formato de fecha inválido para {fecha}. Se esperaba YYYY-MM-DD")
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    try:
        # CAMBIA ESTO (operación con sqlite3):
        # with sqlite3.connect(db_path) as conn:
        #     cur = conn.execute('INSERT INTO tarea (fecha, texto) VALUES (?, ?)', (fecha, texto))
        #     conn.commit()
        #     tarea_id = cur.lastrowid
        # A ESTO (operación con SQLAlchemy):
        nueva_tarea = Tarea(fecha=fecha, texto=texto)
        db.session.add(nueva_tarea)
        db.session.commit()
        tarea_id = nueva_tarea.id # SQLAlchemy ya asigna el ID
        print(f"Tarea '{texto}' guardada con ID: {tarea_id} para la fecha: {fecha}")
        return jsonify({"id": tarea_id, "fecha": fecha, "texto": texto}), 201
    except Exception as e: # Cambiado a Exception para capturar errores de SQLAlchemy
        db.session.rollback() # MUY IMPORTANTE: Deshace cambios si hay error
        print(f"Error al insertar la tarea en la base de datos: {e}")
        return jsonify({"error": f"Error al guardar la tarea: {e}"}), 500

@app.route('/api/tareas/<fecha>', methods=['GET'])
def tareas_por_fecha(fecha):
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

    # CAMBIA ESTO (operación con sqlite3):
    # with sqlite3.connect(db_path) as conn:
    #     cur = conn.execute('SELECT id, texto FROM tarea WHERE fecha = ?', (fecha,))
    #     filas = cur.fetchall()
    # tareas = [{"id": f[0], "texto": f[1]} for f in filas]
    # A ESTO (operación con SQLAlchemy):
    tareas_db = Tarea.query.filter_by(fecha=fecha).all()
    tareas = [{"id": t.id, "texto": t.texto} for t in tareas_db]
    return jsonify(tareas)

@app.route('/api/tareas/<int:tarea_id>', methods=['DELETE'])
def borrar_tarea(tarea_id):
    try:
        # CAMBIA ESTO (operación con sqlite3):
        # with sqlite3.connect(db_path) as conn:
        #     conn.execute('DELETE FROM tarea WHERE id = ?', (tarea_id,))
        #     conn.commit()
        # A ESTO (operación con SQLAlchemy):
        tarea_a_borrar = Tarea.query.get(tarea_id)
        if tarea_a_borrar:
            db.session.delete(tarea_a_borrar)
            db.session.commit()
            print(f"Tarea con ID {tarea_id} eliminada.")
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Tarea no encontrada"}), 404
    except Exception as e: # Cambiado a Exception para capturar errores de SQLAlchemy
        db.session.rollback() # Deshace cambios si hay error
        print(f"Error al borrar la tarea: {e}")
        return jsonify({"error": f"Error al borrar la tarea: {e}"}), 500


@app.route('/api/tareas-mes/<mes>', methods=['GET'])
def tareas_por_mes(mes):
    try:
        datetime.strptime(mes + '-01', '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Formato de mes inválido. Use YYYY-MM"}), 400

    # CAMBIA ESTO (operación con sqlite3):
    # with sqlite3.connect(db_path) as conn:
    #     cur = conn.execute('SELECT DISTINCT fecha FROM tarea WHERE fecha LIKE ?', (mes + '%',))
    #     filas = cur.fetchall()
    # fechas = [f[0] for f in filas]
    # A ESTO (operación con SQLAlchemy):
    fechas_distintas = db.session.query(Tarea.fecha).filter(Tarea.fecha.like(mes + '%')).distinct().all()
    fechas = [f[0] for f in fechas_distintas]
    return jsonify(fechas)

if __name__ == '__main__':
    # Esto sigue siendo igual, pero ahora init_db() usará SQLAlchemy
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)