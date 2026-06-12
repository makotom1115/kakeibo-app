# ==============================
# 標準ライブラリ
# ==============================
import csv
import json
import os
import re
from datetime import date, datetime
from io import BytesIO, StringIO
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


# ==============================
# Flask
# ==============================
from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
    send_file,
    send_from_directory
)

# ==============================
# DB
# ==============================
from models import (
    db,
    Account,
    Categories,
    HouseholdBudget,
    Users
)

# ==============================
# Forms
# ==============================
from forms import (
    ManualForm,
    OCRForm,
    RegisterForm
)

# ==============================
# OCR
# ==============================
from gemini_ocr import (
    CATEGORY_MAP,
    analyze_receipt
)

# ==============================
# Flask-WTF
# ==============================
from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)
from werkzeug.utils import (
    secure_filename,
    safe_join
)

# ==============================
# PDF
# ==============================
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle
)

# ==============================
# 環境変数
# ==============================
from dotenv import load_dotenv

# ==============================
# アプリのインスタンス生成
# ==============================
app = Flask(__name__)

# ==============================
# シークレットキー設定
# ==============================
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# =======================================
# DBファイルの設定（web：Postgres、local：SQlite）
# ========================================
database_url = os.environ.get("DATABASE_URL")

if database_url:
    database_url = database_url.replace(
        "postgres://",
        "postgresql",
        1
    )

basedir = os.path.abspath(os.path.dirname(__file__))

sqlite_path = "sqlite:///" + os.path.join(basedir, "kakeibo.sqlite")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url if database_url else sqlite_path

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# =============================
# アプリ実行
# =============================
# ★db変数を使用してSQLAlchemyを操作できる
db.init_app(app)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ===============================================
# ルーティング
# ===============================================

UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ログイン画面
@app.route('/', methods=['GET', 'POST'])
def app_login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        # メールアドレス検索
        account = Account.query.filter_by(
            email=email
        ).first()

        # アカウント存在 + パスワード一致
        if account and check_password_hash(
            account.password_hash,
            password
        ):

            session['login'] = True
            session['account_id'] = account.id

            print("CWD:", os.getcwd())
            print("DB PATH:", os.path.abspath("kakeibo.sqlite"))

            return redirect(url_for('top'))

        flash('メールアドレスまたはパスワードが違います')

    return render_template('content/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():

    form = RegisterForm()

    if form.validate_on_submit():

        # メール重複チェック
        account = Account.query.filter_by(
            email=form.email.data
        ).first()

        if account:
            flash("そのメールアドレスは既に登録されています")
            return render_template(
                'content/register.html',
                form=form
            )

        password_hash = generate_password_hash(
            form.password.data
        )

        account = Account(
            email=form.email.data,
            password_hash=password_hash
        )

        db.session.add(account)
        db.session.commit()

        seed_categories(account.id)

        return redirect(url_for('app_login'))

    return render_template(
        'content/register.html',
        form=form
    )

def seed_categories(account_id):

    defaults = [
        {"name": "食費", "transaction_type": "expense"},
        {"name": "日用品", "transaction_type": "expense"},
        {"name": "交通費", "transaction_type": "expense"},
        {"name": "医療費", "transaction_type": "expense"},
        {"name": "娯楽費", "transaction_type": "expense"},
        {"name": "通信費", "transaction_type": "expense"},
        {"name": "水道光熱費", "transaction_type": "expense"},
        {"name": "雑費", "transaction_type": "expense"},
        {"name": "給与", "transaction_type": "income"},
    ]

    for item in defaults:
        exists = Categories.query.filter_by(
            account_id=account_id,
            name=item["name"],
            transaction_type=item["transaction_type"]
        ).first()

        if not exists:
            db.session.add(Categories(
                account_id=account_id,
                name=item["name"],
                transaction_type=item["transaction_type"]
            ))

    db.session.commit()

# ==================================================

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # セキュリティ対策（パストラバーサル防止）
    safe_path = safe_join(UPLOAD_FOLDER, filename)

    if not os.path.exists(safe_path):
        return "Not found", 404

    return send_from_directory(UPLOAD_FOLDER, filename)

def convert_to_jpeg(src_path):
    img = Image.open(src_path)

    # EXIFの回転情報を反映
    img = ImageOps.exif_transpose(img)

    if img.mode != "RGB":
        img = img.convert("RGB")

    new_path = src_path + ".jpg"

    img.save(new_path, "JPEG")

    print(img.size)
    print(img.getexif())

    return new_path


@app.route('/ocr_image')
def ocr_image():

    image_path = session.get("ocr_image_filename")

    if not image_path or not os.path.exists(image_path):
        return "Image not found", 404

    return send_file(image_path)

# TOP画面
@app.route('/top', methods=['GET', 'POST'])
def top():
    if not session.get('login'):
        return redirect(url_for('app_login'))
    return render_template('content/top.html')

# TOP画面　→　ログアウト処理
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('app_login'))

