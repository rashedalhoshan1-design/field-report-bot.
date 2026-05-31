import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

# States
(REPORT_TYPE,
 # تقرير ميداني
 F_FLIGHT, F_DATE, F_CARRIER, F_ORIGIN, F_BLOCK_ON, F_STAND,
 F_AC_TYPE, F_PAX, F_BUS_COUNT, F_LATE_BUS, F_PREV_BUS, F_DELAY_MIN,
 F_SUBJECT, F_EXTRA, F_ACTIONS,
 # تقرير متابعة تشغيلية
 T_FLIGHT, T_DATE, T_CARRIER, T_DEST, T_DEP_TIME, T_STAND,
 T_SUBJECT, T_DETAILS, T_ACTIONS, T_FINAL_STATUS
) = range(26)

ARABIC_MONTHS = ['','يناير','فبراير','مارس','أبريل','مايو','يونيو',
                 'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']

def format_date(s):
    if not s or s == 'تخطي':
        return ''
    try:
        d = datetime.strptime(s, "%d/%m/%Y")
        return f"{d.day} {ARABIC_MONTHS[d.month]} {d.year}"
    except:
        return s

def skip_hint(field):
    return f"\nأرسل *تخطي* لتركه فارغاً" if field in ['date','time'] else ""

SEP = "─" * 32

# ─── تقرير ميداني ───────────────────────────────
def build_field_report(d):
    date_str = format_date(d.get('date',''))
    block_on = d.get('block_on','')
    late = d.get('late_bus','').strip()

    summary = (f"تمت متابعة الرحلة ميدانياً، وتم دعم الرحلة بـ {d['bus_count']} "
               f"باصات من قبل شركة SAAS. كانت جميع الباصات جاهزة ووصلت في الوقت المطلوب")
    if late and late != 'لا':
        summary += (f"، باستثناء الباص رقم {late} الذي تأخر لمدة {d['delay_min']} دقيقة"
                    f" بعد مغادرة الباص رقم {d['prev_bus']}، مما أدى إلى انتظار بعض الركاب خارج الطائرة.")
    else:
        summary += "."

    extra = d.get('extra','').strip()
    if extra and extra != 'لا':
        summary += f"\n{extra}"

    actions_raw = d.get('actions','').strip()
    if actions_raw and actions_raw != 'لا':
        actions = "\n".join(f"• {a.strip()}" for a in actions_raw.split('\n') if a.strip())
    else:
        actions = "• تم توثيق الحالة ومتابعتها ميدانياً أثناء التشغيل."
        if late and late != 'لا':
            actions += f"\n• سوف يتم رفع Inspection Report على شركة SAAS بسبب تأخر الباص رقم {late}."

    lines = ["تقرير ميداني", SEP]
    lines.append(f"رقم الرحلة     : {d['flight_num']}")
    if date_str: lines.append(f"التاريخ        : {date_str}")
    lines.append(f"الناقل         : {d['carrier']}")
    lines.append(f"القادمة من     : {d['origin']}")
    if block_on and block_on != 'تخطي': lines.append(f"Block On       : {block_on}")
    lines.append(f"الموقف (Stand) : {d['stand']}")
    lines.append(f"نوع الطائرة   : {d['ac_type']}")
    lines.append(f"عدد الركاب    : {d['pax']} راكب")
    lines += [SEP, f"الموضوع:\n{d['subject']}", "",
              f"ملخص الحالة التشغيلية:\n{summary}", "",
              f"الإجراء المتخذ:\n{actions}", SEP]
    return "\n".join(lines)

# ─── تقرير متابعة تشغيلية ───────────────────────
def build_ops_report(d):
    date_str = format_date(d.get('date',''))
    dep_time = d.get('dep_time','')
    details = d.get('details','').strip()
    actions_raw = d.get('actions','').strip()
    final = d.get('final_status','').strip()

    if actions_raw and actions_raw != 'لا':
        actions = "\n".join(f"• {a.strip()}" for a in actions_raw.split('\n') if a.strip())
    else:
        actions = "• تمت متابعة الرحلة ميدانياً حتى اكتمال الإجراءات التشغيلية."

    lines = ["تقرير متابعة تشغيلية", SEP]
    lines.append(f"رقم الرحلة     : {d['flight_num']}")
    if date_str: lines.append(f"التاريخ        : {date_str}")
    lines.append(f"الناقل         : {d['carrier']}")
    lines.append(f"الوجهة         : {d['dest']}")
    if dep_time and dep_time != 'تخطي': lines.append(f"وقت المغادرة   : {dep_time}")
    lines.append(f"الموقف (Stand) : {d['stand']}")
    lines += [SEP, f"الموضوع:\n{d['subject']}", ""]
    if details and details != 'لا':
        lines += [f"التفاصيل:\n{details}", ""]
    lines += [f"الإجراءات:\n{actions}", ""]
    if final and final != 'لا':
        lines += [f"الحالة النهائية:\n{final}", ""]
    lines.append(SEP)
    return "\n".join(lines)

