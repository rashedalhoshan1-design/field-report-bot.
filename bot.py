import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
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

def kb(*options):
    return ReplyKeyboardMarkup([[o] for o in options], resize_keyboard=True, one_time_keyboard=True)

def kb_row(*options):
    return ReplyKeyboardMarkup([list(options)], resize_keyboard=True, one_time_keyboard=True)

SEP = "─" * 32

def build_field_report(d):
    late = d.get('late_bus','').strip()

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

    default_actions = "• تم توثيق الحالة ومتابعتها ميدانياً أثناء التشغيل."
    if late and late != 'لا':
        default_actions += f"\n• سوف يتم رفع Inspection Report على شركة SAAS بسبب تأخر الباص رقم {late}."

    summary = d.get('summary') or default_summary
    actions_raw = d.get('actions') or default_actions
    if actions_raw != default_actions:
        actions = "\n".join(f"• {a.strip()}" for a in actions_raw.split('\n') if a.strip())
    else:
        actions = actions_raw

    lines = ["تقرير ميداني", SEP,
             f"رقم الرحلة     : {d['flight_num']}",
             f"التاريخ        : {d['date']}",
             f"الناقل         : {d['carrier']}",
             f"القادمة من     : {d['origin']}"]
    if d.get('block_on','').strip():
        lines.append(f"Block On       : {d['block_on']}")
    lines += [f"الموقف (Stand) : {d['stand']}",
              f"نوع الطائرة   : {d['ac_type']}",
              f"عدد الركاب    : {d['pax']} راكب",
              SEP,
              f"الموضوع:\n{d['subject']}", "",
              f"ملخص الحالة التشغيلية:\n{summary}", "",
              f"الإجراء المتخذ:\n{actions}", SEP]
    return "\n".join(lines)

def build_ops_report(d):
    default_actions = (
        "• تم تنفيذ عمليات نقل الركاب بشكل منتظم ودون تأخير.\n"
        "• تمت متابعة الرحلة ميدانياً حتى اكتمال الإجراءات التشغيلية."
    )
    default_final = (
        "تم تنفيذ وإدارة العمليات التشغيلية للرحلة بصورة مستقرة "
        "دون أي تأثير تشغيلي على الرحلة."
    )

    details = d.get('details','')
    actions_raw = d.get('actions') or default_actions
    final = d.get('final_status') or default_final

    if actions_raw != default_actions:
        actions = "\n".join(f"• {a.strip()}" for a in actions_raw.split('\n') if a.strip())
    else:
        actions = actions_raw

    lines = ["تقرير متابعة تشغيلية", SEP,
             f"رقم الرحلة     : {d['flight_num']}",
             f"التاريخ        : {d['date']}",
             f"الناقل         : {d['carrier']}",
             f"الوجهة         : {d['dest']}"]
    if d.get('dep_time','').strip():
        lines.append(f"وقت المغادرة   : {d['dep_time']}")
    lines += [f"الموقف (Stand) : {d['stand']}", SEP,
              f"الموضوع:\n{d['subject']}", ""]
    if details:
        lines += [f"التفاصيل:\n{details}", ""]
    lines += [f"الإجراءات:\n{actions}", "",
              f"الحالة النهائية:\n{final}", SEP]
    return "\n".join(lines)

# ── start ───────────────────────────────────────
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data.clear()
    c.user_data['start_date'] = now_date()
    c.user_data['start_time'] = now_time()
    await u.message.reply_text(
        "✈️ مولّد التقارير الميدانية\n\n/cancel للإلغاء\n\nاختر نوع التقرير:",
        reply_markup=kb_row("تقرير ميداني", "تقرير متابعة تشغيلية"))
    return REPORT_TYPE

async def report_type(u: Update, c: ContextTypes.DEFAULT_TYPE):
    t = u.message.text.strip()
    if "ميداني" in t or t == "1":
        c.user_data['type'] = 'field'
        await u.message.reply_text("رقم الرحلة؟\nمثال: SV1084", reply_markup=ReplyKeyboardRemove())
        return F_FLIGHT
    elif "تشغيلية" in t or t == "2":
        c.user_data['type'] = 'ops'
        await u.message.reply_text("رقم الرحلة؟\nمثال: XY093", reply_markup=ReplyKeyboardRemove())
        return T_FLIGHT
    else:
        await u.message.reply_text("اختر من الأزرار 👆")
        return REPORT_TYPE

# ── تقرير ميداني ────────────────────────────────
async def f1(u,c):
    c.user_data['flight_num'] = u.message.text.strip()
    auto = c.user_data['start_date']
    await u.message.reply_text(
        f"التاريخ؟\nالتلقائي: {auto}",
        reply_markup=kb(auto, "أدخل تاريخاً آخر"))
    return F_DATE

