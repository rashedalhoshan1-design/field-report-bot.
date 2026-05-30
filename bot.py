import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

(FLIGHT_NUM, DATE, CARRIER, ORIGIN, BLOCK_ON, STAND,
 AC_TYPE, PAX, BUS_COUNT, LATE_BUS, PREV_BUS, DELAY_MIN,
 SUBJECT, EXTRA, ACTIONS) = range(15)

ARABIC_MONTHS = ['','يناير','فبراير','مارس','أبريل','مايو','يونيو',
                 'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']

def format_date(date_str):
    try:
        d = datetime.strptime(date_str, "%d/%m/%Y")
        return f"{d.day} {ARABIC_MONTHS[d.month]} {d.year}"
    except:
        return date_str

def build_report(d):
    summary = (
        f"تمت متابعة الرحلة ميدانياً، وتم دعم الرحلة بـ {d['bus_count']} باصات من قبل شركة SAAS. "
        f"كانت جميع الباصات جاهزة ووصلت في الوقت المطلوب"
    )
    if d.get('late_bus','').strip() != 'لا':
        summary += (
            f"، باستثناء الباص رقم {d['late_bus']}"
            f" الذي تأخر لمدة {d['delay_min']} دقيقة"
            f" بعد مغادرة الباص رقم {d['prev_bus']}"
            f"، مما أدى إلى انتظار بعض الركاب خارج الطائرة."
        )
    else:
        summary += "."

    if d.get('extra','').strip() not in ('لا',''):
        summary += f"\n{d['extra']}"

    if d.get('actions','').strip() not in ('لا',''):
        actions = "\n".join(f"• {a.strip()}" for a in d['actions'].split('\n') if a.strip())
    else:
        actions = "• تم توثيق الحالة ومتابعتها ميدانياً أثناء التشغيل."
        if d.get('late_bus','').strip() != 'لا':
            actions += f"\n• سوف يتم رفع Inspection Report على شركة SAAS بسبب تأخر الباص رقم {d['late_bus']}."

    sep = "─" * 35
    return f"""تقرير ميداني
{sep}
رقم الرحلة     : {d['flight_num']}
التاريخ        : {format_date(d['date'])}
الناقل         : {d['carrier']}
القادمة من     : {d['origin']}
Block On       : {d['block_on']}
الموقف (Stand) : {d['stand']}
نوع الطائرة   : {d['ac_type']}
عدد الركاب    : {d['pax']} راكب
{sep}
الموضوع:
{d['subject']}

ملخص الحالة التشغيلية:
{summary}

الإجراء المتخذ:
{actions}
{sep}""".strip()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    today = datetime.now().strftime("%d/%m/%Y")
    await update.message.reply_text(
        f"✈️ مولّد التقرير الميداني\n\nأرسل /cancel للإلغاء في أي وقت.\n\n📋 رقم الرحلة؟\nمثال: SV1084"
    )
    return FLIGHT_NUM

async def get_flight_num(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['flight_num'] = update.message.text.strip()
    today = datetime.now().strftime("%d/%m/%Y")
    await update.message.reply_text(f"📅 التاريخ؟\nمثال: {today}")
    return DATE

async def get_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['date'] = update.message.text.strip()
    await update.message.reply_text("🏢 الناقل؟\nمثال: Saudi Airlines")
    return CARRIER

async def get_carrier(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['carrier'] = update.message.text.strip()
    await update.message.reply_text("🛫 القادمة من؟\nمثال: JED")
    return ORIGIN

async def get_origin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['origin'] = update.message.text.strip()
    await update.message.reply_text("⏱ وقت Block On؟\nمثال: 21:50")
    return BLOCK_ON

async def get_block_on(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['block_on'] = update.message.text.strip()
    await update.message.reply_text("🅿️ الموقف (Stand)؟\nمثال: E25C")
    return STAND

async def get_stand(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['stand'] = update.message.text.strip()
    await update.message.reply_text("✈️ نوع الطائرة؟\nمثال: B777")
    return AC_TYPE

async def get_ac_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['ac_type'] = update.message.text.strip()
    await update.message.reply_text("👥 عدد الركاب (PAX)؟\nمثال: 353")
    return PAX

async def get_pax(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['pax'] = update.message.text.strip()
    await update.message.reply_text("🚌 عدد الباصات المخصصة؟\nمثال: 7")
    return BUS_COUNT

async def get_bus_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['bus_count'] = update.message.text.strip()
    await update.message.reply_text("🚌 رقم الباص المتأخر؟\nأرسل لا إذا ما في تأخير")
    return LATE_BUS

async def get_late_bus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['late_bus'] = update.message.text.strip()
    if ctx.user_data['late_bus'] == 'لا':
        ctx.user_data['prev_bus'] = ''
        ctx.user_data['delay_min'] = ''
        await update.message.reply_text("📝 الموضوع؟\nمثال: تأخر باص نقل الركاب الأخير")
        return SUBJECT
    await update.message.reply_text("🚌 الباص الذي غادر قبله؟\nمثال: SR146")
    return PREV_BUS

async def get_prev_bus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['prev_bus'] = update.message.text.strip()
    await update.message.reply_text("⏱ مدة التأخير بالدقائق؟\nمثال: 3")
    return DELAY_MIN

async def get_delay_min(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['delay_min'] = update.message.text.strip()
    await update.message.reply_text("📝 الموضوع؟\nمثال: تأخر باص نقل الركاب الأخير")
    return SUBJECT

async def get_subject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['subject'] = update.message.text.strip()
    await update.message.reply_text("📋 تفاصيل إضافية للملخص؟\nأرسل لا إذا ما في إضافات")
    return EXTRA

async def get_extra(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['extra'] = update.message.text.strip()
    await update.message.reply_text("⚡️ الإجراءات المتخذة؟\nأرسل لا للإجراءات الافتراضية")
    return ACTIONS

async def get_actions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['actions'] = update.message.text.strip()
    report = build_report(ctx.user_data)
    await update.message.reply_text(f"✅ التقرير جاهز:\n\n{report}")
    await update.message.reply_text("🔄 أرسل /start لتقرير جديد")
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء. أرسل /start للبدء من جديد.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FLIGHT_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_flight_num)],
            DATE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            CARRIER:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_carrier)],
            ORIGIN:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_origin)],
            BLOCK_ON:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_block_on)],
            STAND:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stand)],
            AC_TYPE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ac_type)],
            PAX:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pax)],
            BUS_COUNT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bus_count)],
            LATE_BUS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_late_bus)],
            PREV_BUS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_prev_bus)],
            DELAY_MIN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delay_min)],
            SUBJECT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_subject)],
            EXTRA:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra)],
            ACTIONS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_actions)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    print("✅ البوت شغّال!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
