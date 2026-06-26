import os, csv, io
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production')
raw_db = os.environ.get('DATABASE_URL')
if raw_db and raw_db.startswith('postgres://'):
    raw_db = raw_db.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db or 'sqlite:///tmart_mystery.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    role = db.Column(db.String(30), default='auditor')  # admin, manager, auditor
    focus = db.Column(db.String(160), default='')
    password_hash = db.Column(db.String(255), nullable=False)
    is_active_flag = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_active(self): return self.is_active_flag
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), default='')
    active = db.Column(db.Boolean, default=True)

class Audit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    audit_no = db.Column(db.String(30), unique=True, nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    auditor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    category = db.Column(db.String(120), nullable=False)
    item_type = db.Column(db.String(120), default='')
    product_name = db.Column(db.String(180), nullable=False)
    brand = db.Column(db.String(120), default='')
    supplier = db.Column(db.String(120), default='')
    packaging = db.Column(db.Integer, default=0)
    delivery_time = db.Column(db.Integer, default=0)
    packing = db.Column(db.Integer, default=0)
    taste = db.Column(db.Integer, default=0)
    ingredient = db.Column(db.Integer, default=0)
    expiry = db.Column(db.Integer, default=0)
    sensory = db.Column(db.Integer, default=0)
    availability_pct = db.Column(db.Float, default=0)
    stock_status = db.Column(db.String(40), default='partial')
    critical_available = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=0)
    rating = db.Column(db.String(40), default='POOR')
    notes = db.Column(db.Text, default='')
    photo = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    auditor = db.relationship('User')
    store = db.relationship('Store')

