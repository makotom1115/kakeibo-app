from flask_sqlalchemy import SQLAlchemy
from datetime import date



# =============================================
# データベースのインスタンス生成
# =============================================
db = SQLAlchemy()

# =============================================
# モデル
# =============================================
class HouseholdBudget(db.Model):
    # テーブル名
    __tablename__ = 'household_budget'
    # アカウントID
    account_id = db.Column(
        db.Integer,
        db.ForeignKey("accounts.id"),
        nullable=False
        )
    # id
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
        )
    # ユーザーID
    user_id = db.Column(
        db.Integer, 
        db.ForeignKey('users.id'), # 外部キー
        nullable=False
        ) 

    # 費目ID
    category_id = db.Column(
        db.Integer,
        db.ForeignKey('categories.id'), # 外部キー
        nullable=False
        )

    # 家計簿入力日
    input_date = db.Column(
        db.Date,
        default=date.today
        )
    
    # レシートの会計日
    posting_date = db.Column(
        db.Date,
        nullable=False
        )
    
    # 収入額
    income = db.Column(
        db.Integer
        )
    
    # 支出額
    expense = db.Column(
        db.Integer
        )
    
    # 備考（主に企業名）
    memo = db.Column(
        db.Text
        )

class Account(db.Model):
    __tablename__ = 'accounts'
    # アカウントID
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )
    # e-mailアドレス
    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False
    )
    # e-mailアドレス確認用
    password_hash = db.Column(
        db.String(255),
        nullable=False
    )
    # Usersとのリレーション用
    users = db.relationship(
        "Users",
        backref="accounts",
        lazy=True
    )
    # Categoriesとのリレーション用
    categories = db.relationship(
        "Categories",
        backref="accounts",
        lazy=True
    )


class Users(db.Model):
    # テーブル名
    __tablename__ = 'users'
    # ユーザーID
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
        )
    # アカウントID
    account_id = db.Column(
        db.Integer,
        db.ForeignKey("accounts.id"),
        nullable=False
    )
    # ユーザー名
    name = db.Column(
        db.String(10),
        nullable=False
        )
    household_budgets = db.relationship(
        'HouseholdBudget',
        backref='user',
        lazy=True
    )
    def __repr__(self):
        return f'<Users {self.name}>'

class Categories(db.Model):
    # テーブル名
    __tablename__ = 'categories'
    # 費目ID
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
        )
    # アカウントID
    account_id = db.Column(
        db.Integer,
        db.ForeignKey("accounts.id"),
        nullable=False
        )
    # 費目名
    name = db.Column(
        db.String(10),
        nullable=False
        )
    # 収入/支出選択
    transaction_type = db.Column(
        db.String(10),
        nullable=False
        )
    household_budgets = db.relationship(
        'HouseholdBudget',
        backref='categories',
        lazy=True
    )
