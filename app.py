#!/usr/bin/env python3
"""xmotp.com - 厦门高端办公空间房源管理平台"""
import os, sqlite3, hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'xmotp-secret-' + os.urandom(12).hex())
DATABASE = os.path.join(os.path.dirname(__file__), 'xmotp.db')

# ── 数据库 ────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    g.pop('db', None)

def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT NOT NULL DEFAULT '',
            building_name TEXT NOT NULL DEFAULT '',
            area_m2 REAL DEFAULT 0,
            rent_per_day REAL DEFAULT 0,
            total_rent_month REAL DEFAULT 0,
            floor_info TEXT DEFAULT '',
            decoration TEXT DEFAULT '精装',
            property_fee REAL DEFAULT 0,
            parking TEXT DEFAULT '',
            lease_expiry TEXT DEFAULT '',
            source TEXT DEFAULT '',
            contact_name TEXT DEFAULT '',
            contact_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            status TEXT DEFAULT '在租',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # 默认管理员账号: admin / admin123
    pwd = hashlib.sha256('admin123'.encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
               ('admin', pwd, '管理员'))
    db.commit()
    db.close()

# ── 登录 ──────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*a, **kw):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*a, **kw)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE username=?", (request.form['username'],)).fetchone()
        if u and u['password_hash'] == hashlib.sha256(request.form['password'].encode()).hexdigest():
            session['user'] = {'id': u['id'], 'name': u['display_name'] or u['username']}
            return redirect(url_for('index'))
        return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── 房源管理 ──────────────────────────────────────────

@app.route('/')
@login_required
def index():
    db = get_db()
    # 筛选参数
    district = request.args.get('district', '').strip()
    status = request.args.get('status', '在租').strip()
    keyword = request.args.get('keyword', '').strip()
    area_min = request.args.get('area_min', '').strip()
    area_max = request.args.get('area_max', '').strip()
    rent_min = request.args.get('rent_min', '').strip()
    rent_max = request.args.get('rent_max', '').strip()
    page = max(1, int(request.args.get('page', '1') or '1'))

    conditions = []
    params = []

    if status != '全部':
        conditions.append("status = ?")
        params.append(status)

    if district:
        conditions.append("district = ?")
        params.append(district)

    if keyword:
        conditions.append("(building_name LIKE ? OR contact_name LIKE ? OR contact_phone LIKE ?)")
        kw = f'%{keyword}%'
        params.extend([kw, kw, kw])

    if area_min:
        conditions.append("area_m2 >= ?")
        params.append(float(area_min))
    if area_max:
        conditions.append("area_m2 <= ?")
        params.append(float(area_max))

    if rent_min:
        conditions.append("rent_per_day >= ?")
        params.append(float(rent_min))
    if rent_max:
        conditions.append("rent_per_day <= ?")
        params.append(float(rent_max))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    per_page = 20
    offset = (page - 1) * per_page

    total = db.execute(f"SELECT COUNT(*) FROM listings {where}", params).fetchone()[0]
    listings = db.execute(
        f"SELECT * FROM listings {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)

    # 获取所有区域和状态用于筛选
    districts = [r['district'] for r in db.execute("SELECT DISTINCT district FROM listings WHERE district != '' ORDER BY district").fetchall()]

    stats = dict(db.execute(
        "SELECT status, COUNT(*) FROM listings GROUP BY status"
    ).fetchall())

    return render_template('index.html',
        listings=listings, districts=districts,
        stats=stats, page=page, total_pages=total_pages, total=total,
        cur_district=district, cur_status=status, cur_keyword=keyword,
        cur_area_min=area_min, cur_area_max=area_max,
        cur_rent_min=rent_min, cur_rent_max=rent_max,
    )

@app.route('/listing/new', methods=['GET', 'POST'])
@login_required
def listing_new():
    if request.method == 'POST':
        db = get_db()
        db.execute("""
            INSERT INTO listings (district, building_name, area_m2, rent_per_day, total_rent_month,
                floor_info, decoration, property_fee, parking, lease_expiry,
                source, contact_name, contact_phone, notes, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form.get('district', ''),
            request.form.get('building_name', ''),
            float(request.form.get('area_m2', 0) or 0),
            float(request.form.get('rent_per_day', 0) or 0),
            float(request.form.get('total_rent_month', 0) or 0),
            request.form.get('floor_info', ''),
            request.form.get('decoration', '精装'),
            float(request.form.get('property_fee', 0) or 0),
            request.form.get('parking', ''),
            request.form.get('lease_expiry', ''),
            request.form.get('source', ''),
            request.form.get('contact_name', ''),
            request.form.get('contact_phone', ''),
            request.form.get('notes', ''),
            '在租'
        ))
        db.commit()
        return redirect(url_for('index'))
    return render_template('form.html', listing=None)

@app.route('/listing/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def listing_edit(id):
    db = get_db()
    listing = db.execute("SELECT * FROM listings WHERE id=?", (id,)).fetchone()
    if not listing:
        return "房源不存在", 404
    if request.method == 'POST':
        db.execute("""
            UPDATE listings SET district=?, building_name=?, area_m2=?, rent_per_day=?,
                total_rent_month=?, floor_info=?, decoration=?, property_fee=?, parking=?,
                lease_expiry=?, source=?, contact_name=?, contact_phone=?, notes=?,
                status=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            request.form.get('district', ''),
            request.form.get('building_name', ''),
            float(request.form.get('area_m2', 0) or 0),
            float(request.form.get('rent_per_day', 0) or 0),
            float(request.form.get('total_rent_month', 0) or 0),
            request.form.get('floor_info', ''),
            request.form.get('decoration', '精装'),
            float(request.form.get('property_fee', 0) or 0),
            request.form.get('parking', ''),
            request.form.get('lease_expiry', ''),
            request.form.get('source', ''),
            request.form.get('contact_name', ''),
            request.form.get('contact_phone', ''),
            request.form.get('notes', ''),
            request.form.get('status', '在租'),
            id
        ))
        db.commit()
        return redirect(url_for('index'))
    return render_template('form.html', listing=listing)

@app.route('/listing/<int:id>/delete', methods=['POST'])
@login_required
def listing_delete(id):
    db = get_db()
    db.execute("UPDATE listings SET status='已下架', updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    return redirect(url_for('index'))

@app.route('/listing/<int:id>/detail')
@login_required
def listing_detail(id):
    db = get_db()
    listing = db.execute("SELECT * FROM listings WHERE id=?", (id,)).fetchone()
    if not listing:
        return "房源不存在", 404
    return render_template('detail.html', listing=listing)

@app.route('/export')
@login_required
def export():
    db = get_db()
    rows = db.execute("SELECT * FROM listings WHERE status='在租' ORDER BY district, building_name").fetchall()
    import csv, io
    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(['区域', '楼盘名', '面积(㎡)', '日租金(元/㎡)', '月租金', '楼层', '装修', '物业费', '停车位', '合同到期', '来源', '联系人', '电话', '备注'])
    for r in rows:
        w.writerow([r['district'], r['building_name'], r['area_m2'], r['rent_per_day'],
                    r['total_rent_month'], r['floor_info'], r['decoration'], r['property_fee'],
                    r['parking'], r['lease_expiry'], r['source'], r['contact_name'],
                    r['contact_phone'], r['notes']])
    output = si.getvalue().encode('utf-8-sig')
    return app.response_class(output, mimetype='text/csv',
                              headers={'Content-Disposition': 'attachment; filename=房源导出.csv'})

# ── 启动 ──────────────────────────────────────────────

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
        print("数据库已初始化")
    app.run(host='0.0.0.0', port=5100, debug=False)
