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

(REPORT_TYPE,
 F_FLIGHT, F_DATE, F_CARRIER, F_ORIGIN, F_BLOCK_ON, F_STAND,
 F_AC_TYPE, F_PAX, F_BUS_COUNT, F_LATE_BUS, F_PREV_BUS, F_DELAY_MIN,
 F_SUBJECT, F_SUMMARY, F_ACTIONS,
 T_FLIGHT, T_DATE, T_CARRIER, T_DEST, T_DEP_TIME, T_STAND,
 T_SUBJECT, T_DETAILS, T_ACTIONS, T_FINAL_STATUS
) = range(26)

ARABIC_MONTHS = ['','يناير','فبراير','مارس','أبريل','مايو','يونيو',
                 'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']

def now_date():
    d = datetime.now()
    return f"{d.day} {ARABIC_MONTHS[d.month]} {d.year}"

def now_time():
    return datetime.now().strftime("%H:%M")

def parse_val(v, default):
    """إذا المستخدم ما غيّر، يرجع الافتراضي. وإلا يرجع اللي كتبه."""
    v = v.strip() if v else ''
    if not v:
        return default
    return v

SEP = "─" * 32

def build_field_report(d):
    late = d.get('late_bus','').strip()

    # ملخص افتراضي
    default_summary = (
        f"تمت متابعة الرحلة ميدانياً، وتم دعم الرحلة بـ {d['bus_count']} "
        f"باصات من قبل شركة SAAS. كانت جميع الباصات جاهزة ووصلت في الوقت المطلوب"
    )
    if late and late != 'لا':
        default_summary += (
            f"، باستثناء الباص رقم {late} الذي تأخر لمدة {d.get('delay_min','')} دقيقة"
            f" بعد مغادرة الباص رقم {d.get('prev_bus','')}، "
            f"مما أدى إلى انتظار بعض الركاب خارج الطائرة."
        )
    else:
        default_summary += "."

    # إجراءات افتراضية
    default_actions = "• تم توثيق الحالة ومتابعتها ميدانياً أثناء التشغيل."
    if late and late != 'لا':
        default_actions += f"\n• سوف يتم رفع Inspection Report على شركة SAAS بسبب تأخر الباص رقم {late}."

    summary = parse_val(d.get('summary',''), default_summary)
    actions_raw = parse_val(d.get('actions',''), default_actions)

    # إذا المستخدم كتب إجراءات، نحول كل سطر لنقطة
    if actions_raw != default_actions:
        actions = "\n".join(f"• {a.strip()}" for a in actions_raw.split('\n') if a.strip())
    else:
        actions = actions_raw

    lines = ["تقرير ميداني", SEP]
    lines.append(f"رقم الرحلة     : {d['flight_num']}")
    lines.append(f"التاريخ        : {d['date']}")
    lines.append(f"الناقل         : {d['carrier']}")
    lines.append(f"القادمة من     : {d['origin']}")
    if d.get('block_on','').strip():
        lines.append(f"Block On       : {d['block_on']}")
    lines.append(f"الموقف (Stand) : {d['stand']}")
    lines.append(f"نوع الطائرة   : {d['ac_type']}")
    lines.append(f"عدد الركاب    : {d['pax']} راكب")
    lines += [SEP,
              f"الموضوع:\n{d['subject']}", "",
              f"ملخص الحالة التشغيلية:\n{summary}", "",
              f"الإجراء المتخذ:\n{actions}", SEP]
    return "\n".join(lines)

