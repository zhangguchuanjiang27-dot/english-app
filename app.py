import streamlit as st
from openai import OpenAI
import hmac
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
import datetime

# --- 0. ログイン機能 ---
def check_password():
    if st.session_state.get('password_correct', False):
        return True

    st.title("🔒 先生用ログイン (OpenAI版)")
    st.caption("管理者から配布されたIDとパスワードを入力してください。")
    
    with st.form("login_form"):
        user_id = st.text_input("ユーザーID")
        password = st.text_input("パスワード", type="password")
        submit_button = st.form_submit_button("ログイン")

        if submit_button:
            if "passwords" not in st.secrets:
                st.error("設定エラー: Secretsにユーザー情報が登録されていません。")
                return False
            
            if user_id in st.secrets["passwords"] and \
               hmac.compare_digest(password, st.secrets["passwords"][user_id]):
                st.session_state['password_correct'] = True
                st.session_state['user_id'] = user_id
                st.rerun()
            else:
                st.error("IDまたはパスワードが間違っています。")
    return False

if not check_password():
    st.stop()

# ========================================================
# 🔓 ログイン成功後の世界
# ========================================================

# --- APIキーの取得 ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except:
    st.error("APIキーが設定されていません。Secretsの OPENAI_API_KEY を設定してください。")
    st.stop()

# --- OpenAIクライアント ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- セッションステート (履歴機能は削除し、現在のデータのみ保持) ---
if 'current_data' not in st.session_state:
    st.session_state.current_data = None

# --- PDF関数 ---
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

# --- 音声生成関数 ---
def generate_speech(text):
    try:
        # ポーズ（間）を作るための調整
        formatted_text = text.replace("[PAUSE]", " ... ... ... ") 
        
        # 万が一「Title:」などが残っていたら削除する念入りな処理
        lines = formatted_text.split('\n')
        clean_lines = [line for line in lines if not line.strip().lower().startswith("title")]
        clean_text = "\n".join(clean_lines)

        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=clean_text
        )
        return io.BytesIO(response.content)
    except Exception as e:
        st.error(f"音声生成エラー: {e}")
        return None

# --- 画面レイアウト ---
st.title("🇬🇧 英語問題メーカー (Simple)")
st.caption("必要な機能だけに絞ったシンプル版です。")

with st.sidebar:
    st.header("⚙️ 問題の設定")
    grammar_list = [
        "be動詞 (現在)", "一般動詞 (現在)", "疑問文・否定文の作り方",
        "疑問詞 (5W1H)", "命令文", "三人称単数現在 (三単現)",
        "現在進行形", "can (助動詞)", "一般動詞の過去形",
        "名詞の複数形", "代名詞 (I, my, me, mine等)",
        "be動詞 (過去)", "過去進行形", "不定詞", "動名詞", "比較"
    ]
    
    selected_grammars = st.multiselect(
        "ターゲット文法 (複数選択可)", 
        grammar_list, 
        default=["be動詞 (現在)"]
    )
    
    st.divider()
    
    problem_type = st.radio("問題形式を選択", [
        "🎧 リスニング問題 (Listening)",
        "🔠 4択問題 (Grammar)",
        "🇯🇵 和訳問題 (Eng → Jap)",
        "🇺🇸 英訳問題 (Jap → Eng)",
        "📖 長文読解 (Reading)"
    ])
    
    level = st.selectbox("レベル目安", ["中学1年基礎", "中学1年応用", "中学2年基礎", "中学2年応用", "中学3年受験"])
    q_num = st.slider("問題数", 1, 10, 5)

    # 履歴欄は削除しました

