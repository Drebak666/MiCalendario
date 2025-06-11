import os
import datetime
import locale
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Config DB: usa DATABASE_URL en Railway o SQLite local
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL:
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tareas.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Tarea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.String(10), nullable=False)  # formato 'YYYY-MM-DD'
    texto = db.Column(db.Text, nullable=False)
    creada = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'fecha': self.fecha,
            'texto': self.texto,
            'creada': self.creada.isoformat()
        }

def init_db():
    with app.app_context():
        db.create_all()

@app.before_first_request
def crear_bd():
    init_db()

@app.route('/')
def inicio():
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
    except:
        pass
    hoy = datetime.datetime.now()
    fecha_actual = hoy.strftime('%A %d de %B de %Y').capitalize()
    return render_template('index.html', fecha_actual=fecha_actual)

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/ping')
def ping():
    return 'pong'

@app.route('/api/tareas/<fecha>', methods=['GET'])
def obtener_tareas(fecha):
    tareas = Tarea.query.filter_by(fecha=fecha).order_by(Tarea.creada).all()
    return jsonify([t.to_dict() for t in tareas])

@app.route('/api/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json() or {}
    fecha = data.get('fecha')
    texto = (data.get('texto') or '').strip()
    if not fecha or not texto:
        return jsonify({'error': 'Fecha y texto requeridos'}), 400
    nueva = Tarea(fecha=fecha, texto=texto)
    db.session.add(nueva)
    db.session.commit()
    return jsonify(nueva.to_dict()), 201

@app.route('/api/tareas/<int:id>', methods=['DELETE'])
def borrar_tarea(id):
    tarea = Tarea.query.get(id)
    if not tarea:
        return jsonify({'error': 'No encontrada'}), 404
    db.session.delete(tarea)
    db.session.commit()
    return jsonify({'result': 'ok'}), 200

@app.route('/api/tareas-mes/<mes_str>', methods=['GET'])
def tareas_por_mes(mes_str):
    try:
        year, mon = mes_str.split('-')
    except:
        return jsonify({'error': 'Formato inválido'}), 400
    like = f"{year}-{mon}-%"
    filas = Tarea.query.filter(Tarea.fecha.like(like)).all()
    fechas = sorted({t.fecha for t in filas})
    return jsonify(fechas)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