def build_ops_report(d):
    default_details = ''
    default_actions = (
        "• تم تنفيذ عمليات نقل الركاب بشكل منتظم ودون تأخير.\n"
        "• تمت متابعة الرحلة ميدانياً حتى اكتمال الإجراءات التشغيلية."
    )
    default_final = (
        "تم تنفيذ وإدارة العمليات التشغيلية للرحلة بصورة مستقرة "
        "دون أي تأثير تشغيلي على الرحلة."
    )

    details = parse_val(d.get('details',''), default_details)
    actions_raw = parse_val(d.get('actions',''), default_actions)
    final = parse_val(d.get('final_status',''), default_final)

    if actions_raw != default_actions:
        actions = "\n".join(f"• {a.strip()}" for a in actions_raw.split('\n') if a.strip())
    else:
        actions = actions_raw

    lines = ["تقرير متابعة تشغيلية", SEP]
    lines.append(f"رقم الرحلة     : {d['flight_num']}")
    lines.append(f"التاريخ        : {d['date']}")
    lines.append(f"الناقل         : {d['carrier']}")
    lines.append(f"الوجهة         : {d['dest']}")
    if d.get('dep_time','').strip():
        lines.append(f"وقت المغادرة   : {d['dep_time']}")
    lines.append(f"الموقف (Stand) : {d['stand']}")
    lines += [SEP, f"الموضوع:\n{d['subject']}", ""]
    if details:
        lines += [f"التفاصيل:\n{details}", ""]
    lines += [f"الإجراءات:\n{actions}", "",
              f"الحالة النهائية:\n{final}", SEP]
    return "\n".join(lines)

AUTO_HINT = "\nأرسل ✅ للاحتفاظ بالنص الافتراضي، أو اكتب نصك:"

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data.clear()
    c.user_data['start_date'] = now_date()
    c.user_data['start_time'] = now_time()
    await u.message.reply_text(
        "✈️ مولّد التقارير الميدانية\n\n/cancel للإلغاء\n\nاختر نوع التقرير:\n1️⃣ تقرير ميداني\n2️⃣ تقرير متابعة تشغيلية",
        reply_markup=ReplyKeyboardMarkup(
            [["1️⃣ تقرير ميداني","2️⃣ تقرير متابعة تشغيلية"]],
            resize_keyboard=True, one_time_keyboard=True)
    )
    return REPORT_TYPE

