#!/usr/bin/env python3
"""
TreidingSB - Generator raport SAPTAMANAL SMC (multilingv: ro, en, ru, uk, pl)
"""

import os, sys, json, re, requests
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("EROARE: variabila ANTHROPIC_API_KEY nu este setata.")
    sys.exit(1)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-sonnet-4-6"

# Limbile in care se genereaza raportul. "ro" este limba sursa (folosita pentru
# analiza AI initiala); celelalte sunt obtinute printr-o singura trecere de
# traducere per limba, ca sa nu multiplicam numarul de apeluri catre model.
LANGS = ["ro", "en", "ru", "uk", "pl"]
LANG_NAMES_FOR_PROMPT = {"en": "English", "ru": "Russian (Русский)", "uk": "Ukrainian (Українська)", "pl": "Polish (Polski)"}

PIATA = {
    "EURUSD":  {"pret": "1.1426", "var": "+0.0002 (+0.02%) ▲"},
    "GBPUSD":  {"pret": "1.3264", "var": "+0.0012 (+0.09%) ▲"},
    "XAUUSD":  {"pret": "4,018.89", "var": "+2.23 (+0.06%) ▲"},
    "XAGUSD":  {"pret": "59.2275", "var": "+0.9340 (+1.60%) ▲"},
    "DXY":     {"pret": "101.14",  "var": "+0.01 (+0.01%) ▲"},
    "FED":     {"pret": "3.75%",   "var": "Urmatoarea sedinta: 29 iulie"},
    "BCE":     {"pret": "2.40%",   "var": "Urmatoarea sedinta: 23 iulie"},
    "BOE":     {"pret": "3.75%",   "var": "Urmatoarea sedinta: 30 iulie"},
    "US10Y":   {"pret": "4.452%",  "var": "+0.075 (+1.71%) ▲"},
}

# "tip" e o cheie (nu text), tradusa la construirea PDF-ului prin LABELS[lang]["tip_instrument"]
INSTRUMENTE = [
    {"simbol": "XAU/USD", "pret": PIATA["XAUUSD"]["pret"], "tip": "metal"},
    {"simbol": "XAG/USD", "pret": PIATA["XAGUSD"]["pret"], "tip": "metal"},
    {"simbol": "EUR/USD", "pret": PIATA["EURUSD"]["pret"], "tip": "forex"},
    {"simbol": "GBP/USD", "pret": PIATA["GBPUSD"]["pret"], "tip": "forex"},
]

NOW   = datetime.now(timezone.utc)
TODAY = NOW.date()

LUNI_RO = {1:"Ianuarie",2:"Februarie",3:"Martie",4:"Aprilie",5:"Mai",6:"Iunie",7:"Iulie",8:"August",9:"Septembrie",10:"Octombrie",11:"Noiembrie",12:"Decembrie"}
ZILE_RO = {0:"Luni",1:"Marti",2:"Miercuri",3:"Joi",4:"Vineri",5:"Sambata",6:"Duminica"}

