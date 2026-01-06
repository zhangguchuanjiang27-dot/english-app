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

    st.title("🔒 先生用ログイン")
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

# --- OpenAIクライアントの準備 ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- セッションステート初期化 ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_data' not in st.session_state:
    st.session_state.current_data = None

# --- サイドバー ---
st.sidebar.success(f"ログイン中: {st.session_state['user_id']} 先生")
if st.sidebar.button("ログアウト"):
    st.session_state['password_correct'] = False
    st.session_state['user_id'] = None
    st.rerun()
st.sidebar.divider()

# --- PDF関数 ---
def create_pdf(problem_text):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    # フォント設定
    font_name = "Helvetica"
    font_path = "ipaexg.ttf" 
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('IPAexGothic', font_path))
            font_name = 'IPAexGothic'
        except:
            pass
    
    p.setFont(font_name, 11)
    
    # ページ設定
    width, height = A4
    x_margin = 50
    y_margin = 50
    y = 800
    line_height = 15
    max_width = width - (x_margin * 2)

    for line in problem_text.split('\n'):
        # 空行の処理
        if not line:
            y -= line_height
            if y < y_margin:
                p.showPage()
                p.setFont(font_name, 11)
                y = 800
            continue
        
        # 文字単位での折り返し処理
        current_line = ""
        for char in line:
            if p.stringWidth(current_line + char, font_name, 11) <= max_width:
                current_line += char
            else:
                p.drawString(x_margin, y, current_line)
                y -= line_height
                if y < y_margin:
                    p.showPage()
                    p.setFont(font_name, 11)
                    y = 800
                current_line = char
        
        # 残りの文字を描画
        if current_line:
            p.drawString(x_margin, y, current_line)
            y -= line_height
            if y < y_margin:
                p.showPage()
                p.setFont(font_name, 11)
                y = 800
                
    p.save()
    buffer.seek(0)
    return buffer

# --- 画面レイアウト ---
st.title("英語問題メーカー")