# ─── start ──────────────────────────────────────
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data.clear()
    kb = [["📋 تقرير ميداني", "📊 تقرير متابعة تشغيلية"]]
    await u.message.reply_text(
        "✈️ مولّد التقارير الميدانية\n\n/cancel للإلغاء\n\nاختر نوع التقرير:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
    )
    return REPORT_TYPE

async def report_type(u: Update, c: ContextTypes.DEFAULT_TYPE):
    t = u.message.text.strip()
    if "ميداني" in t:
        c.user_data['type'] = 'field'
        await u.message.reply_text("📋 *تقرير ميداني*\n\nرقم الرحلة؟\nمثال: SV1084",
                                   parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return F_FLIGHT
    elif "تشغيلية" in t:
        c.user_data['type'] = 'ops'
        await u.message.reply_text("📊 *تقرير متابعة تشغيلية*\n\nرقم الرحلة؟\nمثال: XY093",
                                   parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return T_FLIGHT
    else:
        await u.message.reply_text("اختر من الأزرار 👆")
        return REPORT_TYPE

# ─── تقرير ميداني steps ─────────────────────────
async def f1(u,c): c.user_data['flight_num']=u.message.text.strip(); await u.message.reply_text("📅 التاريخ؟\nمثال: 31/05/2026\nأو أرسل *تخطي*", parse_mode="Markdown"); return F_DATE
async def f2(u,c): c.user_data['date']=u.message.text.strip(); await u.message.reply_text("🏢 الناقل؟\nمثال: Saudi Airlines"); return F_CARRIER
async def f3(u,c): c.user_data['carrier']=u.message.text.strip(); await u.message.reply_text("🛫 القادمة من؟\nمثال: JED"); return F_ORIGIN
async def f4(u,c): c.user_data['origin']=u.message.text.strip(); await u.message.reply_text("⏱ وقت Block On؟\nمثال: 21:50\nأو أرسل *تخطي*", parse_mode="Markdown"); return F_BLOCK_ON
async def f5(u,c): c.user_data['block_on']=u.message.text.strip(); await u.message.reply_text("🅿️ الموقف Stand؟\nمثال: E25C"); return F_STAND
async def f6(u,c): c.user_data['stand']=u.message.text.strip(); await u.message.reply_text("✈️ نوع الطائرة؟\nمثال: B777"); return F_AC_TYPE
async def f7(u,c): c.user_data['ac_type']=u.message.text.strip(); await u.message.reply_text("👥 عدد الركاب PAX؟\nمثال: 353"); return F_PAX
async def f8(u,c): c.user_data['pax']=u.message.text.strip(); await u.message.reply_text("🚌 عدد الباصات؟\nمثال: 7"); return F_BUS_COUNT
async def f9(u,c): c.user_data['bus_count']=u.message.text.strip(); await u.message.reply_text("🚌 رقم الباص المتأخر؟\nأرسل *لا* إذا ما في تأخير", parse_mode="Markdown"); return F_LATE_BUS

async def f10(u,c):
    c.user_data['late_bus']=u.message.text.strip()
    if c.user_data['late_bus']=='لا':
        c.user_data['prev_bus']=''; c.user_data['delay_min']=''
        await u.message.reply_text("📝 الموضوع؟\nمثال: تأخر باص نقل الركاب الأخير"); return F_SUBJECT
    await u.message.reply_text("🚌 الباص الذي غادر قبله؟\nمثال: SR146"); return F_PREV_BUS

async def f11(u,c): c.user_data['prev_bus']=u.message.text.strip(); await u.message.reply_text("⏱ مدة التأخير بالدقائق؟\nمثال: 3"); return F_DELAY_MIN
async def f12(u,c): c.user_data['delay_min']=u.message.text.strip(); await u.message.reply_text("📝 الموضوع؟\nمثال: تأخر باص نقل الركاب الأخير"); return F_SUBJECT
async def f13(u,c): c.user_data['subject']=u.message.text.strip(); await u.message.reply_text("📋 تفاصيل إضافية للملخص؟\nأرسل *لا* إذا ما في", parse_mode="Markdown"); return F_EXTRA
async def f14(u,c): c.user_data['extra']=u.message.text.strip(); await u.message.reply_text("⚡️ الإجراءات المتخذة؟\nأرسل *لا* للافتراضية", parse_mode="Markdown"); return F_ACTIONS

async def f15(u,c):
    c.user_data['actions']=u.message.text.strip()
    await u.message.reply_text(f"✅ التقرير جاهز:\n\n{build_field_report(c.user_data)}")
    await u.message.reply_text("🔄 أرسل /start لتقرير جديد")
    return ConversationHandler.END

# ─── تقرير متابعة تشغيلية steps ─────────────────
async def t1(u,c): c.user_data['flight_num']=u.message.text.strip(); await u.message.reply_text("📅 التاريخ؟\nمثال: 31/05/2026\nأو أرسل *تخطي*", parse_mode="Markdown"); return T_DATE
async def t2(u,c): c.user_data['date']=u.message.text.strip(); await u.message.reply_text("🏢 الناقل؟\nمثال: Flynas"); return T_CARRIER
async def t3(u,c): c.user_data['carrier']=u.message.text.strip(); await u.message.reply_text("🛬 الوجهة؟\nمثال: MED"); return T_DEST
async def t4(u,c): c.user_data['dest']=u.message.text.strip(); await u.message.reply_text("⏱ وقت المغادرة الفعلي؟\nمثال: 08:10\nأو أرسل *تخطي*", parse_mode="Markdown"); return T_DEP_TIME
async def t5(u,c): c.user_data['dep_time']=u.message.text.strip(); await u.message.reply_text("🅿️ الموقف Stand؟\nمثال: E34L"); return T_STAND
async def t6(u,c): c.user_data['stand']=u.message.text.strip(); await u.message.reply_text("📝 الموضوع؟\nمثال: متابعة عمليات Turnaround"); return T_SUBJECT
async def t7(u,c): c.user_data['subject']=u.message.text.strip(); await u.message.reply_text("📋 التفاصيل؟\nاكتب ما تمت ملاحظته وما تم اتخاذه\nأو أرسل *لا* للتخطي", parse_mode="Markdown"); return T_DETAILS
async def t8(u,c): c.user_data['details']=u.message.text.strip(); await u.message.reply_text("⚡️ الإجراءات (نقاط)؟\nأرسل *لا* للافتراضية", parse_mode="Markdown"); return T_ACTIONS
async def t9(u,c): c.user_data['actions']=u.message.text.strip(); await u.message.reply_text("🏁 الحالة النهائية؟\nأو أرسل *لا* للتخطي", parse_mode="Markdown"); return T_FINAL_STATUS

async def t10(u,c):
    c.user_data['final_status']=u.message.text.strip()
    await u.message.reply_text(f"✅ التقرير جاهز:\n\n{build_ops_report(c.user_data)}")
    await u.message.reply_text("🔄 أرسل /start لتقرير جديد")
    return ConversationHandler.END

async def cancel(u,c):
    await u.message.reply_text("❌ تم الإلغاء. /start للبدء من جديد", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    T = filters.TEXT & ~filters.COMMAND
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REPORT_TYPE: [MessageHandler(T, report_type)],
            F_FLIGHT:[MessageHandler(T,f1)], F_DATE:[MessageHandler(T,f2)],
            F_CARRIER:[MessageHandler(T,f3)], F_ORIGIN:[MessageHandler(T,f4)],
            F_BLOCK_ON:[MessageHandler(T,f5)], F_STAND:[MessageHandler(T,f6)],
            F_AC_TYPE:[MessageHandler(T,f7)], F_PAX:[MessageHandler(T,f8)],
            F_BUS_COUNT:[MessageHandler(T,f9)], F_LATE_BUS:[MessageHandler(T,f10)],
            F_PREV_BUS:[MessageHandler(T,f11)], F_DELAY_MIN:[MessageHandler(T,f12)],
            F_SUBJECT:[MessageHandler(T,f13)], F_EXTRA:[MessageHandler(T,f14)],
            F_ACTIONS:[MessageHandler(T,f15)],
            T_FLIGHT:[MessageHandler(T,t1)], T_DATE:[MessageHandler(T,t2)],
            T_CARRIER:[MessageHandler(T,t3)], T_DEST:[MessageHandler(T,t4)],
            T_DEP_TIME:[MessageHandler(T,t5)], T_STAND:[MessageHandler(T,t6)],
            T_SUBJECT:[MessageHandler(T,t7)], T_DETAILS:[MessageHandler(T,t8)],
            T_ACTIONS:[MessageHandler(T,t9)], T_FINAL_STATUS:[MessageHandler(T,t10)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
