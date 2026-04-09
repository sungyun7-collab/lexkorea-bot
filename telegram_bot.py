"""
LexKorea 판례분석 텔레그램 봇
===============================
사용법: 텔레그램에서 사건 개요를 입력하면 유사 판례와 유불리 분석을 답장해줍니다.

환경변수 설정:
  TELEGRAM_BOT_TOKEN  : BotFather에서 받은 봇 토큰
  CLAUDE_API_KEY      : Anthropic Claude API 키
"""

import os
import logging
import anthropic
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ── 로깅 설정 ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── 환경변수 ───────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")

# ── 대화 상태 ──────────────────────────────────────────────────────────────
CHOOSE_FIELD, INPUT_CASE = range(2)

# ── 법률 분야 목록 ─────────────────────────────────────────────────────────
LEGAL_FIELDS = {
    "⚖️ 민사": "민사",
    "🔒 형사": "형사",
    "👷 노동": "노동",
    "🏠 부동산": "부동산",
    "🏥 의료법": "의료법",
}

FIELD_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton(k)] for k in LEGAL_FIELDS.keys()],
    resize_keyboard=True,
    one_time_keyboard=True,
)

# ── Claude 분석 함수 ────────────────────────────────────────────────────────
def analyze_with_claude(field: str, case_text: str) -> str:
    """Claude API를 호출하여 판례 분석 결과를 반환합니다."""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    system_prompt = f"""당신은 한국 {field} 법률 전문가입니다.
사용자가 사건 개요를 입력하면 다음 형식으로 분석해 주세요:

1. 📋 **핵심 쟁점** (2~3가지)
2. ⚖️ **유사 판례** (3~5개)
   - 판례명/사건번호
   - 요지 한 줄 요약
   - 본 사건과의 관련성
3. ✅ **유리한 요소**
4. ❌ **불리한 요소**
5. 🔮 **종합 전망** (승소 가능성 및 권고사항)

⚠️ 이 분석은 참고용이며, 정확한 법률 조언은 변호사와 상담하세요.
텔레그램 메시지에 적합하게 간결하고 명확하게 작성하세요."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": f"[{field} 사건]\n\n{case_text}"}],
    )
    return message.content[0].text


# ── 핸들러 ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """봇 시작 명령어 처리"""
    await update.message.reply_text(
        "⚖️ *LexKorea 판례분석 봇*에 오신 것을 환영합니다!\n\n"
        "사건을 분석할 법률 분야를 선택해 주세요:",
        parse_mode="Markdown",
        reply_markup=FIELD_KEYBOARD,
    )
    return CHOOSE_FIELD


async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """법률 분야 선택 처리"""
    text = update.message.text
    field = LEGAL_FIELDS.get(text)

    if not field:
        await update.message.reply_text(
            "아래 버튼 중 하나를 선택해 주세요.",
            reply_markup=FIELD_KEYBOARD,
        )
        return CHOOSE_FIELD

    context.user_data["field"] = field
    await update.message.reply_text(
        f"*{field}* 분야를 선택하셨습니다.\n\n"
        "📝 사건 개요와 사실관계를 자세히 입력해 주세요.\n"
        "(언제, 어디서, 무슨 일이 있었는지 구체적으로 써주실수록 분석이 정확해집니다)\n\n"
        "취소하려면 /cancel 을 입력하세요.",
        parse_mode="Markdown",
        reply_markup=None,
    )
    return INPUT_CASE


async def input_case(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """사건 개요 입력 후 Claude 분석 실행"""
    case_text = update.message.text
    field = context.user_data.get("field", "민사")

    await update.message.reply_text("🔍 판례를 분석 중입니다... 잠시만 기다려 주세요.")

    try:
        result = analyze_with_claude(field, case_text)

        # 텔레그램 메시지 길이 제한(4096자) 대응
        if len(result) > 4000:
            chunks = [result[i : i + 4000] for i in range(0, len(result), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text(result, parse_mode="Markdown")

    except anthropic.APIError as e:
        logger.error("Claude API 오류: %s", e)
        await update.message.reply_text(
            "❌ API 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.\n"
            f"오류 내용: {str(e)}"
        )
    except Exception as e:
        logger.error("예상치 못한 오류: %s", e)
        await update.message.reply_text("❌ 오류가 발생했습니다. 잠시 후 /start 로 다시 시작해 주세요.")

    # 분석 완료 후 새 분석 시작 안내
    await update.message.reply_text(
        "✅ 분석 완료!\n새 사건을 분석하려면 /start 를 입력하세요.",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """대화 취소"""
    await update.message.reply_text(
        "취소되었습니다. 새로 시작하려면 /start 를 입력하세요."
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """도움말"""
    await update.message.reply_text(
        "⚖️ *LexKorea 판례분석 봇 사용법*\n\n"
        "1. /start — 분석 시작\n"
        "2. 법률 분야 선택 (민사/형사/노동/부동산/의료법)\n"
        "3. 사건 개요와 사실관계 입력\n"
        "4. 유사 판례 및 유불리 분석 결과 수신\n\n"
        "/cancel — 현재 분석 취소\n"
        "/help — 이 도움말 보기\n\n"
        "⚠️ 분석 결과는 참고용입니다. 정확한 법률 조언은 변호사와 상담하세요.",
        parse_mode="Markdown",
    )


# ── 메인 ───────────────────────────────────────────────────────────────────
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("환경변수 TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다.")
    if not CLAUDE_API_KEY:
        raise ValueError("환경변수 CLAUDE_API_KEY 가 설정되지 않았습니다.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_field)],
            INPUT_CASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_case)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))

    logger.info("봇 시작됨 — polling 모드")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
