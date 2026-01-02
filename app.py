import streamlit as st
import google.generativeai as genai
import hmac # パスワードを安全に比較するための道具
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
import datetime

# --- 0. ログイン機能の関数 ---
def check_password():
    """IDとパスワードによるログイン認証"""
    
    # すでにログイン済みならOKを返す
    if st.session_state.get('password_correct', False):
        return True

    # --- ログイン画面の表示 ---
    st.title("🔒 先生用ログイン")
    st.caption("管理者から配布されたIDとパスワードを入力してください。")
    
    # フォームを使ってEnterキーでログインできるようにする
    with st.form("login_form"):
        user_id = st.text_input("ユーザーID")
        password = st.text_input("パスワード", type="password")
        submit_button = st.form_submit_button("ログイン")

        if submit_button:
            # Secretsに「passwords」という設定があるか確認
            if "passwords" not in st.secrets:
                st.error("設定エラー: Secretsにユーザー情報が登録されていません。")
                return False
            
            # IDが存在し、かつパスワードが一致するか確認
            if user_id in st.secrets["passwords"] and \
               hmac.compare_digest(password, st.secrets["passwords"][user_id]):
                
                st.session_state['password_correct'] = True
                st.session_state['user_id'] = user_id # 誰が入ったか記録
                st.rerun() # 画面を再読み込みしてアプリへ
                
            else:
                st.error("IDまたはパスワードが間違っています。")

    return False

# --- メイン処理の前にロックをかける ---
if not check_password():
    st.stop() # ログインしていない場合はここでプログラムを強制停止！

# ========================================================
# 🔓 ここから下は、ログイン成功者だけが見られる世界
# ========================================================

# --- APIキーの取得（Secretsから安全に取得） ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("APIキーが設定されていません。Streamlit CloudのSecretsを設定してください。")
    st.stop()

# --- 初期設定 ---
if len(API_KEY) < 30:
    st.error("APIキーが無効です。")
else:
    genai.configure(api_key=API_KEY)

# --- セッションステート初期化 ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_data' not in st.session_state:
    st.session_state.current_data = None

# --- サイドバー：ログアウト機能とユーザー表示 ---
st.sidebar.success(f"ログイン中: {st.session_state['user_id']} 先生")
if st.sidebar.button("ログアウト"):
    st.session_state['password_correct'] = False
    st.session_state['user_id'] = None
    st.rerun()
st.sidebar.divider()

# --- (以下、いつものアプリ機能) ---

# --- 1. PDFを作る関数 ---
def create_pdf(problem_text):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    
    font_path = "ipaexg.ttf" 
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('IPAexGothic', font_path))
            p.setFont('IPAexGothic', 11)
        except:
            p.setFont("Helvetica", 11)
    else:
        p.setFont("Helvetica", 11)
    
    y = 800 
    line_height = 15 
    
    for line in problem_text.split('\n'):
        if y < 50:
            p.showPage()
            if os.path.exists(font_path):
                p.setFont('IPAexGothic', 11)
            else:
                p.setFont("Helvetica", 11)
            y = 800
        
        try:
            p.drawString(50, y, line)
        except:
            pass
        y -= line_height
        
    p.save()
    buffer.seek(0)
    return buffer

# --- 2. 画面レイアウト ---
st.title("🇬🇧 英語問題メーカー")
st.caption("AIを活用した英語教材作成ツール")

