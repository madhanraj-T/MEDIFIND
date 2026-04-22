"""
MediFind — AI-Powered Smart Hospital Locator & Appointment Booking System
app.py  |  Flask Backend Application

Run:
    pip install flask flask-sqlalchemy flask-cors flask-bcrypt flask-jwt-extended
    python app.py

Environment variables (set in .env or export):
    SECRET_KEY        — Flask session secret
    JWT_SECRET_KEY    — JWT signing key
    DATABASE_URL      — SQLAlchemy DB URI (default: sqlite:///medifind.db)
    ANTHROPIC_API_KEY — For AI chatbot (optional)
"""

import os
import math
import datetime
import secrets

from flask import Flask, request, jsonify, render_template, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from flask_cors import CORS


# ─────────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY']        = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['JWT_SECRET_KEY']    = os.getenv('JWT_SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///medifind.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=24)

db      = SQLAlchemy(app)
bcrypt  = Bcrypt(app)
jwt     = JWTManager(app)


# ─────────────────────────────────────────────
# Database Models
# ─────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(200), unique=True, nullable=False)
    phone      = db.Column(db.String(20), nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    appointments = db.relationship('Appointment', backref='user', lazy=True)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'email': self.email, 'phone': self.phone}


class Hospital(db.Model):
    __tablename__ = 'hospitals'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(200), nullable=False)
    address      = db.Column(db.String(300), nullable=False)
    latitude     = db.Column(db.Float, nullable=False)
    longitude    = db.Column(db.Float, nullable=False)
    rating       = db.Column(db.Float, default=0.0)
    badge        = db.Column(db.String(80))
    color        = db.Column(db.String(20), default='green')
    is_available = db.Column(db.Boolean, default=True)
    doctors      = db.relationship('Doctor', backref='hospital', lazy=True)

    def to_dict(self, distance_km=None):
        return {
            'id': self.id, 'name': self.name, 'address': self.address,
            'latitude': self.latitude, 'longitude': self.longitude,
            'rating': self.rating, 'badge': self.badge, 'color': self.color,
            'available': self.is_available,
            'distance': f'{distance_km:.1f} km' if distance_km is not None else None,
            'specs': list({d.specialization for d in self.doctors})
        }


class Doctor(db.Model):
    __tablename__ = 'doctors'
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    experience_yrs = db.Column(db.Integer, default=1)
    fee            = db.Column(db.Integer, default=500)
    initials       = db.Column(db.String(4))
    color          = db.Column(db.String(20), default='teal')
    hospital_id    = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)
    appointments   = db.relationship('Appointment', backref='doctor', lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'specialization': self.specialization,
            'experience': f'{self.experience_yrs} yrs', 'fee': f'₹{self.fee}',
            'initials': self.initials, 'color': self.color,
            'hospital': self.hospital.name if self.hospital else None,
            'hospital_id': self.hospital_id
        }


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id         = db.Column(db.Integer, primary_key=True)
    reference  = db.Column(db.String(30), unique=True, nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id  = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appt_date  = db.Column(db.Date, nullable=False)
    appt_time  = db.Column(db.String(10), nullable=False)
    reason     = db.Column(db.Text)
    status     = db.Column(db.String(20), default='confirmed')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'reference': self.reference,
            'doctor': self.doctor.name if self.doctor else None,
            'hospital': self.doctor.hospital.name if self.doctor and self.doctor.hospital else None,
            'date': str(self.appt_date), 'time': self.appt_time,
            'reason': self.reason, 'status': self.status
        }


# ─────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def generate_reference():
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return f'MF-{timestamp}-{secrets.token_hex(3).upper()}'


def get_available_slots(doctor_id, date_str):
    all_slots = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '13:00', '13:30', '14:00', '15:00', '15:30', '16:00'
    ]
    try:
        appt_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return all_slots
    booked = {
        a.appt_time for a in Appointment.query.filter_by(
            doctor_id=doctor_id, appt_date=appt_date, status='confirmed'
        ).all()
    }
    return [s for s in all_slots if s not in booked]


