#!/usr/bin/env python3
"""
TreidingSB - Generator raport SAPTAMANAL SMC
"""

import os, sys, json, requests
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

INSTRUMENTE = [
    {"simbol": "XAU/USD", "pret": PIATA["XAUUSD"]["pret"], "tip": "Metal pretios"},
    {"simbol": "XAG/USD", "pret": PIATA["XAGUSD"]["pret"], "tip": "Metal pretios"},
    {"simbol": "EUR/USD", "pret": PIATA["EURUSD"]["pret"], "tip": "Forex major"},
    {"simbol": "GBP/USD", "pret": PIATA["GBPUSD"]["pret"], "tip": "Forex major"},
]

NOW   = datetime.now(timezone.utc)
TODAY = NOW.date()
YEAR  = TODAY.year
MONTH = TODAY.month

LUNI_RO = {
    1:"Ianuarie",2:"Februarie",3:"Martie",4:"Aprilie",
    5:"Mai",6:"Iunie",7:"Iulie",8:"August",
    9:"Septembrie",10:"Octombrie",11:"Noiembrie",12:"Decembrie"
}
ZILE_RO = {0:"Luni",1:"Marti",2:"Miercuri",3:"Joi",4:"Vineri",5:"Sambata",6:"Duminica"}

DAYS_SINCE_MON  = TODAY.weekday()
MONDAY_CURENT   = TODAY - timedelta(days=DAYS_SINCE_MON)
MONDAY_URMATOR  = MONDAY_CURENT + timedelta(days=7)

M = MONDAY_CURENT.month
if M in [1,2,3]:   QUARTER = "Q1"
elif M in [4,5,6]: QUARTER = "Q2"
elif M in [7,8,9]: QUARTER = "Q3"
else:              QUARTER = "Q4"

QUARTER_YEAR = MONDAY_CURENT.year
DATE_RAPORT    = MONDAY_CURENT.strftime("%d") + " " + LUNI_RO[MONDAY_CURENT.month] + " " + str(MONDAY_CURENT.year)
DATE_URMATOARE = MONDAY_URMATOR.strftime("%d") + " " + LUNI_RO[MONDAY_URMATOR.month] + " " + str(MONDAY_URMATOR.year)
SAPTAMANA_NR   = MONDAY_CURENT.isocalendar()[1]
IS_MID_WEEK = TODAY.weekday() > 1
ZIUA_CURENTA = ZILE_RO[TODAY.weekday()]

OUTPUT_DIR = Path(__file__).parent.parent / "reports" / f"{QUARTER}_{QUARTER_YEAR}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = f"raport-{MONDAY_CURENT.strftime('%Y-%m-%d')}.pdf"

C_AURIU = HexColor("#F5A623")
C_NAVY  = HexColor("#0D1B33")
C_BLUE  = HexColor("#2563EB")
C_TEXT  = HexColor("#1A2B4A")
C_GRI   = HexColor("#64748B")
C_VERDE = HexColor("#00A862")
C_ROSU  = HexColor("#E5484D")
C_AMBER = HexColor("#F59E0B")
C_BG    = HexColor("#F8FAFC")

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
Raport saptamanal: {DATE_RAPORT} (Saptamana {SAPTAMANA_NR}, {QUARTER} {QUARTER_YEAR})
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
    return f"""Scrie calendarul economic pentru saptamana {DATE_RAPORT}.
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
    return f"""Analiza SMC {instrument['simbol']} la {instrument['pret']} - saptamana {DATE_RAPORT}.
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

def nota_box(text, stil_text, bg, border_color, story):
    box = [[Paragraph(text, stil_text)]]
    t = Table(box, colWidths=[162*mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),1,border_color),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story.append(t)
    story.append(Spacer(1, 8))

