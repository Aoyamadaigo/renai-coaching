from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'amour-dev-key-change-in-production')

_db_url = os.environ.get('DATABASE_URL', 'sqlite:///amour.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'ログインが必要です。'


# ── Models ───────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id           = db.Column(db.Integer, primary_key=True)
    email        = db.Column(db.String(120), unique=True, nullable=False)
    name         = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role         = db.Column(db.String(20), default='user')   # 'user' | 'coach'
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    sessions     = db.relationship('WorkSession', backref='user', lazy=True,
                                   order_by='WorkSession.created_at.desc()')

    def set_password(self, pw):   self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)


class WorkSession(db.Model):
    __tablename__ = 'work_sessions'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed    = db.Column(db.Boolean, default=False)
    current_step = db.Column(db.Integer, default=1)

    events      = db.relationship('Step1Event', backref='session', lazy=True,
                                  order_by='Step1Event.order_num', cascade='all, delete-orphan')
    loves       = db.relationship('Step2Love',  backref='session', lazy=True,
                                  order_by='Step2Love.love_num',  cascade='all, delete-orphan')
    analysis    = db.relationship('Step3Analysis', backref='session', uselist=False,
                                  cascade='all, delete-orphan')
    summary     = db.relationship('SessionSummary', backref='session', uselist=False,
                                  cascade='all, delete-orphan')
    coach_notes = db.relationship('CoachNote', backref='session', lazy=True,
                                  order_by='CoachNote.created_at.desc()', cascade='all, delete-orphan')


class Step1Event(db.Model):
    __tablename__ = 'step1_events'
    id           = db.Column(db.Integer, primary_key=True)
    session_id   = db.Column(db.Integer, db.ForeignKey('work_sessions.id'), nullable=False)
    order_num    = db.Column(db.Integer, default=0)
    time_period  = db.Column(db.String(100), default='')
    partner_name = db.Column(db.String(100), default='')
    community    = db.Column(db.String(200), default='')
    reason       = db.Column(db.Text, default='')


class Step2Love(db.Model):
    __tablename__ = 'step2_loves'
    id            = db.Column(db.Integer, primary_key=True)
    session_id    = db.Column(db.Integer, db.ForeignKey('work_sessions.id'), nullable=False)
    love_num      = db.Column(db.Integer, nullable=False)   # 1 / 2 / 3
    attraction    = db.Column(db.Text, default='')
    self_image    = db.Column(db.Text, default='')
    hardships     = db.Column(db.Text, default='')
    joys          = db.Column(db.Text, default='')
    breakup_reason = db.Column(db.Text, default='')
    learning      = db.Column(db.Text, default='')


class Step3Analysis(db.Model):
    __tablename__ = 'step3_analysis'
    id             = db.Column(db.Integer, primary_key=True)
    session_id     = db.Column(db.Integer, db.ForeignKey('work_sessions.id'), nullable=False)
    commonalities  = db.Column(db.Text, default='')
    struggles      = db.Column(db.Text, default='')
    behaviors      = db.Column(db.Text, default='')
    triggers       = db.Column(db.Text, default='')
    desires        = db.Column(db.Text, default='')


class SessionSummary(db.Model):
    __tablename__ = 'session_summaries'
    id            = db.Column(db.Integer, primary_key=True)
    session_id    = db.Column(db.Integer, db.ForeignKey('work_sessions.id'), nullable=False)
    good_patterns = db.Column(db.Text, default='')
    bad_patterns  = db.Column(db.Text, default='')
    action_theme  = db.Column(db.Text, default='')


class CoachNote(db.Model):
    __tablename__ = 'coach_notes'
    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('work_sessions.id'), nullable=False)
    coach_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    coach      = db.relationship('User', foreign_keys=[coach_id])


class UserProfile(db.Model):
    __tablename__ = 'user_profiles'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    ideal_partner  = db.Column(db.Text, default='')   # 理想のパートナー・関係像
    current_goal   = db.Column(db.Text, default='')   # 今の目標
    action_items   = db.Column(db.Text, default='')   # 次のアクションプラン
    notes          = db.Column(db.Text, default='')   # メモ帳
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@login_manager.user_loader
def load_user(uid): return User.query.get(int(uid))