# --- メイン処理 ---
if st.button("✨ 問題を作成する", use_container_width=True):
    if not os.path.exists("ipaexg.ttf"):
        st.warning("⚠️ 'ipaexg.ttf' が見つかりません。PDFの日本語が文字化けします。")

    if not selected_grammars:
        st.error("⚠️ 文法項目を少なくとも1つ選択してください。")
        st.stop()

    try:
        grammar_topic_str = "、".join(selected_grammars)
        
        with st.spinner(f"AIが『{problem_type}』を作成中..."):
            
            separator_mark = "|||SPLIT|||"
            script_mark = "|||SCRIPT_END|||"
            
            if len(selected_grammars) == 1:
                mix_instruction = f"ターゲット文法「{grammar_topic_str}」を集中的に使用してください。"
            else:
                mix_instruction = f"ターゲット文法「{grammar_topic_str}」をなるべく全て使用・網羅するように構成してください。"

            # 形式ごとの指示
            if problem_type == "🎧 リスニング問題 (Listening)":
                instruction = f"""
                ターゲット文法「{grammar_topic_str}」を使った**リスニングテスト（物語形式）**を作成してください。
                
                【超重要：構成ルール】
                AIは以下の順番でテキストを出力すること。**冒頭にタイトルや挨拶を一切書かないこと。**
                
                1. **[放送文パート]**:
                   - いきなり英語の物語(Story)から書き始めること。
                   - 物語の直後に "Question 1: ...", "Question 2: ..." と質問文を続けること。
                   - 質問の間には `[PAUSE]` を入れること。
                   - 日本語訳や注釈は一切含めないこと（英語のみ）。
                
                2. **{script_mark}** (この区切り文字を入れる)
                
                3. **[生徒用問題用紙パート]**:
                   - 質問文は書かず、**4つの選択肢 (A)(B)(C)(D) のみを記述**すること。
                   - タイトル: {grammar_topic_str} 確認テスト
                   - 名前欄: ______________
                
                4. **{separator_mark}** (この区切り文字を入れる)
                
                5. **[解答パート]**:
                   - 解答と解説、放送文のスクリプト（和訳付き）を記述。
                """
            elif problem_type == "🔠 4択問題 (Grammar)":
                instruction = f"""
                文法「{grammar_topic_str}」の**4択穴埋め問題**。(A)(B)(C)(D)形式。指示: {mix_instruction}
                構成: [問題用紙] -> {separator_mark} -> [解答]
                問題用紙の冒頭にタイトルと名前欄をつけること。
                """
            elif problem_type == "🇯🇵 和訳問題 (Eng → Jap)":
                instruction = f"""
                文法「{grammar_topic_str}」を使った**英語短文**とその和訳問題。指示: {mix_instruction}
                構成: [問題用紙] -> {separator_mark} -> [解答]
                問題用紙の冒頭にタイトルと名前欄をつけること。
                """
            elif problem_type == "🇺🇸 英訳問題 (Jap → Eng)":
                instruction = f"""
                文法「{grammar_topic_str}」を使った**日本語短文**とその英訳問題。指示: {mix_instruction}
                構成: [問題用紙] -> {separator_mark} -> [解答]
                問題用紙の冒頭にタイトルと名前欄をつけること。
                """
            else:
                instruction = f"""
                文法「{grammar_topic_str}」を使った**英語長文**とその読解問題。指示: {mix_instruction}
                構成: [問題用紙] -> {separator_mark} -> [解答]
                問題用紙の冒頭にタイトルと名前欄をつけること。
                """

            prompt = f"""
            あなたは日本の中学校英語教師です。以下の条件でテストを作成してください。
            条件: レベル[{level}] 問題数[{q_num}]
            指示: {instruction}
            禁止: マークダウン記号(**など)
            """

            # --- テキスト生成 ---
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            generated_text = response.choices[0].message.content
            generated_text = generated_text.replace("**", "").replace("##", "").replace("__", "")
            
            # --- 解析処理 ---
            audio_data = None
            script_text = ""
            
            if problem_type == "🎧 リスニング問題 (Listening)" and script_mark in generated_text:
                parts = generated_text.split(script_mark)
                script_part = parts[0].strip() # 放送文
                rest_part = parts[1].strip()   # 問題と解答
                
                # スクリプトの掃除（Titleなどが残っていたら消す）
                script_text = script_part.replace("Title:", "").strip()
                
                audio_data = generate_speech(script_text)
                
                if separator_mark in rest_part:
                    q_a_parts = rest_part.split(separator_mark)
                    q_text = q_a_parts[0].strip()
                    a_text = f"【放送文(Script)】\n\n{script_text}\n\n----------------\n\n" + q_a_parts[1].strip()
                else:
                    q_text = rest_part
                    a_text = "分割失敗"
                    
            else:
                # リスニング以外
                if separator_mark in generated_text:
                    parts = generated_text.split(separator_mark)
                    q_text = parts[0].strip()
                    a_text = parts[1].strip()
                else:
                    q_text = generated_text
                    a_text = "分割失敗"

            new_data = {
                "type": problem_type,
                "q_text": q_text,
                "a_text": a_text,
                "audio": audio_data,
                "script": script_text
            }
            
            st.session_state.current_data = new_data
            st.rerun()

    except Exception as e:
        st.error(f"エラー: {e}")

# --- 結果表示 ---
if st.session_state.current_data is not None:
    data = st.session_state.current_data
    
    st.divider()
    st.subheader(f"📄 作成結果")
    
    if data['type'] == "🎧 リスニング問題 (Listening)" and data['audio'] is not None:
        st.info("🎧 生成された音声")
        st.audio(data['audio'], format="audio/mp3")
        
        st.download_button(
            label="⬇️ 音声(MP3)をダウンロード",
            data=data['audio'],
            file_name=f"listening_audio.mp3",
            mime="audio/mpeg"
        )
        with st.expander("放送文（スクリプト）を確認"):
            st.write(data['script'])
    
    tab1, tab2 = st.tabs(["問題用紙", "解答・解説"])
    with tab1:
        st.text_area("問題プレビュー", data['q_text'], height=400)
    with tab2:
        st.text_area("解答プレビュー", data['a_text'], height=400)
    
    pdf_q = create_pdf(data['q_text'])
    pdf_a = create_pdf(data['a_text'])
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("⬇️ 問題PDF", pdf_q, file_name="question.pdf", mime="application/pdf")
    with col2:
        st.download_button("⬇️ 解答PDF", pdf_a, file_name="answer.pdf", mime="application/pdf")