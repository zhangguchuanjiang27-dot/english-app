import streamlit as st
import google.generativeai as genai
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
import datetime

# ==========================================
# 👇 ここにあなたのAPIキーを貼り付けてください
API_KEY = "AIzaSyBCFa_edizOfgLjeRa8LnhRl_RtT8P339s" 
# ==========================================

# --- 初期設定 ---
if len(API_KEY) < 30:
    st.error("APIキーが正しく設定されていません。コードを確認してください。")
else:
    genai.configure(api_key=API_KEY)

# --- セッションステート初期化 ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_data' not in st.session_state:
    st.session_state.current_data = None

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
st.title("🇬🇧 英語問題メーカー (Multi-Mode)")
st.caption("4択・和訳・英訳・長文読解の4つのモードに対応しました。")

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
    
    # ★ここを拡張しました
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
    
    # 履歴表示エリア
    st.header("📚 作成履歴")
    if len(st.session_state.history) > 0:
        for i, item in enumerate(reversed(st.session_state.history)):
            # 履歴ラベルに「形式」も表示するように変更
            type_label = item['type'][:2] # 絵文字だけ取る
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
            
            # --- プロンプトの切り替えロジック ---
            if problem_type == "🔠 4択問題 (Grammar)":
                instruction = f"""
                ターゲット文法「{grammar_topic}」に関する**4択穴埋め問題**を作成してください。
                選択肢は (A) (B) (C) (D) の形式にしてください。
                """
            elif problem_type == "🇯🇵 和訳問題 (Eng → Jap)":
                instruction = f"""
                ターゲット文法「{grammar_topic}」を使った**英語の短文**を提示し、
                それを日本語に訳させる問題を作成してください。
                問題用紙には英語の文だけを書き、解答用紙に模範和訳を書いてください。
                """
            elif problem_type == "🇺🇸 英訳問題 (Jap → Eng)":
                instruction = f"""
                ターゲット文法「{grammar_topic}」を使った文を作るための**日本語の短文**を提示し、
                それを英語に訳させる問題を作成してください。
                整序問題（並び替え）ではなく、記述式（Writing）にしてください。
                """
            else: # 長文読解
                instruction = f"""
                ターゲット文法「{grammar_topic}」を多用した**英語の長文ストーリー**を作成し、
                その内容に関する読解問題（内容一致や理由説明など）を作成してください。
                """

            # 共通プロンプト
            prompt = f"""
            あなたは日本の中学校英語教師です。以下の条件でテストを作成してください。
            
            【条件】
            - 対象レベル: {level}
            - 問題数: {q_num}問
            - 指示: {instruction}
            - 禁止事項: マークダウン記号（**や##）は絶対に使用しないこと。
            
            【出力フォーマット】
            必ず以下の構成にし、問題と解答の間に「{separator_mark}」を入れてください。
            
            タイトル: {grammar_topic} 確認テスト ({problem_type})
            名前: ____________________
            
            (ここに生徒用の問題を記述)
            (記述スペースが必要な場合は ______________ のように下線を引いてください)
            
            {separator_mark}
            
            【解答・解説】
            (ここに解答と、なぜそうなるかの解説を記述)
            """
            
            response = model.generate_content(prompt)
            generated_text = response.text
            generated_text = generated_text.replace("**", "").replace("##", "").replace("__", "")
            
            # 分割処理
            if separator_mark in generated_text:
                parts = generated_text.split(separator_mark)
                q_text = parts[0].strip()
                a_text = parts[1].strip()
            else:
                q_text = generated_text
                a_text = "分割失敗"

            # 履歴に保存するデータ
            new_data = {
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "topic": grammar_topic,
                "type": problem_type, # 形式も保存
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
        st.download_button(
            label="⬇️ 問題PDF",
            data=pdf_q,
            file_name="question.pdf",
            mime="application/pdf"
        )
    with col2:
        st.download_button(
            label="⬇️ 解答PDF",
            data=pdf_a,
            file_name="answer.pdf",
            mime="application/pdf"
        )