# ─────────────────────────────────────────────
# Routes — Frontend
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ─────────────────────────────────────────────
# Routes — Authentication
# ─────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    for field in ('name', 'email', 'phone', 'password'):
        if not data.get(field, '').strip():
            return jsonify({'success': False, 'message': f'{field} is required'}), 400
    if User.query.filter_by(email=data['email'].lower()).first():
        return jsonify({'success': False, 'message': 'Email already registered'}), 409
    hashed_pw = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    user = User(name=data['name'].strip(), email=data['email'].strip().lower(),
                phone=data['phone'].strip(), password=hashed_pw)
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=user.id)
    return jsonify({'success': True, 'token': token, 'user': user.to_dict()}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    user = User.query.filter_by(email=data.get('email', '').lower()).first()
    if not user or not bcrypt.check_password_hash(user.password, data.get('password', '')):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    token = create_access_token(identity=user.id)
    return jsonify({'success': True, 'token': token, 'user': user.to_dict()})


@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = User.query.get_or_404(get_jwt_identity())
    return jsonify(user.to_dict())


# ─────────────────────────────────────────────
# Routes — Hospitals
# ─────────────────────────────────────────────

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    try:
        lat    = float(request.args.get('lat', 0))
        lng    = float(request.args.get('lng', 0))
        radius = float(request.args.get('radius', 5))
    except ValueError:
        return jsonify({'error': 'Invalid coordinates'}), 400
    hospitals = Hospital.query.all()
    results = []
    for h in hospitals:
        if lat and lng:
            dist = haversine_km(lat, lng, h.latitude, h.longitude)
            if dist <= radius:
                results.append((dist, h))
        else:
            results.append((None, h))
    results.sort(key=lambda x: x[0] if x[0] is not None else 0)
    return jsonify([h.to_dict(dist) for dist, h in results])


@app.route('/api/hospitals/<int:hospital_id>', methods=['GET'])
def get_hospital(hospital_id):
    return jsonify(Hospital.query.get_or_404(hospital_id).to_dict())


# ─────────────────────────────────────────────
# Routes — Doctors
# ─────────────────────────────────────────────

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    spec    = request.args.get('specialization', '').strip()
    hosp_id = request.args.get('hospital_id', type=int)
    query = Doctor.query
    if spec:    query = query.filter(Doctor.specialization.ilike(f'%{spec}%'))
    if hosp_id: query = query.filter_by(hospital_id=hosp_id)
    return jsonify([d.to_dict() for d in query.all()])


@app.route('/api/doctors/<int:doctor_id>', methods=['GET'])
def get_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    date   = request.args.get('date', str(datetime.date.today()))
    data   = doctor.to_dict()
    data['available_slots'] = get_available_slots(doctor_id, date)
    return jsonify(data)


# ─────────────────────────────────────────────
# Routes — Appointments
# ─────────────────────────────────────────────

@app.route('/api/appointments', methods=['POST'])
@jwt_required()
def create_appointment():
    user_id = get_jwt_identity()
    data    = request.get_json()
    for field in ('doctor_id', 'date', 'time'):
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field} is required'}), 400
    doctor = Doctor.query.get(data['doctor_id'])
    if not doctor:
        return jsonify({'success': False, 'message': 'Doctor not found'}), 404
    try:
        appt_date = datetime.date.fromisoformat(data['date'])
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format (YYYY-MM-DD)'}), 400
    if appt_date < datetime.date.today():
        return jsonify({'success': False, 'message': 'Cannot book past dates'}), 400
    available = get_available_slots(data['doctor_id'], data['date'])
    if data['time'] not in available:
        return jsonify({'success': False, 'message': 'This slot is already booked'}), 409
    appointment = Appointment(
        reference=generate_reference(), user_id=user_id,
        doctor_id=data['doctor_id'], appt_date=appt_date,
        appt_time=data['time'], reason=data.get('reason', '').strip()
    )
    db.session.add(appointment)
    db.session.commit()
    return jsonify({'success': True, 'reference': appointment.reference,
                    'appointment': appointment.to_dict()}), 201


@app.route('/api/appointments', methods=['GET'])
@jwt_required()
def get_user_appointments():
    user_id = get_jwt_identity()
    return jsonify([a.to_dict() for a in Appointment.query.filter_by(user_id=user_id).all()])


@app.route('/api/appointments/<int:appt_id>/cancel', methods=['PATCH'])
@jwt_required()
def cancel_appointment(appt_id):
    user_id     = get_jwt_identity()
    appointment = Appointment.query.get_or_404(appt_id)
    if appointment.user_id != user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    appointment.status = 'cancelled'
    db.session.commit()
    return jsonify({'success': True, 'appointment': appointment.to_dict()})