async def f2(u,c):
    v = u.message.text.strip()
    c.user_data['date'] = v if v != "أدخل تاريخاً آخر" else ""
    if v == "أدخل تاريخاً آخر":
        await u.message.reply_text("اكتب التاريخ:\nمثال: 30/05/2026", reply_markup=ReplyKeyboardRemove())
        return F_DATE
    await u.message.reply_text("الناقل؟\nمثال: Saudi Airlines", reply_markup=ReplyKeyboardRemove())
    return F_CARRIER

async def f3(u,c):
    if not c.user_data.get('date'):
        c.user_data['date'] = u.message.text.strip()
        await u.message.reply_text("الناقل؟\nمثال: Saudi Airlines")
        return F_CARRIER
    c.user_data['carrier'] = u.message.text.strip()
    await u.message.reply_text("القادمة من؟\nمثال: JED")
    return F_ORIGIN

async def f4(u,c):
    c.user_data['carrier'] = c.user_data.get('carrier') or u.message.text.strip()
    if not c.user_data.get('carrier'):
        c.user_data['carrier'] = u.message.text.strip()
    await u.message.reply_text("القادمة من؟\nمثال: JED")
    return F_ORIGIN

# أعيد كتابة الـ handlers بشكل أوضح
async def f_carrier(u,c):
    c.user_data['carrier'] = u.message.text.strip()
    await u.message.reply_text("القادمة من؟\nمثال: JED")
    return F_ORIGIN

async def f_origin(u,c):
    c.user_data['origin'] = u.message.text.strip()
    auto = c.user_data['start_time']
    await u.message.reply_text(
        f"وقت Block On؟\nالتلقائي: {auto}",
        reply_markup=kb(auto, "أدخل وقتاً آخر", "بدون وقت"))
    return F_BLOCK_ON

async def f_block_on(u,c):
    v = u.message.text.strip()
    if v == "بدون وقت":
        c.user_data['block_on'] = ''
    elif v == "أدخل وقتاً آخر":
        await u.message.reply_text("اكتب الوقت:\nمثال: 21:50", reply_markup=ReplyKeyboardRemove())
        return F_BLOCK_ON
    else:
        c.user_data['block_on'] = v
    await u.message.reply_text("الموقف Stand؟\nمثال: E25C", reply_markup=ReplyKeyboardRemove())
    return F_STAND

async def f_stand(u,c):
    if not c.user_data.get('block_on') and u.message.text.strip() not in ["بدون وقت","أدخل وقتاً آخر"]:
        # المستخدم كتب الوقت يدوياً
        pass
    c.user_data['stand'] = u.message.text.strip()
    await u.message.reply_text("نوع الطائرة؟\nمثال: B777")
    return F_AC_TYPE

async def f_ac(u,c):
    c.user_data['ac_type'] = u.message.text.strip()
    await u.message.reply_text("عدد الركاب PAX؟\nمثال: 353")
    return F_PAX

async def f_pax(u,c):
    c.user_data['pax'] = u.message.text.strip()
    await u.message.reply_text("عدد الباصات؟\nمثال: 7")
    return F_BUS_COUNT

async def f_bus(u,c):
    c.user_data['bus_count'] = u.message.text.strip()
    await u.message.reply_text("هل في باص متأخر؟", reply_markup=kb_row("نعم", "لا"))
    return F_LATE_BUS

async def f_late(u,c):
    v = u.message.text.strip()
    if v == "لا":
        c.user_data['late_bus'] = 'لا'
        c.user_data['prev_bus'] = ''
        c.user_data['delay_min'] = ''
        await u.message.reply_text("الموضوع؟\nمثال: تأخر باص نقل الركاب الأخير", reply_markup=ReplyKeyboardRemove())
        return F_SUBJECT
    await u.message.reply_text("رقم الباص المتأخر؟\nمثال: SR113", reply_markup=ReplyKeyboardRemove())
    return F_LATE_BUS

async def f_late2(u,c):
    if not c.user_data.get('late_bus') or c.user_data['late_bus'] == 'لا':
        c.user_data['late_bus'] = u.message.text.strip()
        await u.message.reply_text("الباص الذي غادر قبله؟\nمثال: SR146")
        return F_PREV_BUS
    c.user_data['late_bus'] = u.message.text.strip()
    await u.message.reply_text("الباص الذي غادر قبله؟\nمثال: SR146")
    return F_PREV_BUS

async def f_prev(u,c):
    c.user_data['prev_bus'] = u.message.text.strip()
    await u.message.reply_text("مدة التأخير بالدقائق؟\nمثال: 3")
    return F_DELAY_MIN