# TOP画面　→　Input画面
@app.route('/input/page', methods=['GET', 'POST'])
def input_page():

    if not session.get('login'):
        return redirect(url_for('app_login'))

    mode = request.form.get("mode", "manual")

    manual_form = ManualForm()
    ocr_form = OCRForm()

    register_heif_opener()

    category_id = None
    income = 0
    expense = 0
    ocr_result = {}

    # =====================
    # 共通データ
    # =====================
    users = Users.query.filter_by(
        account_id=session["account_id"]
    ).all()

    categories = Categories.query.filter_by(
        account_id=session["account_id"]
    ).all()

    today = date.today().isoformat()

    recent_budgets = (
        db.session.query(HouseholdBudget)
        .filter_by(account_id=session["account_id"])
        .order_by(HouseholdBudget.id.desc())
        .limit(5)
        .all()
    )

    balance = (
        (db.session.query(db.func.sum(HouseholdBudget.income))
         .filter_by(account_id=session["account_id"])
         .scalar() or 0)
        -
        (db.session.query(db.func.sum(HouseholdBudget.expense))
         .filter_by(account_id=session["account_id"])
         .scalar() or 0)
    )

    ocr_result = None

    # =====================
    # OCRモード
    # =====================
    if request.method == "POST" and mode == "ocr":

        if not ocr_form.validate_on_submit():
            return render_template(
                "content/input_page.html",
                manual_form=manual_form,
                ocr_form=ocr_form,
                users=users,
                categories=categories,
                balance=balance,
                recent_budgets=recent_budgets,
                message="画像を選択してください"
            )

        image_file = ocr_form.receipt_image.data

        upload_dir = os.path.join(app.root_path, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        filename = secure_filename(image_file.filename)
        path = os.path.join(upload_dir, filename)

        image_file.save(path)
        path = convert_to_jpeg(path)

        processed_filename = os.path.basename(path)
        session["ocr_image_filename"] = processed_filename

        raw = analyze_receipt(path)

        cleaned = raw.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            ocr_result = json.loads(cleaned)
        except:
            return "OCR解析失敗", 500

        if ocr_result["transaction_type"] == "expense":
            income = 0
            expense = ocr_result["amount"]
        else:
            income = ocr_result["amount"]
            expense = 0

        # 費目処理
        def normalize_category(category):
            if not category:
                return "雑費"                          # OCR失敗やNoneのとき
            return CATEGORY_MAP.get(category, "雑費")  # マッピングになければ雑費

        raw_category = ocr_result.get("category")      # OCR結果取得
        category_name = normalize_category(raw_category)

        category = Categories.query.filter_by(
            account_id=session["account_id"],
            name=category_name
        ).first()

        if not category:
            # 「雑費」を取得
            category = Categories.query.filter_by(
                account_id=session["account_id"],
                name="雑費"
            ).first()

        if category:
            category_id = category.id
            category_name = category.name
        else:
            category_id = None   # 念のため

        session["draft"] = {
            "user_id": request.form.get("user_id"),
            "category_id": category_id,
            "income": income,
            "expense": expense,
            "memo": ocr_result.get("memo") or ocr_result.get("store", ""),
            "posting_date": ocr_result.get("date")
        }
        
        return redirect(url_for("input_page_preview"))

    # =====================
    # 手入力モード
    # =====================
    if request.method == "POST" and mode == "manual":

        category_id = request.form.get("category_id")

        if not manual_form.validate():
            return render_template(
                "content/input_page.html",
                manual_form=manual_form,
                ocr_form=ocr_form,
                users=users,
                categories=categories,
                balance=balance,
                recent_budgets=recent_budgets,
                message="入力エラーがあります"
            )

        session["draft"] = {
            "income": manual_form.income.data or 0,
            "expense": manual_form.expense.data or 0,
            "memo": manual_form.memo.data or "",
            "posting_date": manual_form.posting_date.data.isoformat()
        }

        return redirect(url_for("input_page_preview"))

    # =====================
    # GET
    # =====================
    return render_template(
        "content/input_page.html",
        manual_form=manual_form,
        ocr_form=ocr_form,
        users=users,
        categories=categories,
        balance=balance,
        recent_budgets=recent_budgets,
        today=today
    )



# プレビュー表示
@app.route('/input/preview')
def input_page_preview():
    data = session.get("draft")

    image_filename = session.get("ocr_image_filename")

    if not data:
        return redirect(url_for("input_page"))
    
    users = Users.query.filter_by(
        account_id=session["account_id"]
    ).all()

    categories = Categories.query.filter_by(
        account_id=session["account_id"]
    ).all()

    return render_template(
        "content/input_preview.html", 
        data=data, 
        users=users, 
        categories=categories,
        image_filename=image_filename
    )

# 保存
@app.route('/input/save', methods=['POST'])
def save():

    filename = session.get("ocr_image_filename")

    if filename:
        full_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(full_path):
            os.remove(full_path)

    posting_date_str = request.form.get("posting_date")
    posting_date = datetime.strptime(posting_date_str, "%Y-%m-%d").date()

    new_data = HouseholdBudget(
        account_id=session["account_id"],
        user_id=request.form.get("user_id"),
        category_id=request.form.get("category_id"),
        income=request.form.get("income"),
        expense=request.form.get("expense"),
        memo=request.form.get("memo"),
        posting_date=posting_date,
        input_date=date.today()
    )

    db.session.add(new_data)
    db.session.commit()

    session.pop("draft", None)
    session.pop("ocr_temp", None)
    session.pop("ocr_image_filename", None)

    return redirect(url_for("input_page"))

# 登録内容の全件表示
@app.route('/input/all/content')
def input_all_content():
    if not session.get('login'):
        return redirect(url_for('app_login'))
    
    householdbudgets = HouseholdBudget.query.filter_by(
        account_id=session["account_id"]
    ).order_by(
        HouseholdBudget.id.desc()
    ).all()
    return render_template('content/input_all_content.html', householdbudgets=householdbudgets)

# 入力内容の編集
@app.route('/input/edit/<id>', methods=['GET', 'POST'])
def input_edit(id):

    if not session.get('login'):
        return redirect(url_for('app_login'))
    
    householdbudget = HouseholdBudget.query.filter_by(
        id=id,
        account_id=session["account_id"]
    ).first_or_404()
    
    users = Users.query.filter_by(
        account_id=session["account_id"]
    ).all()

    categories = Categories.query.filter_by(
        account_id=session["account_id"]
    ).all()

    if request.method == 'POST':

        user_id = request.form.get('user_id')
        category_id = request.form.get('category_id')

        householdbudget.user_id = request.form.get('user_id')
        householdbudget.category_id = request.form.get('category_id')
        householdbudget.posting_date = datetime.strptime(
            request.form.get('posting_date'),
            '%Y-%m-%d'
        ).date()

        householdbudget.income = int(
            request.form.get('income') or 0
        )
        
        householdbudget.expense = int(
            request.form.get('expense') or 0
        )
        
        householdbudget.memo = request.form.get('memo')

        db.session.commit()

        return redirect(url_for('input_all_content'))


    
    return render_template(
        'content/input_edit.html', 
        householdbudget=householdbudget, 
        users=users, 
        categories=categories
    )

# editでの行単位削除処理
@app.route('/input/delete/<int:id>', methods=['POST'])
def input_delete(id):

    if not session.get('login'):
        return redirect(url_for('app_login'))

    householdbudget = HouseholdBudget.query.filter_by(
        id=id,
        account_id=session["account_id"]
    ).first_or_404()

    db.session.delete(householdbudget)
    db.session.commit()

    return redirect(url_for('input_all_content'))

# TOP画面　→　serch_TOP画面
@app.route('/search/top', methods=['GET', 'POST'])
def search_top():
    if not session.get('login'):
        return redirect(url_for('app_login'))
    return render_template('content/search_top.html')

#　TOP画面　→　マスタTOP画面
@app.route('/master', methods=['GET', 'POST'])
def master_top():
    if not session.get('login'):
        return redirect(url_for('app_login')) 
    return render_template('admin/master_top.html')

# =================================================

# search_top画面 →　簡易検索画面
@app.route('/search/simple', methods=['GET', 'POST'])
def search_simple():
    if not session.get('login'):
        return redirect(url_for('app_login'))
    
    start_date = date.today().replace(day=1).isoformat()
    end_date = date.today().isoformat()
    
    return render_template('content/search_simple.html', start_date=start_date, end_date=end_date)
    
# search_top画面　→　詳細検索画面
@app.route('/search/advanced', methods=['GET', 'POST'])
def search_advanced():
    if not session.get('login'):
        return redirect(url_for('app_login')) 
    
    start_date = date.today().replace(day=1).isoformat()
    end_date = date.today().isoformat()

    categories = Categories.query.all()

    return render_template('content/search_advanced.html', start_date=start_date, end_date=end_date, categories=categories)

# 簡易検索画面・詳細検索画面　→　ファイル出力画面
@app.route('/export', methods=['GET','POST'])
def export():
    if not session.get('login'):
        return redirect(url_for('app_login'))

    # 会計日検索の情報取得
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    # 簡易or詳細モードの情報取得
    search_mode = request.form.get('search_mode')

    # 収支検索の情報取得
    transaction_type = request.form.get('transaction_type')

    # 費目検索の情報取得
    category_id = request.form.get('category_id')

    # memo検索の情報取得
    memo  = request.form.get('memo')

    return render_template(
        'content/export.html',
        start_date=start_date,
        end_date=end_date,
        search_mode=search_mode,
        transaction_type=transaction_type,
        category_id=category_id,
        memo=memo
        )

# CSV出力
@app.route('/csv/download', methods=['POST'])
def csv_download():
    if not session.get('login'):
        return redirect(url_for('app_login'))

    # HouseholdBudget と Account を 内部結合してqueryに保存
    query = HouseholdBudget.query.join(Categories)

    # posting_dateの昇順で並べ替え
    query = query.order_by(HouseholdBudget.posting_date.asc())

    # account_id情報にフィルターをかけ、他のアカウントの情報が表示されないようにする
    query = query.filter(
        HouseholdBudget.account_id == session["account_id"]
        )

    # 'start_date'フォームに入力されたを保存（form type=date でも受け取りは文字列）
    start_date = request.form.get('start_date')
    # 'end_date'フォームに入力されたを保存（form type=date でも受け取りは文字列）
    end_date = request.form.get('end_date')

    # 取得したデータをdate型に変換
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # 収支情報の取得
    transaction_type = (request.form.get("transaction_type") or "").strip()
    # 取引種別が空、もしくは変な値じゃないか確認
    if transaction_type:
        query = query.filter(Categories.transaction_type == transaction_type)

    # 費目ID取得
    category_id = (request.form.get("category_id") or "").strip()
    # category_idが空、もしくは変な文字列じゃないか確認
    if category_id:
        query = query.filter(HouseholdBudget.category_id == category_id)

    # メモの取得
    memo = (request.form.get('memo') or "").strip()
    # memoが空、もしくは変な文字列じゃないか確認
    if memo:
        query = query.filter(HouseholdBudget.memo.like(f"%{memo}%"))

    # 日付（共通項目）
    query = query.filter(
    HouseholdBudget.posting_date >= start_date,
    HouseholdBudget.posting_date <= end_date
    )
    
    rows = query.all()
    
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "posting_date",
        "input_date",
        "user_name",
        "category_name",
        "income", 
        "expense", 
        "memo"
        ])

    for r in rows:
        writer.writerow([
            r.posting_date,
            r.input_date,
            r.user.name,
            r.categories.name,
            r.income,
            r.expense,
            r.memo
            ])
    output.seek(0)

    return Response(
        output.getvalue().encode('utf-8-sig'), 
        mimetype="text/csv", 
        headers={"Content-Disposition": "attachment; filename=export.csv"})