# サイドバー設定
with st.sidebar:
    st.header("⚙️ 問題の設定")
    
    grammar_list = [
        "be動詞 (現在)", "一般動詞 (現在)", "疑問文・否定文の作り方",
        "疑問詞 (5W1H)", "命令文", "三人称単数現在 (三単現)",
        "現在進行形", "can (助動詞)", "一般動詞の過去形",
        "名詞の複数形", "代名詞 (I, my, me, mine等)",
        "be動詞 (過去)", "過去進行形"
    ]
    
    grammar_topic = st.selectbox("ターゲット文法", grammar_list)
    st.divider()
    
    problem_type = st.radio(
        "問題形式を選択",
        [
            "🔠 4択問題 (Grammar)",
            "🇯🇵 和訳問題 (Eng → Jap)",
            "🇺🇸 英訳問題 (Jap → Eng)",
            "📖 長文読解 (Reading)"
        ]
    )
    
    level = st.selectbox("レベル目安", ["中学1年基礎", "中学1年応用", "中学2年基礎", "中学2年応用", "中学3年受験"])
    q_num = st.slider("問題数", 1, 10, 5)

    st.divider()
    
    st.header("📚 作成履歴")
    if len(st.session_state.history) > 0:
        for i, item in enumerate(reversed(st.session_state.history)):
            type_label = item['type'][:2] 
            label = f"{type_label} {item['time']} - {item['topic']}"
            if st.button(label, key=f"hist_{i}"):
                st.session_state.current_data = item
                st.rerun()
    else:
        st.info("履歴なし")

# --- 3. メイン処理 ---
if st.button("✨ 問題を作成する", use_container_width=True):
    if not os.path.exists("ipaexg.ttf"):
        st.warning("⚠️ 'ipaexg.ttf' が見つかりません。PDFの日本語が文字化けします。")

    try:
        with st.spinner(f"AIが『{problem_type}』を作成中..."):
            model = genai.GenerativeModel('models/gemini-2.5-flash')
            separator_mark = "|||SPLIT|||"
            
            if problem_type == "🔠 4択問題 (Grammar)":
                instruction = f"ターゲット文法「{grammar_topic}」に関する**4択穴埋め問題**を作成してください。選択肢は (A) (B) (C) (D)。"
            elif problem_type == "🇯🇵 和訳問題 (Eng → Jap)":
                instruction = f"ターゲット文法「{grammar_topic}」を使った**英語の短文**を提示し、日本語訳させる問題を作成してください。"
            elif problem_type == "🇺🇸 英訳問題 (Jap → Eng)":
                instruction = f"ターゲット文法「{grammar_topic}」を使った文を作るための**日本語の短文**を提示し、英語訳させる問題を作成してください。"
            else: 
                instruction = f"ターゲット文法「{grammar_topic}」を多用した**英語の長文ストーリー**を作成し、読解問題を作成してください。"

            prompt = f"""
            あなたは日本の中学校英語教師です。以下の条件でテストを作成してください。
            条件: レベル[{level}] 問題数[{q_num}]
            指示: {instruction}
            禁止: マークダウン記号(**など)
            
            【出力フォーマット】
            必ず問題と解答の間に「{separator_mark}」を入れてください。
            
            タイトル: {grammar_topic} 確認テスト ({problem_type})
            名前: ____________________
            
            (問題文)
            
            {separator_mark}
            
            【解答・解説】
            (解答文)
            """
            
            response = model.generate_content(prompt)
            generated_text = response.text
            generated_text = generated_text.replace("**", "").replace("##", "").replace("__", "")
            
            if separator_mark in generated_text:
                parts = generated_text.split(separator_mark)
                q_text = parts[0].strip()
                a_text = parts[1].strip()
            else:
                q_text = generated_text
                a_text = "分割失敗"

            new_data = {
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "topic": grammar_topic,
                "type": problem_type,
                "q_text": q_text,
                "a_text": a_text
            }
            
            st.session_state.history.append(new_data)
            st.session_state.current_data = new_data
            st.rerun()

    except Exception as e:
        st.error(f"エラー: {e}")

# --- 4. 結果表示 ---
if st.session_state.current_data is not None:
    data = st.session_state.current_data
    
    st.divider()
    st.subheader(f"📄 {data['topic']} ({data['type']})")
    
    tab1, tab2 = st.tabs(["問題プレビュー", "解答プレビュー"])
    with tab1:
        st.text_area("問題", data['q_text'], height=400)
    with tab2:
        st.text_area("解答", data['a_text'], height=400)
    
    pdf_q = create_pdf(data['q_text'])
    pdf_a = create_pdf(data['a_text'])
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("⬇️ 問題PDF", pdf_q, file_name="question.pdf", mime="application/pdf")
    with col2:
        st.download_button("⬇️ 解答PDF", pdf_a, file_name="answer.pdf", mime="application/pdf")