def construieste_pdf(context_macro, calendar, analize_factori, analize_smc):
    output_path = OUTPUT_DIR / REPORT_FILE
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, topMargin=18*mm, bottomMargin=16*mm, leftMargin=18*mm, rightMargin=18*mm)
    S = stiluri()
    story = []

    story.append(Paragraph(f"TreidingSB &mdash; Raport Saptamanal {DATE_RAPORT}", S["TitluRaport"]))
    story.append(Paragraph(f"Saptamana {SAPTAMANA_NR} &middot; {QUARTER} {QUARTER_YEAR} &middot; Valabil: {DATE_RAPORT} &rarr; {DATE_URMATOARE} &middot; XAU | XAG | EUR/USD | GBP/USD", S["SubtitluRaport"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_AURIU, spaceAfter=10))

    if IS_MID_WEEK:
        nota_box(f"<b>Nota ({ZIUA_CURENTA}):</b> Raportul din {DATE_RAPORT} ramane activ. Urmatoarea actualizare: <b>{DATE_URMATOARE}</b>.", S["NotitaViolet"], HexColor("#F5F3FF"), HexColor("#7C3AED"), story)

    nota_box("<b>Important:</b> Acest raport se va modifica in functie de noutatile economice si fundamentale aparute in cursul saptamanii. Acesti factori sunt cei care misca activele in acest moment.", S["NotitaGalben"], HexColor("#FFFBEB"), C_AMBER, story)

    story.append(Paragraph("PRETURI DE REFERINTA", S["SectiuneMare"]))
    pret_data = [[Paragraph("<b>Instrument</b>",S["TabelLabel"]),Paragraph("<b>Pret</b>",S["TabelLabel"]),Paragraph("<b>Variatie</b>",S["TabelLabel"])]]
    for sym, lbl in [("EURUSD","EUR/USD"),("GBPUSD","GBP/USD"),("XAUUSD","XAU/USD"),("XAGUSD","XAG/USD"),("DXY","DXY"),("US10Y","US10Y"),("FED","Rata Fed"),("BCE","Rata BCE"),("BOE","Rata BoE")]:
        d = PIATA[sym]
        pret_data.append([Paragraph(lbl,S["TabelText"]),Paragraph(d["pret"],S["PretCurent"] if sym in ["EURUSD","GBPUSD","XAUUSD","XAGUSD"] else S["TabelText"]),Paragraph(d["var"],S["TabelText"])])
    tbl_p = Table(pret_data, colWidths=[46*mm,52*mm,64*mm])
    tbl_p.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_NAVY),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),("ROWBACKGROUNDS",(0,1),(-1,-1),[HexColor("#FFFFFF"),C_BG]),("GRID",(0,0),(-1,-1),0.5,HexColor("#E5EBF2")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
    story.append(tbl_p)
    story.append(Spacer(1,12))

    if context_macro:
        story.append(Paragraph("CONTEXT MACROECONOMIC", S["SectiuneMare"]))
        titluri_m = {"DXY":"DXY","FED":"Fed","BCE/BOE":"BCE / BoE","US10Y":"US10Y","GEOPOLITIC":"Geopolitic"}
        macro_rows = [[Paragraph(f"<b>{titluri_m.get(k,k)}</b>",S["TabelLabel"]),Paragraph(context_macro.get(k,"—"),S["TabelText"])] for k in SECTIUNI_MACRO if context_macro.get(k)]
        if macro_rows:
            tbl_m = Table(macro_rows, colWidths=[24*mm,138*mm])
            tbl_m.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.5,HexColor("#E5EBF2")),("BACKGROUND",(0,0),(0,-1),C_BG),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
            story.append(tbl_m)
        story.append(Spacer(1,12))

    if calendar:
        sapt_end = MONDAY_CURENT + timedelta(days=4)
        story.append(Paragraph(f"CALENDAR ECONOMIC &mdash; {DATE_RAPORT} / {sapt_end.strftime('%d')} {LUNI_RO[sapt_end.month]} {QUARTER_YEAR}", S["SectiuneMare"]))
        culori = {"BULLISH_XAU":C_VERDE,"BEARISH_XAU":C_ROSU,"NEUTRU":C_AMBER}
        etichete = {"BULLISH_XAU":"BULLISH XAU","BEARISH_XAU":"BEARISH XAU","NEUTRU":"NEUTRU"}
        cal_rows = [[Paragraph("<b>Ziua</b>",S["TabelLabel"]),Paragraph("<b>Ora</b>",S["TabelLabel"]),Paragraph("<b>Tara</b>",S["TabelLabel"]),Paragraph("<b>Eveniment</b>",S["TabelLabel"]),Paragraph("<b>Impact XAU</b>",S["TabelLabel"])]]
        for ev in calendar:
            c = culori.get(ev["impact"],C_AMBER)
            lbl = etichete.get(ev["impact"],ev["impact"])
            cal_rows.append([Paragraph(ev["ziua"],S["TabelText"]),Paragraph(ev["ora"],S["TabelText"]),Paragraph(ev["tara"],S["TabelText"]),Paragraph(ev["eveniment"],S["TabelText"]),Paragraph(f'<font color="{c.hexval()}"><b>{lbl}</b></font>',S["TabelText"])])
        tbl_c = Table(cal_rows, colWidths=[20*mm,22*mm,16*mm,80*mm,24*mm])
        tbl_c.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_NAVY),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),("ROWBACKGROUNDS",(0,1),(-1,-1),[HexColor("#FFFFFF"),C_BG]),("GRID",(0,0),(-1,-1),0.5,HexColor("#E5EBF2")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
        story.append(tbl_c)
        story.append(Spacer(1,5))

    story.append(PageBreak())
    story.append(Paragraph("ANALIZA TEHNICA SMC &mdash; FACTORI SI SCENARII", S["SectiuneMare"]))
    story.append(Spacer(1,6))

    for instr in INSTRUMENTE:
        sim = instr["simbol"]
        factori = analize_factori.get(sim, {})
        smc = analize_smc.get(sim, {})
        bloc = []
        bloc.append(Paragraph(f"{sim} &mdash; {instr['pret']}", S["InstrumentTitlu"]))
        bloc.append(Paragraph(instr["tip"], S["InstrumentSub"]))
        for k, titlu in {"FACTORI_PRINCIPALI":"Factori principali","TREND_ACTUAL":"Trend actual","SCENARIUL_BULLISH":"Scenariu Bullish","SCENARIUL_BEARISH":"Scenariu Bearish","NIVELE_CHEIE":"Nivele cheie","CAND_SE_ACTUALIZEAZA":"Cand se actualizeaza"}.items():
            txt = factori.get(k)
            if not txt: continue
            bloc.append(Paragraph(titlu.upper(), S["SectiuneTitlu"]))
            if k == "CAND_SE_ACTUALIZEAZA":
                b = [[Paragraph(f"<b>Atentie:</b> {txt}", S["NotitaGalben"])]]
                t = Table(b, colWidths=[162*mm])
                t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),HexColor("#FFF7ED")),("BOX",(0,0),(-1,-1),1,C_AMBER),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
                bloc.append(t)
            else:
                bloc.append(Paragraph(txt, S["SectiuneText"]))
        for k, titlu in {"SENTIMENT_GENERAL":"Sentiment general","STRUCTURA_PIATA":"Structura de piata","ZONE_CHEIE":"Zone cheie (OB/FVG)","LICHIDITATE":"Lichiditate","SCENARIU_PRINCIPAL":"Scenariu principal","SCENARIU_ALTERNATIV":"Scenariu alternativ"}.items():
            txt = smc.get(k)
            if txt:
                bloc.append(Paragraph(titlu.upper(), S["SectiuneTitlu"]))
                bloc.append(Paragraph(txt, S["SectiuneText"]))
        bloc.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#E5EBF2"), spaceBefore=8, spaceAfter=12))
        story.append(KeepTogether(bloc))

    story.append(Spacer(1,8))
    story.append(HRFlowable(width="100%", thickness=1, color=C_NAVY, spaceAfter=8))
    story.append(Paragraph("<b>Disclaimer:</b> Raport cu scop exclusiv educativ. Nu constituie consiliere financiara. Tranzactionarea implica riscuri semnificative.", S["Disclaimer"]))
    story.append(Paragraph(f"TreidingSB &middot; {QUARTER} {QUARTER_YEAR} &middot; Saptamana {SAPTAMANA_NR} &middot; treidingsb.vercel.app &middot; Generat: {TODAY.strftime('%d')} {LUNI_RO[TODAY.month]} {YEAR}", S["Footer"]))

    doc.build(story)
    print(f"  PDF: {output_path}")
    return output_path