class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_no = db.Column(db.String(30), unique=True, nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    category = db.Column(db.String(120), default='')
    severity = db.Column(db.String(30), default='medium')
    status = db.Column(db.String(30), default='open')
    description = db.Column(db.Text, nullable=False)
    corrective_action = db.Column(db.Text, default='')
    due_date = db.Column(db.Date)
    photo = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    store = db.relationship('Store')
    assigned_to = db.relationship('User')

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def roles_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                flash('You do not have permission for this action.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return deco

def calc_rating(score):
    if score >= 90: return 'EXCELLENT'
    if score >= 80: return 'VERY GOOD'
    if score >= 70: return 'GOOD'
    if score >= 60: return 'FAIR'
    return 'POOR'

def calculate_score(form):
    weights = {'packaging':20,'delivery_time':15,'packing':15,'taste':15,'ingredient':10,'expiry':15,'sensory':10}
    earned = 0
    for k,w in weights.items():
        earned += w if form.get(k) == 'pass' else 0
    q = earned # out of 100
    av = min(max(float(form.get('availability_pct') or 0),0),100)
    av_score = (av/100)*10
    if form.get('critical_available') == 'on': av_score += 3
    if form.get('stock_status') == 'in-stock': av_score += 2
    final = round(q*0.85 + (av_score/15*100)*0.15)
    return int(final)

def save_upload(field='photo'):
    f = request.files.get(field)
    if not f or not f.filename: return ''
    name = datetime.utcnow().strftime('%Y%m%d%H%M%S_') + secure_filename(f.filename)
    f.save(os.path.join(app.config['UPLOAD_FOLDER'], name))
    return name

def seed():
    if not User.query.filter_by(username='admin').first():
        u=User(username='admin', full_name='System Admin', role='admin', focus='Quality Manager'); u.set_password('Admin@2024'); db.session.add(u)
        for username, name, focus in [('mark','Mark','New Suppliers'),('yara','Yara','New Suppliers'),('alia','Alia','PL Items'),('abdelmaged','Abdel Maged','Other Categories')]:
            x=User(username=username, full_name=name, role='auditor', focus=focus); x.set_password(username.capitalize()+'@2024'); db.session.add(x)
    if Store.query.count()==0:
        stores = [('DS01','talabat mart, New Maadi - Taqseem Laselky'),('DS03','talabat mart, El Rehab City'),('DS08','talabat mart, Nasr City - El Tayaran'),('DS19','talabat mart, Tagammoa 5 - Banks Center'),('DS40','Talabat Mart, Nasr City - Hay 8'),('DS59','EG Nasr City (3)'),('DS65','EG Suez')]
        for c,n in stores: db.session.add(Store(code=c, name=n))
    db.session.commit()

@app.before_request
def init_db():
    if not getattr(app, '_db_ready', False):
        db.create_all(); seed(); app._db_ready = True

@app.route('/')
def home(): return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u=User.query.filter_by(username=request.form['username'].strip()).first()
        if u and u.check_password(request.form['password']) and u.is_active:
            login_user(u); return redirect(url_for('dashboard'))
        flash('Incorrect username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    audits = Audit.query.all()
    issues = Issue.query.all()
    avg = round(sum(a.score for a in audits)/len(audits)) if audits else 0
    return render_template('dashboard.html', audits=audits, issues=issues, avg=avg)

@app.route('/audits')
@login_required
def audits():
    q = Audit.query.order_by(Audit.date.desc(), Audit.id.desc())
    if current_user.role == 'auditor': q = q.filter_by(auditor_id=current_user.id)
    return render_template('audits.html', audits=q.all())

@app.route('/audits/new', methods=['GET','POST'])
@login_required
def audit_new():
    if request.method == 'POST':
        score = calculate_score(request.form)
        a = Audit(audit_no='AUD-'+datetime.utcnow().strftime('%y%m%d%H%M%S'), date=datetime.strptime(request.form['date'],'%Y-%m-%d').date(), auditor_id=current_user.id, store_id=int(request.form['store_id']), category=request.form['category'], item_type=request.form.get('item_type',''), product_name=request.form['product_name'], brand=request.form.get('brand',''), supplier=request.form.get('supplier',''), packaging=1 if request.form.get('packaging')=='pass' else 0, delivery_time=1 if request.form.get('delivery_time')=='pass' else 0, packing=1 if request.form.get('packing')=='pass' else 0, taste=1 if request.form.get('taste')=='pass' else 0, ingredient=1 if request.form.get('ingredient')=='pass' else 0, expiry=1 if request.form.get('expiry')=='pass' else 0, sensory=1 if request.form.get('sensory')=='pass' else 0, availability_pct=float(request.form.get('availability_pct') or 0), stock_status=request.form.get('stock_status','partial'), critical_available=request.form.get('critical_available')=='on', score=score, rating=calc_rating(score), notes=request.form.get('notes',''), photo=save_upload())
        db.session.add(a); db.session.commit(); flash('Audit submitted successfully.', 'success'); return redirect(url_for('audits'))
    return render_template('audit_form.html', stores=Store.query.filter_by(active=True).order_by(Store.code).all(), today=date.today().isoformat())

@app.route('/audits/<int:id>/delete', methods=['POST'])
@login_required
@roles_required('admin','manager')
def audit_delete(id):
    db.session.delete(db.session.get(Audit,id)); db.session.commit(); flash('Audit deleted.', 'success'); return redirect(url_for('audits'))

@app.route('/issues')
@login_required
def issues(): return render_template('issues.html', issues=Issue.query.order_by(Issue.date.desc()).all())

@app.route('/issues/new', methods=['GET','POST'])
@login_required
def issue_new():
    if request.method == 'POST':
        due = request.form.get('due_date')
        issue=Issue(issue_no='ISS-'+datetime.utcnow().strftime('%y%m%d%H%M%S'), date=datetime.strptime(request.form['date'],'%Y-%m-%d').date(), store_id=int(request.form['store_id']), assigned_to_id=int(request.form['assigned_to_id']) if request.form.get('assigned_to_id') else None, category=request.form.get('category',''), severity=request.form.get('severity','medium'), status=request.form.get('status','open'), description=request.form['description'], corrective_action=request.form.get('corrective_action',''), due_date=datetime.strptime(due,'%Y-%m-%d').date() if due else None, photo=save_upload())
        db.session.add(issue); db.session.commit(); flash('Issue saved.', 'success'); return redirect(url_for('issues'))
    return render_template('issue_form.html', stores=Store.query.order_by(Store.code).all(), users=User.query.filter(User.role!='admin').all(), today=date.today().isoformat())

@app.route('/issues/<int:id>/close', methods=['POST'])
@login_required
def issue_close(id):
    i=db.session.get(Issue,id); i.status='closed'; i.corrective_action=request.form.get('corrective_action', i.corrective_action); db.session.commit(); flash('Issue closed.', 'success'); return redirect(url_for('issues'))

@app.route('/users')
@login_required
@roles_required('admin')
def users(): return render_template('users.html', users=User.query.order_by(User.id).all())

@app.route('/users/new', methods=['GET','POST'])
@app.route('/users/<int:id>/edit', methods=['GET','POST'])
@login_required
@roles_required('admin')
def user_form(id=None):
    u=db.session.get(User,id) if id else User()
    if request.method == 'POST':
        u.username=request.form['username'].strip(); u.full_name=request.form['full_name']; u.role=request.form['role']; u.focus=request.form.get('focus',''); u.is_active_flag=request.form.get('is_active')=='on'
        if request.form.get('password'): u.set_password(request.form['password'])
        if not id: db.session.add(u)
        db.session.commit(); flash('User saved.', 'success'); return redirect(url_for('users'))
    return render_template('user_form.html', user=u)

@app.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@roles_required('admin')
def user_delete(id):
    if id == current_user.id: flash('You cannot delete yourself.', 'danger')
    else: db.session.delete(db.session.get(User,id)); db.session.commit(); flash('User deleted.', 'success')
    return redirect(url_for('users'))

@app.route('/stores')
@login_required
def stores(): return render_template('stores.html', stores=Store.query.order_by(Store.code).all())

@app.route('/stores/new', methods=['GET','POST'])
@app.route('/stores/<int:id>/edit', methods=['GET','POST'])
@login_required
@roles_required('admin','manager')
def store_form(id=None):
    s=db.session.get(Store,id) if id else Store(active=True)
    if request.method=='POST':
        s.code=request.form['code'].strip().upper(); s.name=request.form['name']; s.city=request.form.get('city',''); s.active=request.form.get('active')=='on'
        if not id: db.session.add(s)
        db.session.commit(); flash('Store saved.', 'success'); return redirect(url_for('stores'))
    return render_template('store_form.html', store=s)

@app.route('/export/audits.csv')
@login_required
@roles_required('admin','manager')
def export_audits():
    out=io.StringIO(); w=csv.writer(out); w.writerow(['Audit No','Date','Auditor','Store','Category','Product','Supplier','Availability','Score','Rating','Notes'])
    for a in Audit.query.order_by(Audit.date.desc()).all(): w.writerow([a.audit_no,a.date,a.auditor.full_name,a.store.code,a.category,a.product_name,a.supplier,a.availability_pct,a.score,a.rating,a.notes])
    return Response(out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=audits.csv'})

@app.route('/uploads/<path:name>')
@login_required
def uploads(name): return send_from_directory(app.config['UPLOAD_FOLDER'], name)

if __name__ == '__main__':
    port=int(os.environ.get('PORT',5000)); app.run(host='0.0.0.0', port=port)