MONTHS = {
    "ro": LUNI_RO,
    "en": {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"},
    "ru": {1:"Января",2:"Февраля",3:"Марта",4:"Апреля",5:"Мая",6:"Июня",7:"Июля",8:"Августа",9:"Сентября",10:"Октября",11:"Ноября",12:"Декабря"},
    "uk": {1:"Січня",2:"Лютого",3:"Березня",4:"Квітня",5:"Травня",6:"Червня",7:"Липня",8:"Серпня",9:"Вересня",10:"Жовтня",11:"Листопада",12:"Грудня"},
    "pl": {1:"Stycznia",2:"Lutego",3:"Marca",4:"Kwietnia",5:"Maja",6:"Czerwca",7:"Lipca",8:"Sierpnia",9:"Września",10:"Października",11:"Listopada",12:"Grudnia"},
}
DAYS = {
    "ro": ZILE_RO,
    "en": {0:"Monday",1:"Tuesday",2:"Wednesday",3:"Thursday",4:"Friday",5:"Saturday",6:"Sunday"},
    "ru": {0:"Понедельник",1:"Вторник",2:"Среда",3:"Четверг",4:"Пятница",5:"Суббота",6:"Воскресенье"},
    "uk": {0:"Понеділок",1:"Вівторок",2:"Середа",3:"Четвер",4:"П'ятниця",5:"Субота",6:"Неділя"},
    "pl": {0:"Poniedziałek",1:"Wtorek",2:"Środa",3:"Czwartek",4:"Piątek",5:"Sobota",6:"Niedziela"},
}

DAYS_SINCE_MON  = TODAY.weekday()
MONDAY_CURENT   = TODAY - timedelta(days=DAYS_SINCE_MON)
MONDAY_URMATOR  = MONDAY_CURENT + timedelta(days=7)

M = MONDAY_CURENT.month
if M in [1,2,3]:   QUARTER = "Q1"
elif M in [4,5,6]: QUARTER = "Q2"
elif M in [7,8,9]: QUARTER = "Q3"
else:              QUARTER = "Q4"

QUARTER_YEAR = MONDAY_CURENT.year
SAPTAMANA_NR = MONDAY_CURENT.isocalendar()[1]
IS_MID_WEEK  = TODAY.weekday() > 1

def data_localizata(d, lang):
    return f"{d.strftime('%d')} {MONTHS[lang][d.month]} {d.year}"

OUTPUT_DIR = Path(__file__).parent.parent / "reports" / f"{QUARTER}_{QUARTER_YEAR}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

C_AURIU = HexColor("#F5A623")
C_NAVY  = HexColor("#0D1B33")
C_BLUE  = HexColor("#2563EB")
C_TEXT  = HexColor("#1A2B4A")
C_GRI   = HexColor("#64748B")
C_VERDE = HexColor("#00A862")
C_ROSU  = HexColor("#E5484D")
C_AMBER = HexColor("#F59E0B")
C_BG    = HexColor("#F8FAFC")

# ===================== Etichete statice per limba (fara apel API) =====================
LABELS = {
    "ro": {
        "title": "TreidingSB — Raport Saptamanal", "week_word": "Saptamana", "valid_word": "Valabil",
        "note_label": "Nota", "note_body": "Raportul din {date} ramane activ. Urmatoarea actualizare: <b>{next_date}</b>.",
        "important_label": "Important", "important_body": "Acest raport se va modifica in functie de noutatile economice si fundamentale aparute in cursul saptamanii. Acesti factori sunt cei care misca activele in acest moment.",
        "preturi_ref": "PRETURI DE REFERINTA", "col_instrument": "Instrument", "col_pret": "Pret", "col_variatie": "Variatie",
        "rata_fed": "Rata Fed", "rata_bce": "Rata BCE", "rata_boe": "Rata BoE",
        "context_macro": "CONTEXT MACROECONOMIC",
        "macro_titles": {"DXY":"DXY","FED":"Fed","BCE/BOE":"BCE / BoE","US10Y":"US10Y","GEOPOLITIC":"Geopolitic"},
        "calendar_title": "CALENDAR ECONOMIC — {d1} / {d2} {qy}",
        "col_ziua": "Ziua", "col_ora": "Ora", "col_tara": "Tara", "col_eveniment": "Eveniment", "col_impact": "Impact XAU",
        "impact_labels": {"BULLISH_XAU":"BULLISH XAU","BEARISH_XAU":"BEARISH XAU","NEUTRU":"NEUTRU"},
        "analiza_tehnica": "ANALIZA TEHNICA SMC — FACTORI SI SCENARII",
        "tip_metal": "Metal pretios", "tip_forex": "Forex major",
        "factori_titles": {"FACTORI_PRINCIPALI":"Factori principali","TREND_ACTUAL":"Trend actual","SCENARIUL_BULLISH":"Scenariu Bullish","SCENARIUL_BEARISH":"Scenariu Bearish","NIVELE_CHEIE":"Nivele cheie","CAND_SE_ACTUALIZEAZA":"Cand se actualizeaza"},
        "smc_titles": {"SENTIMENT_GENERAL":"Sentiment general","STRUCTURA_PIATA":"Structura de piata","ZONE_CHEIE":"Zone cheie (OB/FVG)","LICHIDITATE":"Lichiditate","SCENARIU_PRINCIPAL":"Scenariu principal","SCENARIU_ALTERNATIV":"Scenariu alternativ"},
        "atentie": "Atentie", "disclaimer": "Raport cu scop exclusiv educativ. Nu constituie consiliere financiara. Tranzactionarea implica riscuri semnificative.",
        "generat": "Generat",
    },
    "en": {
        "title": "TreidingSB — Weekly Report", "week_word": "Week", "valid_word": "Valid",
        "note_label": "Note", "note_body": "The report from {date} remains active. Next update: <b>{next_date}</b>.",
        "important_label": "Important", "important_body": "This report will be updated based on economic and fundamental news released during the week. These are the factors currently moving the assets.",
        "preturi_ref": "REFERENCE PRICES", "col_instrument": "Instrument", "col_pret": "Price", "col_variatie": "Change",
        "rata_fed": "Fed Rate", "rata_bce": "ECB Rate", "rata_boe": "BoE Rate",
        "context_macro": "MACRO CONTEXT",
        "macro_titles": {"DXY":"DXY","FED":"Fed","BCE/BOE":"ECB / BoE","US10Y":"US10Y","GEOPOLITIC":"Geopolitical"},
        "calendar_title": "ECONOMIC CALENDAR — {d1} / {d2} {qy}",
        "col_ziua": "Day", "col_ora": "Time", "col_tara": "Country", "col_eveniment": "Event", "col_impact": "XAU Impact",
        "impact_labels": {"BULLISH_XAU":"BULLISH XAU","BEARISH_XAU":"BEARISH XAU","NEUTRU":"NEUTRAL"},
        "analiza_tehnica": "SMC TECHNICAL ANALYSIS — FACTORS AND SCENARIOS",
        "tip_metal": "Precious metal", "tip_forex": "Major forex pair",
        "factori_titles": {"FACTORI_PRINCIPALI":"Key factors","TREND_ACTUAL":"Current trend","SCENARIUL_BULLISH":"Bullish scenario","SCENARIUL_BEARISH":"Bearish scenario","NIVELE_CHEIE":"Key levels","CAND_SE_ACTUALIZEAZA":"When this updates"},
        "smc_titles": {"SENTIMENT_GENERAL":"General sentiment","STRUCTURA_PIATA":"Market structure","ZONE_CHEIE":"Key zones (OB/FVG)","LICHIDITATE":"Liquidity","SCENARIU_PRINCIPAL":"Main scenario","SCENARIU_ALTERNATIV":"Alternative scenario"},
        "atentie": "Attention", "disclaimer": "Report for educational purposes only. Not financial advice. Trading involves significant risk.",
        "generat": "Generated",
    },
    "ru": {
        "title": "TreidingSB — Еженедельный отчёт", "week_word": "Неделя", "valid_word": "Действует",
        "note_label": "Примечание", "note_body": "Отчёт от {date} остаётся в силе. Следующее обновление: <b>{next_date}</b>.",
        "important_label": "Важно", "important_body": "Этот отчёт будет обновляться с учётом экономических и фундаментальных новостей в течение недели. Именно эти факторы сейчас двигают активы.",
        "preturi_ref": "СПРАВОЧНЫЕ ЦЕНЫ", "col_instrument": "Инструмент", "col_pret": "Цена", "col_variatie": "Изменение",
        "rata_fed": "Ставка ФРС", "rata_bce": "Ставка ЕЦБ", "rata_boe": "Ставка Банка Англии",
        "context_macro": "МАКРОЭКОНОМИЧЕСКИЙ КОНТЕКСТ",
        "macro_titles": {"DXY":"DXY","FED":"ФРС","BCE/BOE":"ЕЦБ / Банк Англии","US10Y":"US10Y","GEOPOLITIC":"Геополитика"},
        "calendar_title": "ЭКОНОМИЧЕСКИЙ КАЛЕНДАРЬ — {d1} / {d2} {qy}",
        "col_ziua": "День", "col_ora": "Время", "col_tara": "Страна", "col_eveniment": "Событие", "col_impact": "Влияние на XAU",
        "impact_labels": {"BULLISH_XAU":"БЫЧИЙ XAU","BEARISH_XAU":"МЕДВЕЖИЙ XAU","NEUTRU":"НЕЙТРАЛЬНО"},
        "analiza_tehnica": "ТЕХНИЧЕСКИЙ АНАЛИЗ SMC — ФАКТОРЫ И СЦЕНАРИИ",
        "tip_metal": "Драгоценный металл", "tip_forex": "Основная валютная пара",
        "factori_titles": {"FACTORI_PRINCIPALI":"Ключевые факторы","TREND_ACTUAL":"Текущий тренд","SCENARIUL_BULLISH":"Бычий сценарий","SCENARIUL_BEARISH":"Медвежий сценарий","NIVELE_CHEIE":"Ключевые уровни","CAND_SE_ACTUALIZEAZA":"Когда обновится"},
        "smc_titles": {"SENTIMENT_GENERAL":"Общее настроение","STRUCTURA_PIATA":"Структура рынка","ZONE_CHEIE":"Ключевые зоны (OB/FVG)","LICHIDITATE":"Ликвидность","SCENARIU_PRINCIPAL":"Основной сценарий","SCENARIU_ALTERNATIV":"Альтернативный сценарий"},
        "atentie": "Внимание", "disclaimer": "Отчёт носит исключительно образовательный характер. Не является финансовой рекомендацией. Торговля сопряжена со значительными рисками.",
        "generat": "Создано",
    },
    "uk": {
        "title": "TreidingSB — Щотижневий звіт", "week_word": "Тиждень", "valid_word": "Дійсний",
        "note_label": "Примітка", "note_body": "Звіт від {date} залишається чинним. Наступне оновлення: <b>{next_date}</b>.",
        "important_label": "Важливо", "important_body": "Цей звіт буде оновлюватися з урахуванням економічних і фундаментальних новин протягом тижня. Саме ці фактори зараз рухають активи.",
        "preturi_ref": "ДОВІДКОВІ ЦІНИ", "col_instrument": "Інструмент", "col_pret": "Ціна", "col_variatie": "Зміна",
        "rata_fed": "Ставка ФРС", "rata_bce": "Ставка ЄЦБ", "rata_boe": "Ставка Банку Англії",
        "context_macro": "МАКРОЕКОНОМІЧНИЙ КОНТЕКСТ",
        "macro_titles": {"DXY":"DXY","FED":"ФРС","BCE/BOE":"ЄЦБ / Банк Англії","US10Y":"US10Y","GEOPOLITIC":"Геополітика"},
        "calendar_title": "ЕКОНОМІЧНИЙ КАЛЕНДАР — {d1} / {d2} {qy}",
        "col_ziua": "День", "col_ora": "Час", "col_tara": "Країна", "col_eveniment": "Подія", "col_impact": "Вплив на XAU",
        "impact_labels": {"BULLISH_XAU":"БИЧАЧИЙ XAU","BEARISH_XAU":"ВЕДМЕЖИЙ XAU","NEUTRU":"НЕЙТРАЛЬНО"},
        "analiza_tehnica": "ТЕХНІЧНИЙ АНАЛІЗ SMC — ФАКТОРИ ТА СЦЕНАРІЇ",
        "tip_metal": "Дорогоцінний метал", "tip_forex": "Основна валютна пара",
        "factori_titles": {"FACTORI_PRINCIPALI":"Ключові фактори","TREND_ACTUAL":"Поточний тренд","SCENARIUL_BULLISH":"Бичачий сценарій","SCENARIUL_BEARISH":"Ведмежий сценарій","NIVELE_CHEIE":"Ключові рівні","CAND_SE_ACTUALIZEAZA":"Коли оновиться"},
        "smc_titles": {"SENTIMENT_GENERAL":"Загальний настрій","STRUCTURA_PIATA":"Структура ринку","ZONE_CHEIE":"Ключові зони (OB/FVG)","LICHIDITATE":"Ліквідність","SCENARIU_PRINCIPAL":"Основний сценарій","SCENARIU_ALTERNATIV":"Альтернативний сценарій"},
        "atentie": "Увага", "disclaimer": "Звіт має виключно освітній характер. Не є фінансовою порадою. Торгівля пов'язана зі значними ризиками.",
        "generat": "Створено",
    },
    "pl": {
        "title": "TreidingSB — Raport tygodniowy", "week_word": "Tydzień", "valid_word": "Ważny",
        "note_label": "Uwaga", "note_body": "Raport z {date} pozostaje aktywny. Następna aktualizacja: <b>{next_date}</b>.",
        "important_label": "Ważne", "important_body": "Ten raport będzie aktualizowany na podstawie wiadomości ekonomicznych i fundamentalnych publikowanych w ciągu tygodnia. To właśnie te czynniki obecnie poruszają aktywami.",
        "preturi_ref": "CENY REFERENCYJNE", "col_instrument": "Instrument", "col_pret": "Cena", "col_variatie": "Zmiana",
        "rata_fed": "Stopa Fed", "rata_bce": "Stopa EBC", "rata_boe": "Stopa BoE",
        "context_macro": "KONTEKST MAKROEKONOMICZNY",
        "macro_titles": {"DXY":"DXY","FED":"Fed","BCE/BOE":"EBC / BoE","US10Y":"US10Y","GEOPOLITIC":"Geopolityka"},
        "calendar_title": "KALENDARZ EKONOMICZNY — {d1} / {d2} {qy}",
        "col_ziua": "Dzień", "col_ora": "Godzina", "col_tara": "Kraj", "col_eveniment": "Wydarzenie", "col_impact": "Wpływ na XAU",
        "impact_labels": {"BULLISH_XAU":"BYCZY XAU","BEARISH_XAU":"NIEDŹWIEDZI XAU","NEUTRU":"NEUTRALNY"},
        "analiza_tehnica": "ANALIZA TECHNICZNA SMC — CZYNNIKI I SCENARIUSZE",
        "tip_metal": "Metal szlachetny", "tip_forex": "Główna para walutowa",
        "factori_titles": {"FACTORI_PRINCIPALI":"Kluczowe czynniki","TREND_ACTUAL":"Aktualny trend","SCENARIUL_BULLISH":"Scenariusz byczy","SCENARIUL_BEARISH":"Scenariusz niedźwiedzi","NIVELE_CHEIE":"Kluczowe poziomy","CAND_SE_ACTUALIZEAZA":"Kiedy nastąpi aktualizacja"},
        "smc_titles": {"SENTIMENT_GENERAL":"Ogólny sentyment","STRUCTURA_PIATA":"Struktura rynku","ZONE_CHEIE":"Kluczowe strefy (OB/FVG)","LICHIDITATE":"Płynność","SCENARIU_PRINCIPAL":"Główny scenariusz","SCENARIU_ALTERNATIV":"Scenariusz alternatywny"},
        "atentie": "Uwaga", "disclaimer": "Raport ma charakter wyłącznie edukacyjny. Nie stanowi porady finansowej. Handel wiąże się ze znacznym ryzykiem.",
        "generat": "Wygenerowano",
    },
}

def stiluri():
    base = getSampleStyleSheet()
    return {
        "TitluRaport": ParagraphStyle("TitluRaport", parent=base["Title"], fontName="Helvetica-Bold", fontSize=19, textColor=C_NAVY, spaceAfter=4, alignment=TA_LEFT),
        "SubtitluRaport": ParagraphStyle("SubtitluRaport", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, textColor=C_GRI, spaceAfter=14),
        "SectiuneMare": ParagraphStyle("SectiuneMare", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=12, textColor=C_NAVY, spaceBefore=6, spaceAfter=8, letterSpacing=0.6),
        "InstrumentTitlu": ParagraphStyle("InstrumentTitlu", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=14, textColor=C_NAVY, spaceBefore=4, spaceAfter=2),
        "InstrumentSub": ParagraphStyle("InstrumentSub", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=9, textColor=C_GRI, spaceAfter=8),
        "SectiuneTitlu": ParagraphStyle("SectiuneTitlu", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=9.5, textColor=C_BLUE, spaceBefore=8, spaceAfter=3, letterSpacing=0.4),
        "SectiuneText": ParagraphStyle("SectiuneText", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, textColor=C_TEXT, leading=14, alignment=TA_JUSTIFY, spaceAfter=4),
        "TabelLabel": ParagraphStyle("TabelLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, textColor=C_NAVY, leading=12),
        "TabelText": ParagraphStyle("TabelText", parent=base["Normal"], fontName="Helvetica", fontSize=8.5, textColor=C_TEXT, leading=12),
        "NotitaViolet": ParagraphStyle("NotitaViolet", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=9, textColor=HexColor("#6D28D9"), leading=13),
        "NotitaGalben": ParagraphStyle("NotitaGalben", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=9, textColor=HexColor("#92400E"), leading=13),
        "PretCurent": ParagraphStyle("PretCurent", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10, textColor=C_VERDE, leading=13),
        "Disclaimer": ParagraphStyle("Disclaimer", parent=base["Normal"], fontName="Helvetica", fontSize=7.5, textColor=C_GRI, leading=11),
        "Footer": ParagraphStyle("Footer", parent=base["Normal"], fontName="Helvetica", fontSize=8, textColor=C_GRI),
    }

def apeleaza_claude(prompt, max_tokens=1800):
    headers = {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {"model": ANTHROPIC_MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(ANTHROPIC_API_URL, headers=headers, json=body, timeout=90)
    r.raise_for_status()
    return "\n".join(b["text"] for b in r.json()["content"] if b["type"] == "text").strip()

def prompt_macro():
    return f"""Esti un analist macroeconomic senior pentru TreidingSB.
Raport saptamanal: {data_localizata(MONDAY_CURENT,'ro')} (Saptamana {SAPTAMANA_NR}, {QUARTER} {QUARTER_YEAR})
Date reale: DXY {PIATA['DXY']['pret']}, EUR/USD {PIATA['EURUSD']['pret']}, GBP/USD {PIATA['GBPUSD']['pret']}, XAU/USD {PIATA['XAUUSD']['pret']}, XAG/USD {PIATA['XAGUSD']['pret']}, Fed {PIATA['FED']['pret']} ({PIATA['FED']['var']}), BCE {PIATA['BCE']['pret']} ({PIATA['BCE']['var']}), BoE {PIATA['BOE']['pret']} ({PIATA['BOE']['var']}), US10Y {PIATA['US10Y']['pret']}.
Scrie contextul macro pe 5 categorii (titlu: text, fara markdown):
DXY: (analiza {PIATA['DXY']['pret']}, directie, impact)
FED: (rata {PIATA['FED']['pret']}, {PIATA['FED']['var']})
BCE/BOE: (BCE {PIATA['BCE']['pret']} {PIATA['BCE']['var']}; BoE {PIATA['BOE']['pret']} {PIATA['BOE']['var']})
US10Y: (randament {PIATA['US10Y']['pret']}, {PIATA['US10Y']['var']}, corelatie aur)
GEOPOLITIC: (context relevant aceasta saptamana)
Fii dens si factual. Text simplu fara markdown."""

def prompt_calendar_saptamana():
    zile = [f"{ZILE_RO[i]} {(MONDAY_CURENT + timedelta(days=i)).strftime('%d')} {LUNI_RO[(MONDAY_CURENT + timedelta(days=i)).month]}" for i in range(5)]
    return f"""Scrie calendarul economic pentru saptamana {data_localizata(MONDAY_CURENT,'ro')}.
Sedinte: Fed {PIATA['FED']['var']}, BCE {PIATA['BCE']['var']}, BoE {PIATA['BOE']['var']}.
Genereaza 6-10 evenimente. Format: ZIUA | ORA_UTC | TARA | EVENIMENT | IMPACT_XAU
IMPACT_XAU = BULLISH_XAU / BEARISH_XAU / NEUTRU
Doar liniile in acest format, fara alt text."""

def prompt_factori(instrument):
    return f"""Analist SMC TreidingSB. Instrument: {instrument['simbol']} la {instrument['pret']}.
Context: DXY {PIATA['DXY']['pret']}, Fed {PIATA['FED']['pret']}, US10Y {PIATA['US10Y']['pret']}.
Scrie pe sectiuni (titlu: text, fara markdown):
FACTORI_PRINCIPALI: (3-4 factori care misca {instrument['simbol']} aceasta saptamana)
TREND_ACTUAL: (directia la {instrument['pret']})
SCENARIUL_BULLISH: (conditii crestere cu niveluri concrete)
SCENARIUL_BEARISH: (conditii scadere cu niveluri concrete)
NIVELE_CHEIE: (suporturi si rezistente la {instrument['pret']})
CAND_SE_ACTUALIZEAZA: (ce date/evenimente ar schimba scenariul aceasta saptamana)"""

def prompt_smc(instrument):
    return f"""Analiza SMC {instrument['simbol']} la {instrument['pret']} - saptamana {data_localizata(MONDAY_CURENT,'ro')}.
Scrie pe sectiuni (titlu: text, fara markdown):
SENTIMENT_GENERAL: (Bullish/Bearish/Neutru la {instrument['pret']})
STRUCTURA_PIATA: (BOS/CHoCH pe H4/D1)
ZONE_CHEIE: (2-3 OB sau FVG cu niveluri)
LICHIDITATE: (EQH/EQL, stop-hunt-uri)
SCENARIU_PRINCIPAL: (intrare, SL, TP cu niveluri, probabilitate %)
SCENARIU_ALTERNATIV: (ce invalideaza scenariul)"""

SECTIUNI_MACRO   = ["DXY","FED","BCE/BOE","US10Y","GEOPOLITIC"]
SECTIUNI_FACTORI = ["FACTORI_PRINCIPALI","TREND_ACTUAL","SCENARIUL_BULLISH","SCENARIUL_BEARISH","NIVELE_CHEIE","CAND_SE_ACTUALIZEAZA"]
SECTIUNI_SMC     = ["SENTIMENT_GENERAL","STRUCTURA_PIATA","ZONE_CHEIE","LICHIDITATE","SCENARIU_PRINCIPAL","SCENARIU_ALTERNATIV"]

def parseaza(text, sectiuni):
    result, key, lines = {}, None, []
    for line in text.split("\n"):
        ls = line.strip()
        matched = None
        for t in sectiuni:
            if ls.upper().startswith(t + ":") or ls.upper().startswith(t.replace("_"," ") + ":"):
                matched = t; break
        if matched:
            if key: result[key] = " ".join(lines).strip()
            key = matched
            rest = ls.split(":", 1)
            lines = [rest[1].strip()] if len(rest) > 1 and rest[1].strip() else []
        elif key:
            lines.append(ls)
    if key: result[key] = " ".join(lines).strip()
    return result

def parseaza_calendar(text):
    eventi = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if "|" not in line: continue
        p = [x.strip() for x in line.split("|")]
        if len(p) >= 5:
            eventi.append({"ziua":p[0],"ora":p[1],"tara":p[2],"eveniment":p[3],"impact":p[4].upper()})
    return eventi

# ===================== Traducere continut AI (o singura trecere per limba) =====================
def _strip_json_fence(text):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n", "", t)
        t = re.sub(r"\n```$", "", t)
    return t.strip()

def traduce_pachet(ctx, cal, a_factori, a_smc, lang):
    """O singura cerere catre Claude care traduce tot continutul analitic
    (macro + calendar + factori + SMC per instrument) intr-o limba tinta,
    pastrand exact structura JSON astfel incat sa poata fi refolosita direct
    in construieste_pdf(). Pastreaza cifrele/tichetele neschimbate."""
    lang_name = LANG_NAMES_FOR_PROMPT[lang]
    payload = {
        "macro": ctx,
        "calendar": cal,
        "instrumente": {
            sim: {"factori": a_factori.get(sim, {}), "smc": a_smc.get(sim, {})}
            for sim in [i["simbol"] for i in INSTRUMENTE]
        }
    }
    prompt = f"""Traduce in {lang_name} continutul JSON de mai jos, pastrat de un raport financiar saptamanal.
Reguli stricte:
- Pastreaza EXACT aceeasi structura JSON (aceleasi chei, acelasi numar de elemente in liste).
- In obiectele din lista "calendar", tradu DOAR campurile "ziua", "tara" si "eveniment". Campurile "ora" si "impact" trebuie copiate exact, neschimbate.
- Tradu doar valorile text (analiza financiara). Nu traduce cifre, procente, tichete (XAU/USD, DXY, Fed, BCE, BoE, US10Y etc.), niveluri de pret sau simboluri.
- Foloseste un ton profesionist, potrivit pentru traderi, in limba {lang_name}.
- Raspunde STRICT cu JSON valid, fara markdown, fara text explicativ, fara ```.

JSON de tradus:
{json.dumps(payload, ensure_ascii=False)}"""

    raw = apeleaza_claude(prompt, max_tokens=4000)
    cleaned = _strip_json_fence(raw)
    data = json.loads(cleaned)

    t_ctx = data.get("macro", ctx)
    t_cal = data.get("calendar", cal)
    t_factori, t_smc = {}, {}
    instr_data = data.get("instrumente", {})
    for sim in [i["simbol"] for i in INSTRUMENTE]:
        entry = instr_data.get(sim, {})
        t_factori[sim] = entry.get("factori", a_factori.get(sim, {}))
        t_smc[sim] = entry.get("smc", a_smc.get(sim, {}))
    return t_ctx, t_cal, t_factori, t_smc

def nota_box(text, stil_text, bg, border_color, story):
    box = [[Paragraph(text, stil_text)]]
    t = Table(box, colWidths=[162*mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),1,border_color),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story.append(t)
    story.append(Spacer(1, 8))

def construieste_pdf(lang, context_macro, calendar, analize_factori, analize_smc):
    L = LABELS[lang]
    date_raport    = data_localizata(MONDAY_CURENT, lang)
    date_urmatoare = data_localizata(MONDAY_URMATOR, lang)
    ziua_curenta   = DAYS[lang][TODAY.weekday()]
    report_file = f"raport-{MONDAY_CURENT.strftime('%Y-%m-%d')}-{lang}.pdf"
    output_path = OUTPUT_DIR / report_file
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, topMargin=18*mm, bottomMargin=16*mm, leftMargin=18*mm, rightMargin=18*mm)
    S = stiluri()
    story = []

    story.append(Paragraph(f"{L['title']} {date_raport}", S["TitluRaport"]))
    story.append(Paragraph(f"{L['week_word']} {SAPTAMANA_NR} &middot; {QUARTER} {QUARTER_YEAR} &middot; {L['valid_word']}: {date_raport} &rarr; {date_urmatoare} &middot; XAU | XAG | EUR/USD | GBP/USD", S["SubtitluRaport"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_AURIU, spaceAfter=10))

    if IS_MID_WEEK:
        body = L["note_body"].format(date=date_raport, next_date=date_urmatoare)
        nota_box(f"<b>{L['note_label']} ({ziua_curenta}):</b> {body}", S["NotitaViolet"], HexColor("#F5F3FF"), HexColor("#7C3AED"), story)

    nota_box(f"<b>{L['important_label']}:</b> {L['important_body']}", S["NotitaGalben"], HexColor("#FFFBEB"), C_AMBER, story)

    story.append(Paragraph(L["preturi_ref"], S["SectiuneMare"]))
    pret_data = [[Paragraph(f"<b>{L['col_instrument']}</b>",S["TabelLabel"]),Paragraph(f"<b>{L['col_pret']}</b>",S["TabelLabel"]),Paragraph(f"<b>{L['col_variatie']}</b>",S["TabelLabel"])]]
    randuri_pret = [("EURUSD","EUR/USD"),("GBPUSD","GBP/USD"),("XAUUSD","XAU/USD"),("XAGUSD","XAG/USD"),("DXY","DXY"),("US10Y","US10Y"),("FED",L["rata_fed"]),("BCE",L["rata_bce"]),("BOE",L["rata_boe"])]
    for sym, lbl in randuri_pret:
        d = PIATA[sym]
        pret_data.append([Paragraph(lbl,S["TabelText"]),Paragraph(d["pret"],S["PretCurent"] if sym in ["EURUSD","GBPUSD","XAUUSD","XAGUSD"] else S["TabelText"]),Paragraph(d["var"],S["TabelText"])])
    tbl_p = Table(pret_data, colWidths=[46*mm,52*mm,64*mm])
    tbl_p.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_NAVY),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),("ROWBACKGROUNDS",(0,1),(-1,-1),[HexColor("#FFFFFF"),C_BG]),("GRID",(0,0),(-1,-1),0.5,HexColor("#E5EBF2")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
    story.append(tbl_p)
    story.append(Spacer(1,12))

    if context_macro:
        story.append(Paragraph(L["context_macro"], S["SectiuneMare"]))
        titluri_m = L["macro_titles"]
        macro_rows = [[Paragraph(f"<b>{titluri_m.get(k,k)}</b>",S["TabelLabel"]),Paragraph(context_macro.get(k,"—"),S["TabelText"])] for k in SECTIUNI_MACRO if context_macro.get(k)]
        if macro_rows:
            tbl_m = Table(macro_rows, colWidths=[24*mm,138*mm])
            tbl_m.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.5,HexColor("#E5EBF2")),("BACKGROUND",(0,0),(0,-1),C_BG),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
            story.append(tbl_m)
        story.append(Spacer(1,12))

    if calendar:
        sapt_end = MONDAY_CURENT + timedelta(days=4)
        story.append(Paragraph(L["calendar_title"].format(d1=date_raport, d2=f"{sapt_end.strftime('%d')} {MONTHS[lang][sapt_end.month]}", qy=QUARTER_YEAR), S["SectiuneMare"]))
        culori = {"BULLISH_XAU":C_VERDE,"BEARISH_XAU":C_ROSU,"NEUTRU":C_AMBER}
        etichete = L["impact_labels"]
        cal_rows = [[Paragraph(f"<b>{L['col_ziua']}</b>",S["TabelLabel"]),Paragraph(f"<b>{L['col_ora']}</b>",S["TabelLabel"]),Paragraph(f"<b>{L['col_tara']}</b>",S["TabelLabel"]),Paragraph(f"<b>{L['col_eveniment']}</b>",S["TabelLabel"]),Paragraph(f"<b>{L['col_impact']}</b>",S["TabelLabel"])]]
        for ev in calendar:
            c = culori.get(ev.get("impact"),C_AMBER)
            lbl = etichete.get(ev.get("impact"),ev.get("impact",""))
            cal_rows.append([Paragraph(ev.get("ziua",""),S["TabelText"]),Paragraph(ev.get("ora",""),S["TabelText"]),Paragraph(ev.get("tara",""),S["TabelText"]),Paragraph(ev.get("eveniment",""),S["TabelText"]),Paragraph(f'<font color="{c.hexval()}"><b>{lbl}</b></font>',S["TabelText"])])
        tbl_c = Table(cal_rows, colWidths=[20*mm,22*mm,16*mm,80*mm,24*mm])
        tbl_c.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_NAVY),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),("ROWBACKGROUNDS",(0,1),(-1,-1),[HexColor("#FFFFFF"),C_BG]),("GRID",(0,0),(-1,-1),0.5,HexColor("#E5EBF2")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
        story.append(tbl_c)
        story.append(Spacer(1,5))

    story.append(PageBreak())
    story.append(Paragraph(L["analiza_tehnica"], S["SectiuneMare"]))
    story.append(Spacer(1,6))

    tip_labels = {"metal": L["tip_metal"], "forex": L["tip_forex"]}
    for instr in INSTRUMENTE:
        sim = instr["simbol"]
        factori = analize_factori.get(sim, {})
        smc = analize_smc.get(sim, {})
        bloc = []
        bloc.append(Paragraph(f"{sim} &mdash; {instr['pret']}", S["InstrumentTitlu"]))
        bloc.append(Paragraph(tip_labels.get(instr["tip"], instr["tip"]), S["InstrumentSub"]))
        for k, titlu in L["factori_titles"].items():
            txt = factori.get(k)
            if not txt: continue
            bloc.append(Paragraph(titlu.upper(), S["SectiuneTitlu"]))
            if k == "CAND_SE_ACTUALIZEAZA":
                b = [[Paragraph(f"<b>{L['atentie']}:</b> {txt}", S["NotitaGalben"])]]
                t = Table(b, colWidths=[162*mm])
                t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),HexColor("#FFF7ED")),("BOX",(0,0),(-1,-1),1,C_AMBER),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
                bloc.append(t)
            else:
                bloc.append(Paragraph(txt, S["SectiuneText"]))
        for k, titlu in L["smc_titles"].items():
            txt = smc.get(k)
            if txt:
                bloc.append(Paragraph(titlu.upper(), S["SectiuneTitlu"]))
                bloc.append(Paragraph(txt, S["SectiuneText"]))
        bloc.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#E5EBF2"), spaceBefore=8, spaceAfter=12))
        story.append(KeepTogether(bloc))

    story.append(Spacer(1,8))
    story.append(HRFlowable(width="100%", thickness=1, color=C_NAVY, spaceAfter=8))
    story.append(Paragraph(f"<b>{L['disclaimer'].split('.')[0]}.</b> {'.'.join(L['disclaimer'].split('.')[1:]).strip()}", S["Disclaimer"]))
    story.append(Paragraph(f"TreidingSB &middot; {QUARTER} {QUARTER_YEAR} &middot; {L['week_word']} {SAPTAMANA_NR} &middot; treidingsb.vercel.app &middot; {L['generat']}: {data_localizata(TODAY, lang)}", S["Footer"]))

    doc.build(story)
    print(f"  PDF ({lang}): {output_path}")
    return output_path, report_file