async def f_delay(u,c):
    c.user_data['delay_min'] = u.message.text.strip()
    await u.message.reply_text("الموضوع؟\nمثال: تأخر باص نقل الركاب الأخير")
    return F_SUBJECT

async def f_subject(u,c):
    c.user_data['subject'] = u.message.text.strip()
    late = c.user_data.get('late_bus','')
    buses = c.user_data.get('bus_count','؟')
    default_preview = (f"تمت متابعة الرحلة ميدانياً، وتم دعم الرحلة بـ {buses} باصات...")
    await u.message.reply_text(
        f"ملخص الحالة التشغيلية؟\n\n📌 الافتراضي:\n{default_preview}",
        reply_markup=kb("استخدم الافتراضي", "اكتب ملخصاً مختلفاً"))
    return F_SUMMARY

async def f_summary(u,c):
    v = u.message.text.strip()
    if v == "استخدم الافتراضي":
        c.user_data['summary'] = ''
        late = c.user_data.get('late_bus','')
        default_actions = "• تم توثيق الحالة ومتابعتها ميدانياً أثناء التشغيل."
        if late and late != 'لا':
            default_actions += f"\n• سوف يتم رفع Inspection Report على شركة SAAS بسبب تأخر الباص رقم {late}."
        await u.message.reply_text(
            f"الإجراءات المتخذة؟\n\n📌 الافتراضي:\n{default_actions}",
            reply_markup=kb("استخدم الافتراضي", "اكتب إجراءات مختلفة"))
        return F_ACTIONS
    elif v == "اكتب ملخصاً مختلفاً":
        await u.message.reply_text("اكتب الملخص:", reply_markup=ReplyKeyboardRemove())
        return F_SUMMARY
    else:
        c.user_data['summary'] = v
        late = c.user_data.get('late_bus','')
        default_actions = "• تم توثيق الحالة ومتابعتها ميدانياً أثناء التشغيل."
        if late and late != 'لا':
            default_actions += f"\n• سوف يتم رفع Inspection Report على شركة SAAS بسبب تأخر الباص رقم {late}."
        await u.message.reply_text(
            f"الإجراءات المتخذة؟\n\n📌 الافتراضي:\n{default_actions}",
            reply_markup=kb("استخدم الافتراضي", "اكتب إجراءات مختلفة"))
        return F_ACTIONS

async def f_actions(u,c):
    v = u.message.text.strip()
    if v == "استخدم الافتراضي":
        c.user_data['actions'] = ''
    elif v == "اكتب إجراءات مختلفة":
        await u.message.reply_text("اكتب الإجراءات (كل إجراء في سطر):", reply_markup=ReplyKeyboardRemove())
        return F_ACTIONS
    else:
        c.user_data['actions'] = v
    await u.message.reply_text(
        f"✅ التقرير جاهز:\n\n{build_field_report(c.user_data)}",
        reply_markup=ReplyKeyboardRemove())
    await u.message.reply_text("🔄 أرسل /start لتقرير جديد")
    return ConversationHandler.END

# ── تقرير متابعة تشغيلية ────────────────────────
async def t1(u,c):
    c.user_data['flight_num'] = u.message.text.strip()
    auto = c.user_data['start_date']
    await u.message.reply_text(f"التاريخ؟\nالتلقائي: {auto}",
        reply_markup=kb(auto, "أدخل تاريخاً آخر"))
    return T_DATE

async def t2(u,c):
    v = u.message.text.strip()
    if v == "أدخل تاريخاً آخر":
        await u.message.reply_text("اكتب التاريخ:\nمثال: 31/05/2026", reply_markup=ReplyKeyboardRemove())
        return T_DATE
    c.user_data['date'] = v
    await u.message.reply_text("الناقل؟\nمثال: Flynas", reply_markup=ReplyKeyboardRemove())
    return T_CARRIER

async def t3(u,c):
    c.user_data['carrier'] = u.message.text.strip()
    await u.message.reply_text("الوجهة؟\nمثال: MED")
    return T_DEST

async def t4(u,c):
    c.user_data['dest'] = u.message.text.strip()
    auto = c.user_data['start_time']
    await u.message.reply_text(f"وقت المغادرة الفعلي؟\nالتلقائي: {auto}",
        reply_markup=kb(auto, "أدخل وقتاً آخر", "بدون وقت"))
    return T_DEP_TIME

async def t5(u,c):
    v = u.message.text.strip()
    if v == "بدون وقت":
        c.user_data['dep_time'] = ''
    elif v == "أدخل وقتاً آخر":
        await u.message.reply_text("اكتب الوقت:\nمثال: 08:10", reply_markup=ReplyKeyboardRemove())
        return T_DEP_TIME
    else:
        c.user_data['dep_time'] = v
    await u.message.reply_text("الموقف Stand؟\nمثال: E34L", reply_markup=ReplyKeyboardRemove())
    return T_STAND

