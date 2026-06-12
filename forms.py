from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import (
    FileField,
    FileAllowed,
    FileRequired
)

from wtforms.fields import (
    StringField,
    IntegerField,
    DateField,
    TextAreaField,
    PasswordField,
    SubmitField
)

from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    Optional,
    ValidationError
)

from models import Account

# ============================================

class RegisterForm(FlaskForm):

    email = StringField(
        'メールアドレス',
        validators=[
            DataRequired(),
            Email(),
            Length(max=255)
        ]
    )

    password = PasswordField(
        'パスワード',
        validators=[
            DataRequired(),
            Length(
                min=8,
                max=20,
                message='パスワードは8～20文字で入力してください'
            )
        ]
    )

    password_confirm = PasswordField(
        'パスワード確認',
        validators=[
            DataRequired(),
            EqualTo(
                'password',
                message='パスワードが一致しません'
            )
        ]
    )

    submit = SubmitField('登録')

    def validate_email(self, field):

        account = Account.query.filter_by(
            email=field.data
        ).first()

        if account:
            raise ValidationError(
                'このメールアドレスは既に登録されています'
            )

# =====================
# 手入力用フォーム
# =====================
class ManualForm(FlaskForm):

    posting_date = DateField(
        '会計日',
        format='%Y-%m-%d',
        validators=[DataRequired()]
    )
    input_date = DateField(default=date.today)
    income = IntegerField(validators=[Optional()])
    expense = IntegerField(validators=[Optional()])

    memo = TextAreaField(validators=[Optional()])


# =====================
# OCR用フォーム
# =====================
class OCRForm(FlaskForm):

    receipt_image = FileField(
        'レシート画像',
        validators=[
            FileRequired(message="画像を選択してください"),
            FileAllowed(['jpg', 'jpeg', 'png', 'pdf', 'heic'], '画像のみ対応')
        ]
    )


# =====================
# 共通送信ボタン
# =====================
class SubmitForm(FlaskForm):
    submit = SubmitField('登録')

    
