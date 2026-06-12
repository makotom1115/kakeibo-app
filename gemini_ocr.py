import os
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image


# .env読み込み
load_dotenv()

# APIキー設定
genai.configure(
    api_key=os.environ.get("GEMINI_API_KEY")
)

# モデル生成
model = genai.GenerativeModel('gemini-2.5-flash')


def analyze_receipt(image_path):

    image = Image.open(image_path)

    prompt = """
    このレシート画像から以下を抽出してください。

    【出力項目】
    ・date（YYYY-MM-DD）
    ・store（店舗名）
    ・amount（数値のみ、円やカンマは禁止）
    ・transaction_type（income / expense）
    ・category（費目）
    ・memo（備考があれば）

    transaction_type は以下のルールで判定してください。

        expense:
        - 店舗レシート
        - 領収書
        - クレジットカード利用明細
        - 商品購入
        - 飲食代
        - 交通費
        - 光熱費

        income:
        - 給与明細
        - 賞与明細
        - 売上伝票
        - 入金通知
        - 振込入金
        - 還付金

    ルール：
    - 通常のレシートは expense
    - 返金・払い戻し・入金の場合のみ income
    - 不明な場合は expense
    - ```やjsonという文字は含めない。
    - 余計な余白は入れない。

    JSON形式で返してください。
    """

    response = model.generate_content([prompt, image])

    return response.text

# マッピング処理のデータ
CATEGORY_MAP = {
    "食費": "食費",
    "食事代": "食費",
    "飲食費": "食費",
    "飲食代": "食費",
    "コンビニ": "食費",
    "スーパー": "食費",
    "外食費": "食費",
    "外食費": "食費",
    "雑費": "雑費",
    "水道光熱費": "水道光熱費",
    "給与所得": "給与",
    "交通費": "交通費",
    "娯楽費": "娯楽費",
    "遊興費": "娯楽費",
    "日用品": "日用品",
    "医療費": "医療費",
    "薬代": "医療費",
    "病院代": "医療費"
    }