def actualizeaza_index(fisiere_per_limba):
    def update_json(path, intrare, key):
        if path.exists():
            with open(path) as f: data = json.load(f)
        else:
            data = {key: []}
        data[key] = [r for r in data[key] if r.get("data") != intrare["data"]]
        data[key].insert(0, intrare)
        data[key] = data[key][:52]
        with open(path,"w",encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    intrare = {
        "data": MONDAY_CURENT.strftime("%Y-%m-%d"),
        "data_afisare": data_localizata(MONDAY_CURENT, "ro"),
        "data_urmatoare": data_localizata(MONDAY_URMATOR, "ro"),
        "saptamana": SAPTAMANA_NR,
        "quarter": QUARTER,
        "year": QUARTER_YEAR,
        "fisiere": {lang: f"{QUARTER}_{QUARTER_YEAR}/{fname}" for lang, fname in fisiere_per_limba.items()},
        "instrumente": [i["simbol"] for i in INSTRUMENTE],
        "preturi": {k: v["pret"] for k, v in PIATA.items()},
    }
    update_json(Path(__file__).parent.parent/"reports"/"index.json", intrare, "rapoarte")
    update_json(OUTPUT_DIR/"index.json", intrare, "rapoarte")
    print(f"  Index actualizat: {QUARTER} {QUARTER_YEAR} / Saptamana {SAPTAMANA_NR}")

def main():
    print(f"=== TreidingSB Raport Saptamanal (multilingv) ===")
    print(f"    Data raport: {data_localizata(MONDAY_CURENT,'ro')} (Saptamana {SAPTAMANA_NR})")
    print(f"    Trimestru: {QUARTER} {QUARTER_YEAR}")

    print("1/5 Continut sursa (RO) - context macro...")
    ctx_ro = parseaza(apeleaza_claude(prompt_macro()), SECTIUNI_MACRO)

    print("2/5 Continut sursa (RO) - calendar saptamana...")
    cal_ro = parseaza_calendar(apeleaza_claude(prompt_calendar_saptamana()))
    print(f"    {len(cal_ro)} evenimente")

    print("3/5 Continut sursa (RO) - analiza per instrument...")
    factori_ro, smc_ro = {}, {}
    for instr in INSTRUMENTE:
        print(f"    {instr['simbol']}...")
        factori_ro[instr["simbol"]] = parseaza(apeleaza_claude(prompt_factori(instr)), SECTIUNI_FACTORI)
        smc_ro[instr["simbol"]] = parseaza(apeleaza_claude(prompt_smc(instr)), SECTIUNI_SMC)

    continut_per_limba = {"ro": (ctx_ro, cal_ro, factori_ro, smc_ro)}

    print("4/5 Traducere continut in celelalte limbi...")
    for lang in LANGS:
        if lang == "ro":
            continue
        try:
            print(f"    -> {lang}...")
            continut_per_limba[lang] = traduce_pachet(ctx_ro, cal_ro, factori_ro, smc_ro, lang)
        except Exception as e:
            print(f"    EROARE traducere {lang}: {e} -- folosesc continutul RO ca rezerva")
            continut_per_limba[lang] = (ctx_ro, cal_ro, factori_ro, smc_ro)

    print("5/5 Construire PDF-uri + index...")
    fisiere_per_limba = {}
    for lang in LANGS:
        ctx, cal, factori, smc = continut_per_limba[lang]
        _, fname = construieste_pdf(lang, ctx, cal, factori, smc)
        fisiere_per_limba[lang] = fname
    actualizeaza_index(fisiere_per_limba)

    print(f"=== Finalizat: {len(fisiere_per_limba)} rapoarte generate ===")

if __name__ == "__main__":
    main()