# pdf出力
@app.route('/pdf/download', methods=['POST'])
def pdf_download():
    if not session.get('login'):
        return redirect(url_for('app_login'))

    query = (
    HouseholdBudget.query
    .join(Account, HouseholdBudget.account_id == Account.id)
    .join(Categories, HouseholdBudget.category_id == Categories.id)
    .join(Users, HouseholdBudget.user_id == Users.id)
)
    
    query = query.order_by(HouseholdBudget.posting_date.asc())

    query = query.filter(
        HouseholdBudget.account_id == session["account_id"]
        )

    # 日付取得
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # 各条件取得
    transaction_type = request.form.get('transaction_type')
    if transaction_type in [None, "", "None"]:
        transaction_type = ""

    category_id = request.form.get('category_id')
    if category_id in [None, "", "None"]:
        category_id = ""

    memo = request.form.get('memo')
    if memo in [None, "", "None"]:
        memo = ""
    else:
        memo = memo.strip()

    # 日付検索
    query = query.filter(
        HouseholdBudget.posting_date >= start_date,
        HouseholdBudget.posting_date <= end_date
    )

    # 取引種別
    if transaction_type:
        query = query.filter(
            Categories.transaction_type == transaction_type
        )

    # 費目
    if category_id:
        query = query.filter(
            HouseholdBudget.category_id == category_id
        )

    # メモ
    if memo:
        query = query.filter(
            HouseholdBudget.memo.like(f"%{memo}%")
        )

    rows = query.all()

    buffer = BytesIO()

    pdf = SimpleDocTemplate(buffer)

    data = []

    # ヘッダー
    data.append([
        "会計日",
        "入力日",
        "ユーザー名",
        "費目名",
        "収入",
        "支出",
        "メモ"
    ])

    # データ
    for r in rows:

        data.append([
            r.posting_date,
            r.input_date,
            r.user.name,
            r.categories.name,
            f"{r.income:,}",
            f"{r.expense:,}",
            r.memo
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        
        # フォントを指定
        ('FONTNAME', (0,0), (-1,-1), 'HeiseiKakuGo-W5'),

        # ヘッダー背景
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),

        # 枠線
        ('GRID', (0,0), (-1,-1), 1, colors.black),

        # 文字中央
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),

        # 余白
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
    ]))

    pdf.build([table])

    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="report.pdf", mimetype="application/pdf")