def coach_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'coach':
            flash('コーチ専用ページです。', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('coach_dashboard') if current_user.role == 'coach' else url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pw    = request.form.get('password', '')
        user  = User.query.filter_by(email=email).first()
        if user and user.check_password(pw):
            login_user(user)
            return redirect(url_for('index'))
        flash('メールアドレスまたはパスワードが正しくありません。', 'error')
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name  = request.form.get('name', '').strip()
        pw    = request.form.get('password', '')
        role  = request.form.get('role', 'user')
        if not all([email, name, pw]):
            flash('すべての項目を入力してください。', 'error')
            return render_template('auth/register.html')
        if User.query.filter_by(email=email).first():
            flash('このメールアドレスはすでに登録されています。', 'error')
            return render_template('auth/register.html')
        user = User(email=email, name=name, role=role)
        user.set_password(pw)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('auth/register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ── User – session flow ───────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    sessions = WorkSession.query.filter_by(user_id=current_user.id)\
                                .order_by(WorkSession.created_at.desc()).all()
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()
    return render_template('session/dashboard.html', sessions=sessions, profile=profile)


@app.route('/dashboard/profile/save', methods=['POST'])
@login_required
def profile_save():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)
    data = request.get_json()
    profile.ideal_partner = data.get('ideal_partner', '')
    profile.current_goal  = data.get('current_goal', '')
    profile.action_items  = data.get('action_items', '')
    profile.notes         = data.get('notes', '')
    profile.updated_at    = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/session/new')
@login_required
def new_session():
    ws = WorkSession(user_id=current_user.id)
    db.session.add(ws)
    db.session.flush()
    for i in range(1, 4):
        db.session.add(Step2Love(session_id=ws.id, love_num=i))
    db.session.add(Step3Analysis(session_id=ws.id))
    db.session.add(SessionSummary(session_id=ws.id))
    db.session.commit()
    return redirect(url_for('step1', session_id=ws.id))


@app.route('/session/<int:session_id>/step1')
@login_required
def step1(session_id):
    ws = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    ws.current_step = max(ws.current_step, 1); db.session.commit()
    events_data = [{'time': e.time_period, 'name': e.partner_name,
                    'community': e.community, 'reason': e.reason} for e in ws.events]
    return render_template('session/step1.html', ws=ws, events_data=events_data)


@app.route('/session/<int:session_id>/step1/save', methods=['POST'])
@login_required
def step1_save(session_id):
    ws   = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    Step1Event.query.filter_by(session_id=ws.id).delete()
    for i, ev in enumerate(data.get('events', [])):
        db.session.add(Step1Event(session_id=ws.id, order_num=i,
            time_period=ev.get('time',''), partner_name=ev.get('name',''),
            community=ev.get('community',''), reason=ev.get('reason','')))
    ws.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/session/<int:session_id>/step2')
@login_required
def step2(session_id):
    ws = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    ws.current_step = max(ws.current_step, 2); db.session.commit()
    loves = {love.love_num: love for love in ws.loves}
    return render_template('session/step2.html', ws=ws, loves=loves)


@app.route('/session/<int:session_id>/step2/save', methods=['POST'])
@login_required
def step2_save(session_id):
    ws   = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    love = Step2Love.query.filter_by(session_id=ws.id, love_num=data.get('love_num')).first()
    if love:
        love.attraction     = data.get('attraction', '')
        love.self_image     = data.get('self_image', '')
        love.hardships      = data.get('hardships', '')
        love.joys           = data.get('joys', '')
        love.breakup_reason = data.get('breakup_reason', '')
        love.learning       = data.get('learning', '')
    ws.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/session/<int:session_id>/step3')
@login_required
def step3(session_id):
    ws = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    ws.current_step = max(ws.current_step, 3); db.session.commit()
    return render_template('session/step3.html', ws=ws)


@app.route('/session/<int:session_id>/step3/save', methods=['POST'])
@login_required
def step3_save(session_id):
    ws   = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    a    = ws.analysis
    if a:
        a.commonalities = data.get('commonalities', '')
        a.struggles     = data.get('struggles', '')
        a.behaviors     = data.get('behaviors', '')
        a.triggers      = data.get('triggers', '')
        a.desires       = data.get('desires', '')
    ws.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/session/<int:session_id>/summary')
@login_required
def session_summary(session_id):
    ws = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    ws.current_step = max(ws.current_step, 4); db.session.commit()
    return render_template('session/summary.html', ws=ws)


@app.route('/session/<int:session_id>/summary/save', methods=['POST'])
@login_required
def summary_save(session_id):
    ws   = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    s    = ws.summary
    if s:
        s.good_patterns = data.get('good', '')
        s.bad_patterns  = data.get('bad', '')
        s.action_theme  = data.get('action', '')
    ws.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/session/<int:session_id>/complete', methods=['POST'])
@login_required
def complete_session(session_id):
    ws = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    ws.completed = True
    ws.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('view_session', session_id=ws.id))