async def t6(u,c):
    c.user_data['stand'] = u.message.text.strip()
    await u.message.reply_text("الموضوع؟\nمثال: متابعة عمليات Turnaround")
    return T_SUBJECT

async def t7(u,c):
    c.user_data['subject'] = u.message.text.strip()
    await u.message.reply_text("التفاصيل؟\nاكتب ما تمت ملاحظته",
        reply_markup=kb("بدون تفاصيل", "اكتب التفاصيل"))
    return T_DETAILS

async def t8(u,c):
    v = u.message.text.strip()
    if v == "بدون تفاصيل":
        c.user_data['details'] = ''
    elif v == "اكتب التفاصيل":
        await u.message.reply_text("اكتب التفاصيل:", reply_markup=ReplyKeyboardRemove())
        return T_DETAILS
    else:
        c.user_data['details'] = v
    default = ("• تم تنفيذ عمليات نقل الركاب بشكل منتظم ودون تأخير.\n"
               "• تمت متابعة الرحلة ميدانياً حتى اكتمال الإجراءات التشغيلية.")
    await u.message.reply_text(
        f"الإجراءات؟\n\n📌 الافتراضي:\n{default}",
        reply_markup=kb("استخدم الافتراضي", "اكتب إجراءات مختلفة"))
    return T_ACTIONS

async def t9(u,c):
    v = u.message.text.strip()
    if v == "استخدم الافتراضي":
        c.user_data['actions'] = ''
    elif v == "اكتب إجراءات مختلفة":
        await u.message.reply_text("اكتب الإجراءات:", reply_markup=ReplyKeyboardRemove())
        return T_ACTIONS
    else:
        c.user_data['actions'] = v
    default = ("تم تنفيذ وإدارة العمليات التشغيلية للرحلة بصورة مستقرة "
               "دون أي تأثير تشغيلي على الرحلة.")
    await u.message.reply_text(
        f"الحالة النهائية؟\n\n📌 الافتراضي:\n{default}",
        reply_markup=kb("استخدم الافتراضي", "اكتب حالة مختلفة"))
    return T_FINAL_STATUS

async def t10(u,c):
    v = u.message.text.strip()
    if v == "استخدم الافتراضي":
        c.user_data['final_status'] = ''
    elif v == "اكتب حالة مختلفة":
        await u.message.reply_text("اكتب الحالة النهائية:", reply_markup=ReplyKeyboardRemove())
        return T_FINAL_STATUS
    else:
        c.user_data['final_status'] = v
    await u.message.reply_text(
        f"✅ التقرير جاهز:\n\n{build_ops_report(c.user_data)}",
        reply_markup=ReplyKeyboardRemove())
    await u.message.reply_text("🔄 أرسل /start لتقرير جديد")
    return ConversationHandler.END

async def cancel(u,c):
    await u.message.reply_text("❌ تم الإلغاء. /start للبدء", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    T = filters.TEXT & ~filters.COMMAND
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REPORT_TYPE:[MessageHandler(T,report_type)],
            F_FLIGHT:[MessageHandler(T,f1)],
            F_DATE:[MessageHandler(T,f2)],
            F_CARRIER:[MessageHandler(T,f_carrier)],
            F_ORIGIN:[MessageHandler(T,f_origin)],
            F_BLOCK_ON:[MessageHandler(T,f_block_on)],
            F_STAND:[MessageHandler(T,f_stand)],
            F_AC_TYPE:[MessageHandler(T,f_ac)],
            F_PAX:[MessageHandler(T,f_pax)],
            F_BUS_COUNT:[MessageHandler(T,f_bus)],
            F_LATE_BUS:[MessageHandler(T,f_late), MessageHandler(T,f_late2)],
            F_PREV_BUS:[MessageHandler(T,f_prev)],
            F_DELAY_MIN:[MessageHandler(T,f_delay)],
            F_SUBJECT:[MessageHandler(T,f_subject)],
            F_SUMMARY:[MessageHandler(T,f_summary)],
            F_ACTIONS:[MessageHandler(T,f_actions)],
            T_FLIGHT:[MessageHandler(T,t1)],
            T_DATE:[MessageHandler(T,t2)],
            T_CARRIER:[MessageHandler(T,t3)],
            T_DEST:[MessageHandler(T,t4)],
            T_DEP_TIME:[MessageHandler(T,t5)],
            T_STAND:[MessageHandler(T,t6)],
            T_SUBJECT:[MessageHandler(T,t7)],
            T_DETAILS:[MessageHandler(T,t8)],
            T_ACTIONS:[MessageHandler(T,t9)],
            T_FINAL_STATUS:[MessageHandler(T,t10)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