# ─────────────────────────────────────────────
# Routes — Chatbot
# ─────────────────────────────────────────────

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    data    = request.get_json()
    message = (data or {}).get('message', '').strip()
    if not message:
        return jsonify({'reply': 'Please type a message.'}), 400

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        try:
            import anthropic
            client  = anthropic.Anthropic(api_key=api_key)
            system  = (
                "You are MediFind's helpful AI health assistant. "
                "You help users find nearby hospitals in Chennai, look up doctors by specialization, "
                "check availability, and understand how to book appointments. "
                "Keep replies concise (2–4 sentences). Do not provide medical diagnoses."
            )
            response = client.messages.create(
                model='claude-opus-4-6', max_tokens=256,
                system=system, messages=[{'role': 'user', 'content': message}]
            )
            return jsonify({'reply': response.content[0].text})
        except Exception as e:
            app.logger.error(f'Claude API error: {e}')

    # Keyword fallback
    m = message.lower()
    if any(k in m for k in ('hospital', 'near', 'close', 'nearby')):
        reply = ('Apollo Hospitals on Greams Road (1.2 km) is the closest, rated 4.8★. '
                 'Would you like to book an appointment there?')
    elif any(k in m for k in ('cardio', 'heart', 'ortho', 'neuro', 'doctor', 'specialist')):
        reply = ('Dr. Priya Nair (Cardiologist, Apollo, ₹800) has availability today. '
                 'Use the Doctors page to browse all specialists and book a slot.')
    elif any(k in m for k in ('book', 'appoint', 'schedule', 'slot')):
        reply = ("Go to the Book tab, select your hospital and doctor, choose a time slot, and confirm. "
                 "You'll receive a reference code immediately.")
    elif any(k in m for k in ('fee', 'cost', 'price', 'charge')):
        reply = ('Consultation fees: General Physicians from ₹400, Specialists ₹500–₹900.')
    elif any(k in m for k in ('cancel', 'reschedule')):
        reply = ('Go to Profile → My Appointments and tap Cancel. Full refunds within 3 business days.')
    else:
        reply = ("I'm here to help! Ask me about nearby hospitals, doctor availability, or how to book.")

    return jsonify({'reply': reply})


# ─────────────────────────────────────────────
# Database Seeding
# ─────────────────────────────────────────────

def seed_database():
    if Hospital.query.count() > 0:
        return
    hospitals_data = [
        ('Apollo Hospitals',      'Greams Road, Chennai',          13.0569, 80.2500, 4.8, 'Multi-Specialty',  'green'),
        ('MIOT International',    'Mount Poonamallee Rd, Chennai', 13.0130, 80.1690, 4.7, 'Tertiary Care',    'blue'),
        ('Fortis Malar Hospital', 'Gandhi Nagar, Adyar, Chennai',  13.0047, 80.2565, 4.6, 'Super-Specialty',  'coral'),
        ('Global Health City',    'Perumbakkam, Chennai',           12.9201, 80.2087, 4.9, 'Transplant Centre','purple'),
        ('Vijaya Hospital',       'NSK Salai, Vadapalani',          13.0523, 80.2116, 4.5, 'General',          'green'),
        ('Sri Ramachandra',       'Porur, Chennai',                 13.0338, 80.1649, 4.7, 'Teaching Hospital','blue'),
    ]
    for name, addr, lat, lng, rating, badge, color in hospitals_data:
        db.session.add(Hospital(name=name, address=addr, latitude=lat, longitude=lng,
                                rating=rating, badge=badge, color=color))
    db.session.flush()
    hospitals = {h.name: h for h in Hospital.query.all()}
    doctors_data = [
        ('Dr. Priya Nair',   'Cardiologist',       14, 800, 'PN', 'teal',   'Apollo Hospitals'),
        ('Dr. Arjun Mehta',  'Orthopedic Surgeon', 11, 600, 'AM', 'blue',   'MIOT International'),
        ('Dr. Sneha Raman',  'Neurologist',          9, 900, 'SR', 'coral', 'Global Health City'),
        ('Dr. Vikram Bose',  'General Physician',    7, 400, 'VB', 'purple','Vijaya Hospital'),
        ('Dr. Kavya Iyer',   'Gynecologist',        12, 700, 'KI', 'amber', 'Fortis Malar Hospital'),
        ('Dr. Rajan Pillai', 'ENT Specialist',      16, 500, 'RP', 'teal',  'Sri Ramachandra'),
        ('Dr. Meera Suresh', 'Dermatologist',        8, 650, 'MS', 'blue',  'Apollo Hospitals'),
        ('Dr. Kiran Anand',  'Pediatrician',        13, 550, 'KA', 'coral', 'Fortis Malar Hospital'),
    ]
    for name, spec, exp, fee, init, color, hosp_name in doctors_data:
        hosp = hospitals.get(hosp_name)
        if hosp:
            db.session.add(Doctor(name=name, specialization=spec, experience_yrs=exp,
                                  fee=fee, initials=init, color=color, hospital_id=hosp.id))
    db.session.commit()
    print('[MediFind] Database seeded.')


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_database()
    app.run(debug=os.getenv('FLASK_ENV', 'development') == 'development',
            host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