@app.route('/session/<int:session_id>/view')
@login_required
def view_session(session_id):
    ws    = WorkSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    loves = {love.love_num: love for love in ws.loves}
    return render_template('session/view.html', ws=ws, loves=loves)


# ── Coach ─────────────────────────────────────────────────────────────────────

@app.route('/coach')
@login_required
@coach_required
def coach_dashboard():
    users = User.query.filter_by(role='user').order_by(User.created_at.desc()).all()
    user_data = []
    for u in users:
        total     = WorkSession.query.filter_by(user_id=u.id).count()
        completed = WorkSession.query.filter_by(user_id=u.id, completed=True).count()
        latest    = WorkSession.query.filter_by(user_id=u.id)\
                               .order_by(WorkSession.updated_at.desc()).first()
        user_data.append({'user': u, 'total': total, 'completed': completed, 'latest': latest})
    return render_template('coach/dashboard.html', user_data=user_data)


@app.route('/coach/user/<int:user_id>')
@login_required
@coach_required
def coach_user(user_id):
    target = User.query.filter_by(id=user_id, role='user').first_or_404()
    sessions = WorkSession.query.filter_by(user_id=user_id)\
                                .order_by(WorkSession.created_at.desc()).all()
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    return render_template('coach/user.html', target=target, sessions=sessions, profile=profile)


@app.route('/coach/session/<int:session_id>')
@login_required
@coach_required
def coach_session(session_id):
    ws      = WorkSession.query.get_or_404(session_id)
    loves   = {love.love_num: love for love in ws.loves}
    profile = UserProfile.query.filter_by(user_id=ws.user_id).first()
    return render_template('coach/session.html', ws=ws, loves=loves, profile=profile)


@app.route('/coach/session/<int:session_id>/note', methods=['POST'])
@login_required
@coach_required
def coach_add_note(session_id):
    ws      = WorkSession.query.get_or_404(session_id)
    content = request.form.get('content', '').strip()
    if content:
        db.session.add(CoachNote(session_id=ws.id, coach_id=current_user.id, content=content))
        db.session.commit()
    return redirect(url_for('coach_session', session_id=session_id))


@app.route('/coach/session/<int:session_id>/note/<int:note_id>/delete', methods=['POST'])
@login_required
@coach_required
def coach_delete_note(session_id, note_id):
    note = CoachNote.query.filter_by(id=note_id, session_id=session_id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('coach_session', session_id=session_id))


# ── Init ──────────────────────────────────────────────────────────────────────

@app.template_filter('fmt_date')
def fmt_date(dt):
    if not dt: return '—'
    return dt.strftime('%Y年%-m月%-d日')


@app.template_filter('fmt_datetime')
def fmt_datetime(dt):
    if not dt: return '—'
    return dt.strftime('%Y年%-m月%-d日 %H:%M')


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