def actualizeaza_index(output_path):
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
        "data_afisare": DATE_RAPORT,
        "data_urmatoare": DATE_URMATOARE,
        "saptamana": SAPTAMANA_NR,
        "quarter": QUARTER,
        "year": QUARTER_YEAR,
        "fisier": f"{QUARTER}_{QUARTER_YEAR}/{REPORT_FILE}",
        "instrumente": [i["simbol"] for i in INSTRUMENTE],
        "preturi": {k: v["pret"] for k, v in PIATA.items()},
    }
    update_json(Path(__file__).parent.parent/"reports"/"index.json", intrare, "rapoarte")
    update_json(OUTPUT_DIR/"index.json", intrare, "rapoarte")
    print(f"  Index actualizat: {QUARTER} {QUARTER_YEAR} / Saptamana {SAPTAMANA_NR}")

def main():
    print(f"=== TreidingSB Raport Saptamanal ===")
    print(f"    Data raport: {DATE_RAPORT} (Saptamana {SAPTAMANA_NR})")
    print(f"    Trimestru: {QUARTER} {QUARTER_YEAR}")

    print("1/4 Context macro...")
    ctx = parseaza(apeleaza_claude(prompt_macro()), SECTIUNI_MACRO)

    print("2/4 Calendar saptamana...")
    cal = parseaza_calendar(apeleaza_claude(prompt_calendar_saptamana()))
    print(f"    {len(cal)} evenimente")

    print("3/4 Analiza per instrument...")
    a_factori, a_smc = {}, {}
    for instr in INSTRUMENTE:
        print(f"    {instr['simbol']}...")
        a_factori[instr["simbol"]] = parseaza(apeleaza_claude(prompt_factori(instr)), SECTIUNI_FACTORI)
        a_smc[instr["simbol"]] = parseaza(apeleaza_claude(prompt_smc(instr)), SECTIUNI_SMC)

    print("4/4 PDF + index...")
    path = construieste_pdf(ctx, cal, a_factori, a_smc)
    actualizeaza_index(path)
    print(f"=== Finalizat: {path} ===")

if __name__ == "__main__":
    main()