with st.sidebar:
    st.header("⚙️ 問題の設定")
    
    # ★ここに追加！モデル切り替えスイッチ
    use_gpt4 = st.toggle("🔥 高性能モデル (GPT-4o) を使う", value=False)
    if use_gpt4:
        selected_model = "gpt-4o"
    else:
        st.caption("※高速生成モード (GPT-4o-mini)")
        selected_model = "gpt-4o-mini"
    
    st.divider()

    # --- 文法項目の定義 ---
    grammar_dict = {
        "中学1年生": [
            "be動詞", "一般動詞（基礎）", "疑問詞", "命令文", "代名詞",
            "三人称単数", "現在進行形", "助動詞can",
            "一般動詞の過去（規則）", "一般動詞の過去（不規則）",
            "be動詞の過去", "過去進行形"
        ],
        "中学2年生": [
            "未来形 (will/be going to)", "助動詞 (must/may/should)", 
            "不定詞 (名詞・副詞・形容詞)", "動名詞", "比較 (比較級・最上級)", 
            "接続詞 (that/if/because/when)"
        ],
        "中学3年生": [
            "受動態 (受け身)", "現在完了形", "分詞 (修飾)", 
            "関係代名詞", "間接疑問文"
        ]
    }
    
    selected_grammars = []
    
    st.markdown("##### 文法項目を選択")
    
    # 中1
    with st.expander("中学1年生 (Grade 1)", expanded=True):
        g1_selected = st.multiselect("中1項目", grammar_dict["中学1年生"], default=["be動詞"])
        selected_grammars.extend(g1_selected)
        
    # 中2
    with st.expander("中学2年生 (Grade 2)"):
        g2_selected = st.multiselect("中2項目", grammar_dict["中学2年生"])
        selected_grammars.extend(g2_selected)
        
    # 中3
    with st.expander("中学3年生 (Grade 3)"):
        g3_selected = st.multiselect("中3項目", grammar_dict["中学3年生"])
        selected_grammars.extend(g3_selected)

    st.divider()
    problem_type = st.radio("問題形式を選択", [
        "🔠 4択問題",
        "✏️ 空欄補充問題",
        "和訳問題",
        "英訳問題",
        "📖 長文読解 (4択問題)"
    ])
    
    reading_text_type = "物語文 (Story)"
    if "長文読解" in problem_type:
        reading_text_type = st.radio("文章タイプ", ["物語文 (Story)", "会話文 (Conversation)"])
    
    level = st.selectbox("学年レベル", ["中学1年生", "中学2年生", "中学3年生"])
    
    if "長文読解" in problem_type:
        st.info("※長文読解は「4問」固定です。")
        q_num = 4
    else:
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
        
        # モデル名を表示
        with st.spinner(f"AI ({selected_model}) が『{grammar_topic_str}』の問題を作成中..."):
            separator_mark = "|||SPLIT|||"
            
            # レベルごとの単語制限
            vocab_limit_instruction = ""
            if level == "中学1年生":
                vocab_limit_instruction = """
                【超重要：単語レベル制限】
                - 中学1年生の教科書(New Horizon Book 1など)に出てくる**超基本的な英単語のみ**を使用すること。
                - 許可されていない文法を使った難しい表現は避けてください。
                """
            elif level == "中学2年生":
                vocab_limit_instruction = """
                【単語レベル制限】
                - 中学2年生レベル(英検4級〜3級)の英単語を使用すること。
                """
            else: # 中学3年生
                vocab_limit_instruction = """
                【単語レベル制限】
                - 中学3年生・高校入試レベル(英検3級〜準2級)の英単語を使用すること。
                """
            
            # --- 文法レベル制限の構築 ---
            allowed_grammar_items = []
            if level == "中学1年生":
                allowed_grammar_items = grammar_dict["中学1年生"]
            elif level == "中学2年生":
                allowed_grammar_items = grammar_dict["中学1年生"] + grammar_dict["中学2年生"]
            else: # 中学3年生
                allowed_grammar_items = grammar_dict["中学1年生"] + grammar_dict["中学2年生"] + grammar_dict["中学3年生"]
            
            allowed_grammar_str = "、".join(allowed_grammar_items)
            grammar_limit_instruction = f"""
            【文法使用制限 (重要)】
            - 本文および設問では、原則として以下の「{level}までの既習範囲」の文法のみを使用してください。
            - 許可される文法範囲: {allowed_grammar_str}
            - 上記範囲外の文法 (例: 中1なのにshouldなど) は絶対に使用しないでください。
            - ただし、ターゲットとして選択された文法項目「{grammar_topic_str}」は最優先で使用してください。
            """

            if len(selected_grammars) == 1:
                mix_instruction = f"ターゲット文法「{grammar_topic_str}」を集中的に使用してください。"
            else:
                mix_instruction = f"ターゲット文法として選ばれた「{grammar_topic_str}」をなるべく全て使用・網羅するように構成してください。"
            
            # 全文法共通: 否定形・疑問形のバランス指示
            mix_instruction += "\n(重要: 選択された文法項目について、肯定形(Affirmative)だけでなく、否定形(Negative)や疑問形(Question)もバランスよく出題に含めてください。常に肯定文ばかりにならないように注意してください。)"
            
            # be動詞: 主語のバリエーション指示
            if "be動詞" in selected_grammars or "be動詞の過去" in selected_grammars:
                mix_instruction += "\n(重要: be動詞の問題では、主語を I, You, He, She, They などの代名詞だけでなく、『This/That/These/Those』、『There is/are構文』、『人の名前 (Ken, My father等)』など多様な主語をバランスよく使ってください。)"
           
            # 形式ごとの指示
            # 形式ごとの指示
            if problem_type == "🔠 4択問題":
                instruction = f"""
                以下の文法項目に関する**4択穴埋め問題**を作成してください。
                文法項目: {grammar_topic_str}
                指示: {mix_instruction}
                単語制限: {vocab_limit_instruction}
                
                【重要：空欄の形式】
                問題文の空所は `( ______ )` のように、下線を使って明確に記述すること。
                選択肢は (A) (B) (C) (D) の形式で記述すること。

                【重要：解答形式】
                [解答]の側には、正解だけでなく、なぜその答えになるのかの「解説」を必ず記述すること。
                """
            elif problem_type == "和訳問題":
                instruction = f"""
                以下の文法項目を使った**英語の短文**を提示し、日本語訳させる問題を作成してください。
                文法項目: {grammar_topic_str}
                指示: {mix_instruction}
                単語制限: {vocab_limit_instruction}
                
                【重要：出力形式】
                [問題用紙]の側には、**英語の文（問題）のみ**を箇条書きで記述すること。日本語の訳（答え）は絶対に書かないこと。
                必ず "1.", "2.", "3." と番号を振って記述すること。
                [解答]の側に、対応する日本語の全訳と、文法的なポイントの「解説」を必ず記述すること。
                """
            elif problem_type == "英訳問題":
                instruction = f"""
                以下の文法項目を使った文を作るための**日本語の短文**を提示し、英語訳させる問題を作成してください。
                文法項目: {grammar_topic_str}
                指示: {mix_instruction}
                単語制限: {vocab_limit_instruction}
                
                【重要：出力形式】
                [問題用紙]の側には、**日本語の文（問題）のみ**を箇条書きで記述すること。英語の答えは絶対に書かないこと。
                必ず "1.", "2.", "3." と番号を振って記述すること。
                [解答]の側に、対応する英語の正解文と、文法的なポイントの「解説」を必ず記述すること。
                """
            elif problem_type == "✏️ 空欄補充問題":
                instruction = f"""
                以下の文法項目を使った**空所補充問題**を作成してください。
                文法項目: {grammar_topic_str}
                指示: {mix_instruction}
                単語制限: {vocab_limit_instruction}

                【重要：出力形式】
                [問題用紙]の側には、以下の形式で記述すること。
                必ず英語の文の**次の行**に日本語訳を記述すること。
                例:
                1. I (      ) playing soccer now.
                (私は今サッカーをしています。)
                
                [解答]の側に、空所に入る語句と、なぜその語句が入るのかの「解説」を必ず記述すること。
                """
            else: # 長文読解
                text_type_en = "Story" if "物語" in reading_text_type else "Conversation/Dialog"
                text_type_jp = "ストーリー" if "物語" in reading_text_type else "会話文"

                instruction = f"""
                以下の構成で長文読解テストを作成してください。
                
                1. **本文(Passage)**: 文法「{grammar_topic_str}」を多用した**英語の{text_type_jp}({text_type_en})**を作成する。
                   - 【絶対ルール】本文は必ず**英語(English)**で書くこと。日本語で書いてはいけません。
                   - 単語レベル: {vocab_limit_instruction}
                   - 文法レベル: {grammar_limit_instruction}
                
                2. **設問(Questions)**: {text_type_jp}の内容に関する**4択問題(A)(B)(C)(D)をちょうど4問**作成する。
                   - 質問には必ず "Q.1", "Q.2", "Q.3", "Q.4" と番号を振ること。
                   - 【重要】設問文や選択肢を作成する際も、必ず文法使用制限({grammar_limit_instruction})を守ること。
                   - 【重要】ターゲット文法「{grammar_topic_str}」に関連する内容を問うたり、選択肢にその文法を含めたりして、ターゲット文法が定着しているか確認できる問題にすること。
                
                3. **出力ルール**:
                   - [問題用紙]側: 英語の{text_type_jp}本文と、4つの設問(選択肢含む)のみを記述。
                   - [解答]側: **冒頭に必ず{text_type_jp}の全文和訳を記述する**こと。その後に、設問の正解と詳しい「解説」を記述すること。
                
                指示: {mix_instruction}
                """

            prompt = f"""
            あなたは日本の中学校英語教師です。以下の条件でテストを作成してください。
            条件: レベル[{level}] 問題数[{q_num}]
            指示: {instruction}
            禁止: マークダウン記号(**など)
            
            【出力フォーマット】
            必ず問題と解答の間に「{separator_mark}」を入れてください。
            
            タイトル: {grammar_topic_str} 確認テスト ({problem_type})
            
            (問題文)
            
            {separator_mark}
            
            【解答・解説】
            (解答文)
            """

            # --- OpenAIへのリクエスト ---
            response = client.chat.completions.create(
                model=selected_model, # ★スイッチで切り替わったモデルを使う
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            generated_text = response.choices[0].message.content
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
                "topic": grammar_topic_str,
                "type": problem_type,
                "q_text": q_text,
                "a_text": a_text
            }
            
            st.session_state.history.append(new_data)
            st.session_state.current_data = new_data
            st.rerun()

    except Exception as e:
        st.error(f"エラー: {e}")

# --- 結果表示 (編集機能付き) ---
if st.session_state.current_data is not None:
    data = st.session_state.current_data
    
    st.divider()
    st.subheader(f"📄 結果 ({data['type']})")
    st.caption(f"文法: {data['topic']}")
    st.info("💡 下のテキストボックスで内容を修正できます。修正後にPDFボタンを押すと反映されます。")
    
    tab1, tab2 = st.tabs(["問題プレビュー", "解答プレビュー"])
    
    with tab1:
        edited_q_text = st.text_area("問題（編集可）", value=data['q_text'], height=400)
        st.session_state.current_data['q_text'] = edited_q_text
        
    with tab2:
        edited_a_text = st.text_area("解答（編集可）", value=data['a_text'], height=400)
        st.session_state.current_data['a_text'] = edited_a_text
    
    pdf_q = create_pdf(edited_q_text)
    pdf_a = create_pdf(edited_a_text)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("⬇️ 問題PDF", pdf_q, file_name="question.pdf", mime="application/pdf")
    with col2:
        st.download_button("⬇️ 解答PDF", pdf_a, file_name="answer.pdf", mime="application/pdf")