# =====================================================

# マスタTOP画面　→　マスタ費目追加
@app.route('/master/category', methods=['GET', 'POST'])
def master_category():
    if not session.get('login'):
        return redirect(url_for('app_login')) 
    
    if request.method == 'POST':

        category_name = request.form['category_name']
        transaction_type = request.form['transaction_type']

        new_category = Categories(
            account_id=session["account_id"],
            name=category_name, 
            transaction_type=transaction_type
            )
        db.session.add(new_category)
        db.session.commit()
        return redirect(url_for('master_top'))

    return render_template('admin/master_category.html')

# 登録した費目の表示
@app.route('/master/category/preview')
def master_category_preview():
    if not session.get('login'):
        return redirect(url_for('app_login'))   

    categories = Categories.query.filter_by(
        account_id=session["account_id"]
        ).all()

    return render_template('admin/master_category_preview.html', Categories=categories)

# 費目編集画面
@app.route('/master/category/edit/<int:id>', methods=['GET', 'POST'])
def master_category_edit(id):
    if not session.get('login'):
        return redirect(url_for('app_login'))   
    
    category = Categories.query.filter_by(
        id=id,
        account_id=session["account_id"]
    ).first_or_404()

    if request.method == 'POST':

        category.name = request.form.get('name')
        category.transaction_type = request.form.get('transaction_type')

        db.session.commit()

        return redirect(url_for('master_category_preview'))

    return render_template('admin/master_category_edit.html', category=category) 

# マスタTOP画面　→　マスタユーザー追加
@app.route('/master/user', methods=['GET', 'POST'])
def master_user():
    if not session.get('login'):
        return redirect(url_for('app_login')) 
    
    if request.method == 'POST':

        user_name = request.form['user_name']

        new_user = Users(
            account_id=session["account_id"],
            name=user_name
            )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('master_top'))
    
    return render_template('admin/master_user.html')

# 登録しているユーザーの表示画面
@app.route('/master/user/preview/', methods=['GET', 'POST'])
def master_user_preview():
    if not session.get('login'):
        return redirect(url_for('app_login')) 
    
    User = Users.query.filter_by(
        account_id=session["account_id"]
        ).all()

    return render_template('admin/master_user_preview.html', User=User)

# ユーザー編集画面
@app.route('/master/user/edit/<id>', methods=['GET', 'POST'])
def master_user_edit(id):
    if not session.get('login'):
        return redirect(url_for('app_login')) 
    
    User = Users.query.filter_by(
        id=id,
        account_id=session["account_id"]
    ).first_or_404()

    if request.method == 'POST': 

        User.name = request.form.get('name')

        db.session.commit()

        return redirect(url_for('master_user_preview'))

    return render_template('admin/master_user_edit.html', User=User) 
