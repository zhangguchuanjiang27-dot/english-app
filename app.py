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

# --- セッションステート初期化 ---
if 'history' not in st.session_state:
    st.session_state.history = []
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
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy", # alloy, echo, fable, onyx, nova, shimmer から選べます
            input=text
        )
        return io.BytesIO(response.content)
    except Exception as e:
        st.error(f"音声生成エラー: {e}")
        return None

# --- 画面レイアウト ---
st.title("🇬🇧 英語問題メーカー (Pro)")
st.caption("リスニング: 会話→質問文(Question 1...)の順で再生されます。")

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
    st.divider()
    
    st.header("📚 作成履歴")
    if len(st.session_state.history) > 0:
        for i, item in enumerate(reversed(st.session_state.history)):
            type_label = item['type'][:2] 
            topics = item['topic'].split("、")
            if len(topics) > 1:
                topic_label = f"{topics[0]} 他{len(topics)-1}件"
            else:
                topic_label = topics[0]
            
            label = f"{type_label} {item['time']} - {topic_label}"
            if st.button(label, key=f"hist_{i}"):
                st.session_state.current_data = item
                st.rerun()
    else:
        st.info("履歴なし")

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
                # ★ここを変更: スクリプトの中に「Question...」を含めるよう指示
                instruction = f"""
                ターゲット文法「{grammar_topic_str}」を使った**リスニングテスト**を作成してください。
                
                【重要：構成について】
                1. **[放送文(Script)]**: 
                   - まず「対話」や「物語」を書く。
                   - その直後に、**"Question 1: ...", "Question 2: ..." と質問文自体も続けて記述する**こと。
                   - 音声生成に使うため、ここにはト書き（Narrator:など）以外の日本語解説は入れないこと。
                
                2. **[問題用紙(Student Sheet)]**: 
                   - 生徒には音声で質問を聞かせるため、ここには**質問文を書かず**、(A) (B) (C) (D) の選択肢のみを記述すること。
                
                3. 出力順序:
                   [放送文(会話+質問)] -> {script_mark} -> [問題用紙(選択肢のみ)] -> {separator_mark} -> [解答(スクリプト訳・答え)]
                """
            elif problem_type == "🔠 4択問題 (Grammar)":
                instruction = f"文法「{grammar_topic_str}」の**4択穴埋め問題**。(A)(B)(C)(D)形式。指示: {mix_instruction}"
            elif problem_type == "🇯🇵 和訳問題 (Eng → Jap)":
                instruction = f"文法「{grammar_topic_str}」を使った**英語短文**とその和訳問題。指示: {mix_instruction}"
            elif problem_type == "🇺🇸 英訳問題 (Jap → Eng)":
                instruction = f"文法「{grammar_topic_str}」を使った**日本語短文**とその英訳問題。指示: {mix_instruction}"
            else:
                instruction = f"文法「{grammar_topic_str}」を使った**英語長文**とその読解問題。指示: {mix_instruction}"

            prompt = f"""
            あなたは日本の中学校英語教師です。以下の条件でテストを作成してください。
            条件: レベル[{level}] 問題数[{q_num}]
            指示: {instruction}
            禁止: マークダウン記号(**など)
            
            【出力フォーマットのルール】
            - 問題と解答の間には必ず「{separator_mark}」を入れること。
            - リスニングの場合、放送文の終わりに「{script_mark}」を入れること。
            
            タイトル: {grammar_topic_str} 確認テスト ({problem_type})
            名前: ____________________
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
                script_part = parts[0].strip()
                rest_part = parts[1].strip()
                
                script_text = script_part.replace("[放送文]", "").replace("Script:", "").strip()
                # 音声生成 (会話 + Questionも読まれる)
                audio_data = generate_speech(script_text)
                
                if separator_mark in rest_part:
                    q_a_parts = rest_part.split(separator_mark)
                    q_text = q_a_parts[0].strip()
                    # 解答PDFにはスクリプト全文を載せる
                    a_text = f"【放送文(Script)】\n\n{script_text}\n\n----------------\n\n" + q_a_parts[1].strip()
                else:
                    q_text = rest_part
                    a_text = "分割失敗"
                    
            else:
                if separator_mark in generated_text:
                    parts = generated_text.split(separator_mark)
                    q_text = parts[0].strip()
                    a_text = parts[1].strip()
                else:
                    q_text = generated_text
                    a_text = "分割失敗"

            new_data = {
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "topic": grammar_topic_str,
                "type": problem_type,
                "q_text": q_text,
                "a_text": a_text,
                "audio": audio_data,
                "script": script_text
            }
            
            st.session_state.history.append(new_data)
            st.session_state.current_data = new_data
            st.rerun()

    except Exception as e:
        st.error(f"エラー: {e}")

# --- 結果表示 ---
if st.session_state.current_data is not None:
    data = st.session_state.current_data
    
    st.divider()
    st.subheader(f"📄 結果 ({data['type']})")
    
    if data['type'] == "🎧 リスニング問題 (Listening)" and data['audio'] is not None:
        st.info("🎧 生成された音声を確認できます")
        st.audio(data['audio'], format="audio/mp3")
        
        st.download_button(
            label="⬇️ 音声(MP3)をダウンロード",
            data=data['audio'],
            file_name=f"listening_audio.mp3",
            mime="audio/mpeg"
        )
        with st.expander("放送文（スクリプト）を見る"):
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