async def report_type(u: Update, c: ContextTypes.DEFAULT_TYPE):
    t = u.message.text.strip()
    if "ميداني" in t or t in ("1","١"):
        c.user_data['type'] = 'field'
        await u.message.reply_text(
            "📋 *تقرير ميداني*\n\nرقم الرحلة؟\nمثال: SV1084",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return F_FLIGHT
    elif "تشغيلية" in t or t in ("2","٢"):
        c.user_data['type'] = 'ops'
        await u.message.reply_text(
            "📊 *تقرير متابعة تشغيلية*\n\nرقم الرحلة؟\nمثال: XY093",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return T_FLIGHT
    else:
        await u.message.reply_text("اكتب 1 أو 2 👆")
        return REPORT_TYPE

# ── تقرير ميداني ────────────────────────────────
async def f1(u,c):
    c.user_data['flight_num'] = u.message.text.strip()
    auto_date = c.user_data['start_date']
    await u.message.reply_text(
        f"📅 التاريخ؟\nأرسل ✅ للتاريخ التلقائي: *{auto_date}*\nأو اكتب تاريخاً آخر",
        parse_mode="Markdown")
    return F_DATE

async def f2(u,c):
    v = u.message.text.strip()
    c.user_data['date'] = c.user_data['start_date'] if v == '✅' else v
    await u.message.reply_text("🏢 الناقل؟\nمثال: Saudi Airlines")
    return F_CARRIER

async def f3(u,c):
    c.user_data['carrier'] = u.message.text.strip()
    await u.message.reply_text("🛫 القادمة من؟\nمثال: JED")
    return F_ORIGIN

async def f4(u,c):
    c.user_data['origin'] = u.message.text.strip()
    auto_time = c.user_data['start_time']
    await u.message.reply_text(
        f"⏱ وقت Block On؟\nأرسل ✅ للوقت التلقائي: *{auto_time}*\nأو اكتب وقتاً آخر\nأو اكتب *-* لتركه فارغاً",
        parse_mode="Markdown")
    return F_BLOCK_ON

async def f5(u,c):
    v = u.message.text.strip()
    if v == '✅':
        c.user_data['block_on'] = c.user_data['start_time']
    elif v == '-':
        c.user_data['block_on'] = ''
    else:
        c.user_data['block_on'] = v
    await u.message.reply_text("🅿️ الموقف Stand؟\nمثال: E25C")
    return F_STAND

async def f6(u,c):
    c.user_data['stand'] = u.message.text.strip()
    await u.message.reply_text("✈️ نوع الطائرة؟\nمثال: B777")
    return F_AC_TYPE

async def f7(u,c):
    c.user_data['ac_type'] = u.message.text.strip()
    await u.message.reply_text("👥 عدد الركاب PAX؟\nمثال: 353")
    return F_PAX

async def f8(u,c):
    c.user_data['pax'] = u.message.text.strip()
    await u.message.reply_text("🚌 عدد الباصات؟\nمثال: 7")
    return F_BUS_COUNT

async def f9(u,c):
    c.user_data['bus_count'] = u.message.text.strip()
    await u.message.reply_text("🚌 رقم الباص المتأخر؟\nأرسل *لا* إذا ما في تأخير", parse_mode="Markdown")
    return F_LATE_BUS

async def f10(u,c):
    c.user_data['late_bus'] = u.message.text.strip()
    if c.user_data['late_bus'] == 'لا':
        c.user_data['prev_bus'] = ''; c.user_data['delay_min'] = ''
        await u.message.reply_text("📝 الموضوع؟\nمثال: تأخر باص نقل الركاب الأخير")
        return F_SUBJECT
    await u.message.reply_text("🚌 الباص الذي غادر قبله؟\nمثال: SR146")
    return F_PREV_BUS

async def f11(u,c):
    c.user_data['prev_bus'] = u.message.text.strip()
    await u.message.reply_text("⏱ مدة التأخير بالدقائق؟\nمثال: 3")
    return F_DELAY_MIN

async def f12(u,c):
    c.user_data['delay_min'] = u.message.text.strip()
    await u.message.reply_text("📝 الموضوع؟\nمثال: تأخر باص نقل الركاب الأخير")
    return F_SUBJECT

async def f13(u,c):
    c.user_data['subject'] = u.message.text.strip()
    late = c.user_data.get('late_bus','')
    buses = c.user_data.get('bus_count','؟')
    default = (f"تمت متابعة الرحلة ميدانياً، وتم دعم الرحلة بـ {buses} باصات من قبل شركة SAAS. "
               f"كانت جميع الباصات جاهزة ووصلت في الوقت المطلوب" +
               (f"، باستثناء الباص رقم {late}..." if late and late != 'لا' else "."))
    await u.message.reply_text(
        f"📋 ملخص الحالة التشغيلية؟\nأرسل ✅ للنص الافتراضي أو اكتب ملخصك\n\n📌 _الافتراضي:_\n_{default}_",
        parse_mode="Markdown")
    return F_SUMMARY

async def f14(u,c):
    v = u.message.text.strip()
    c.user_data['summary'] = '' if v == '✅' else v
    late = c.user_data.get('late_bus','')
    default = "• تم توثيق الحالة ومتابعتها ميدانياً أثناء التشغيل."
    if late and late != 'لا':
        default += f"\n• سوف يتم رفع Inspection Report على شركة SAAS بسبب تأخر الباص رقم {late}."
    await u.message.reply_text(
        f"⚡️ الإجراءات المتخذة؟\nأرسل ✅ للافتراضية أو اكتب إجراءاتك\n\n📌 _الافتراضي:_\n_{default}_",
        parse_mode="Markdown")
    return F_ACTIONS

async def f15(u,c):
    v = u.message.text.strip()
    c.user_data['actions'] = '' if v == '✅' else v
    await u.message.reply_text(f"✅ التقرير جاهز:\n\n{build_field_report(c.user_data)}")
    await u.message.reply_text("🔄 أرسل /start لتقرير جديد")
    return ConversationHandler.END

# ── تقرير متابعة تشغيلية ────────────────────────
async def t1(u,c):
    c.user_data['flight_num'] = u.message.text.strip()
    auto_date = c.user_data['start_date']
    await u.message.reply_text(
        f"📅 التاريخ؟\nأرسل ✅ للتاريخ التلقائي: *{auto_date}*\nأو اكتب تاريخاً آخر",
        parse_mode="Markdown")
    return T_DATE

async def t2(u,c):
    v = u.message.text.strip()
    c.user_data['date'] = c.user_data['start_date'] if v == '✅' else v
    await u.message.reply_text("🏢 الناقل؟\nمثال: Flynas")
    return T_CARRIER

async def t3(u,c):
    c.user_data['carrier'] = u.message.text.strip()
    await u.message.reply_text("🛬 الوجهة؟\nمثال: MED")
    return T_DEST

async def t4(u,c):
    c.user_data['dest'] = u.message.text.strip()
    auto_time = c.user_data['start_time']
    await u.message.reply_text(
        f"⏱ وقت المغادرة الفعلي؟\nأرسل ✅ للوقت التلقائي: *{auto_time}*\nأو اكتب وقتاً آخر\nأو اكتب *-* لتركه فارغاً",
        parse_mode="Markdown")
    return T_DEP_TIME

async def t5(u,c):
    v = u.message.text.strip()
    if v == '✅':
        c.user_data['dep_time'] = c.user_data['start_time']
    elif v == '-':
        c.user_data['dep_time'] = ''
    else:
        c.user_data['dep_time'] = v
    await u.message.reply_text("🅿️ الموقف Stand؟\nمثال: E34L")
    return T_STAND

async def t6(u,c):
    c.user_data['stand'] = u.message.text.strip()
    await u.message.reply_text("📝 الموضوع؟\nمثال: متابعة عمليات Turnaround")
    return T_SUBJECT

async def t7(u,c):
    c.user_data['subject'] = u.message.text.strip()
    await u.message.reply_text(
        "📋 التفاصيل؟\nاكتب ما تمت ملاحظته، أو اكتب *-* لتركه فارغاً",
        parse_mode="Markdown")
    return T_DETAILS

async def t8(u,c):
    v = u.message.text.strip()
    c.user_data['details'] = '' if v == '-' else v
    default = ("• تم تنفيذ عمليات نقل الركاب بشكل منتظم ودون تأخير.\n"
               "• تمت متابعة الرحلة ميدانياً حتى اكتمال الإجراءات التشغيلية.")
    await u.message.reply_text(
        f"⚡️ الإجراءات؟\nأرسل ✅ للافتراضية أو اكتب إجراءاتك\n\n📌 _الافتراضي:_\n_{default}_",
        parse_mode="Markdown")
    return T_ACTIONS

async def t9(u,c):
    v = u.message.text.strip()
    c.user_data['actions'] = '' if v == '✅' else v
    default = ("تم تنفيذ وإدارة العمليات التشغيلية للرحلة بصورة مستقرة "
               "دون أي تأثير تشغيلي على الرحلة.")
    await u.message.reply_text(
        f"🏁 الحالة النهائية؟\nأرسل ✅ للافتراضية أو اكتبها\n\n📌 _الافتراضي:_\n_{default}_",
        parse_mode="Markdown")
    return T_FINAL_STATUS

async def t10(u,c):
    v = u.message.text.strip()
    c.user_data['final_status'] = '' if v == '✅' else v
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
            REPORT_TYPE:[MessageHandler(T,report_type)],
            F_FLIGHT:[MessageHandler(T,f1)], F_DATE:[MessageHandler(T,f2)],
            F_CARRIER:[MessageHandler(T,f3)], F_ORIGIN:[MessageHandler(T,f4)],
            F_BLOCK_ON:[MessageHandler(T,f5)], F_STAND:[MessageHandler(T,f6)],
            F_AC_TYPE:[MessageHandler(T,f7)], F_PAX:[MessageHandler(T,f8)],
            F_BUS_COUNT:[MessageHandler(T,f9)], F_LATE_BUS:[MessageHandler(T,f10)],
            F_PREV_BUS:[MessageHandler(T,f11)], F_DELAY_MIN:[MessageHandler(T,f12)],
            F_SUBJECT:[MessageHandler(T,f13)], F_SUMMARY:[MessageHandler(T,f14)],
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
