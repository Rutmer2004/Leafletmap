"""Maatstaat (xlsx), bijgewerkt rekenboek (xlsx) en toelichting SO/DO (docx).

Gebruik:  python3 src/documenten.py <pad naar origineel Rekenboek_herontwerp.xlsx>
Leest Maatstaat/maatstaat.json (uitvoer van haven.py).
"""
import json
import os
import subprocess
import sys

import openpyxl
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "Maatstaat", "maatstaat.json")))
SO, DO, GEO = D["SO"]["m"], D["DO"]["m"], D["georef"]
ANK = D["DO"]["anker"]
DT = D["DO"].get("info", {}).get("detail", {})


def nl(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


GA, GS = GEO["_afstand"], GEO["_gshhs"]
BRON = [(k, v) for k, v in GEO.items() if not k.startswith("_")]

BESLUITEN = [
    ("B01", "Havenligging", "Zoekgebied locatie B; exacte plaats open.",
     f"Locatie vastgesteld: Porto Central, Presidente Kennedy - Espírito Santo (29350-000). Havenas haaks op de kust (azimut 110 gr) "
     f"door het bouwterrein fase 1; kustpunt A1 E {nl(ANK['A1']['E'], 1)} / N {nl(ANK['A1']['N'], 1)}; bekkens landinwaarts op het Porto Central-terrein.",
     "Vastgelegd", "Ligging van de havenas op het terrein afstemmen met het bouwterrein fase 1 / masterplan."),
    ("B02", "Havenvorm en programma", "SO: grove schets op de Porto Central-render.",
     "DO: de vorm van de render blijft: gebogen dammen, ingang naar het OZO, hoofdbekken langs de noordkade, twee schuine vingers met "
     "insteekbekkens en het tankpark langs de zuidrand. Er staan alleen functies uit de opdracht in: containers (vinger 6), droge bulk/graan "
     "(noordkade), voertuigen/RoRo (vinger 7/8), LNG en de centrale (zuidrand). Erts, werf, industrie en olie zijn weggelaten; de overige "
     "ruimte op vinger 7/8 en de tweede insteek zijn uitbreidingsruimte voor de eigen ladingstromen na 2045.",
     "Vastgelegd", "Uitbreidingsruimte apart onderbouwen als de groei na 2045 aan de orde komt."),
    ("B03", "Havenmond", f"SO: 350 m tussen damhartlijnen, vrij tussen de footprints maar {nl(SO['havenmond_vrij_m'])} m.",
     f"DO: dammen verlegd, {nl(DO['havenmond_vrij_m'])} m vrij tussen de golfbrekerfootprints (90 m breed).",
     "Verwerkt", "Na golfbrekerontwerp (kruin, taluds) footprint en vrije breedte opnieuw meten."),
    ("B04", "Manoeuvreren met grote schepen", f"SO: containerkade in het insteekbekken: een schip van 334 m moet {nl(SO['bocht_hoofdbekken_insteek_graden'])} gr "
     f"draaien vanuit een hoofdbekken van {nl(SO['breedte_hoofdbekken_m'])} m breed. Met een vuistregel voor de bochtstraal van minimaal 3 x LOA "
     f"(ca. 1.000 m) past dat niet. Ook overlapt de draaikom de containervinger ({nl(SO['draaikom_overlap_land_m2'] / 1e4, 1)} ha) en is er "
     "binnen geen draairuimte voor graan- en RoRo-schepen.",
     f"DO: containerkade aan de voorhavenzijde van vinger 6: containerschepen zwaaien in de draaikom (D 720 m = 2,2 LOA) en verhalen zijwaarts "
     f"met sleepboten naar de kade, zonder bocht buiten de draaikom. Graan- en RoRo-schepen (ca. 230 m) varen met {nl(DO['bocht_geul_hoofdbekken_graden'])} gr "
     "koerswijziging het hoofdbekken in en zwaaien in een draaikom binnenhaven van D 460 m (2 x LOA) op de kruising met het insteekbekken, "
     f"op de plaats van de -16 m-cirkel in de render; die ligt {nl(DO['draaikom_binnen_vrij_van_schepen_m'])} m vrij van afgemeerde schepen. "
     f"Draaikom voorhaven {nl(DO['draaikom_vrij_van_schepen_m'])} m vrij; stopweg {nl(DO['stopweg_mond_draaikom_m'])} m = {nl(DO['stopweg_in_LOA'], 1)} LOA.",
     "Verwerkt", "Toetsen met bochtstralen uit PIANC WG121 en een nautische simulatie met sleepboten."),
    ("B05", "Toegangsgeul en sleepboten", "SO: geul knikt 15 gr op 2,2 km buiten de mond; geen sleepbootkoppelpunt.",
     f"DO: rechte geul 220 m, -18,20 m MLWS, in het verlengde van de havenmond; koppelpunt {nl(DO['sleepboot_buiten_mond_m'])} m buiten de mond (A4). "
     f"Lengte buiten de mond voorlopig {nl(DO['geullengte_buiten_mond_m'])} m: Porto Central meldt een toegang van ca. 26 km tot ca. -25 m; "
     "bij een vergelijkbare helling ligt de -18,2 m-lijn rond 18 km.",
     "Deels open", "Eindpunt op de -18,2 m MLWS-dieptelijn van de bathymetrie leggen; MLWS-DHN koppelen; geullengte terugzetten in Nautiek D31."),
    ("B06", "LNG-steiger en tanks", f"SO: LNG-tanks direct achter het containerterrein, op {nl(SO['lng_tank_tot_containerterrein_m'])} m.",
     f"DO: tanks in het zuidelijke deel van de LNG-zone, {nl(DO['lng_tank_tot_containerterrein_m'])} m van het containerterrein met de zuidweg ertussen; "
     f"LNG-steiger achter de zuidelijke dam, {nl(DO['lng_ligplaats_tot_draaikom_m'])} m vrij van de draaikom; ruimte voor een 4e tank.",
     "Verwerkt / QRA open", "QRA en veiligheidsafstanden; N-1-voorraadbeleid kiezen."),
    ("B07", "Droge bulk (graan) en RoRo", f"SO: gedeeld perceel van {nl(SO['graan_ha'])} ha aan de noordkade, weg kruist het terrein.",
     f"DO: graan {nl(DO['graan_ha'], 1)} ha aan de noordkade (render 10) met silo en transportband; RoRo {nl(DO['roro_ha'], 1)} ha in de "
     "noordoosthoek van vinger 7/8 met kade aan het insteekbekken; ieder een kade van 300 m en een eigen poort.",
     "Verwerkt", "Rijcircuit RoRo en conveyorroute graan detailleren."),
    ("B08", "Fasering", "SO: containerfase 1 aan het zuideinde; alle bekkens in fase 1 baggeren.",
     f"DO: containers fase 1 aan de noordkop (C1-C2), de kade groeit zuidwaarts langs de voorhaven; gebaggerd {nl(DO['binnenbekken_m2']['1'] / 1e4, 1)} / "
     f"{nl(DO['binnenbekken_m2']['2'] / 1e4, 1)} / {nl(DO['binnenbekken_m2']['3'] / 1e4, 1)} ha; insteek zuid, hoofdbekken west en tweede insteek "
     f"({nl(DO['reserve_water_m2'] / 1e4, 1)} ha) pas na 2045.",
     "Verwerkt", "Bouwmethode uitbreiding naast werkende kade uitwerken."),
    ("B09", "Centrale en utilities", "SO: centrale naast de LNG-zone.",
     f"DO: reservering {nl(DO['centrale_ha'], 1)} ha naast de LNG-zone langs de zuidrand; gasleiding naar het regionale net; koelwater indicatief.",
     "Reservering", "Vermogen/proceskeuze vaststellen; recirculatie koelwater toetsen."),
    ("B10", "Achterland", "SO: weg door het graan/RoRo-perceel.",
     "DO: noordweg langs graan, RoRo en havendienst; zuidweg langs containerterrein, LNG en centrale; beide aangesloten op het regionale net "
     "aan de westzijde, met spoor.",
     "Verwerkt", "Tracé naar het regionale weg- en spoornet bepalen."),
    ("B11", "Ondergrond en georeferentie", "Kaartondergrond nodig met controle.",
     f"Sentinel-2 L2A van 03-07-2026 (10 m); kust vs. GSHHS gemiddeld {nl(GS['gemiddeld_m'])} m (sd {nl(GS['std_m'])} m); "
     "bronpunten liggen 14-18 m van de waterlijn.",
     "Gecontroleerd", "In Civil 3D drie herkenningspunten tegen Map Aerial meten en afwijking invullen."),
    ("B12", "Grondwerk", "Oppervlakken ontbraken.",
     f"Havenbekken {nl(DO['havenbekken_totaal_m2'])} m2, geul buiten de mond {nl(DO['geul_buiten_m2'])} m2, terreinophoging {nl(DO['terreinophoging_m2'])} m2 ingevuld; "
     "ontwerpbodem als LandXML-oppervlak voor Civil 3D.",
     "Deels open", "Bathymetrie als Civil 3D-oppervlak inlezen en volume tegen Ontwerpbodem_DO berekenen; geul splitsen op DHN -15 m."),
    ("B13", "Variantafweging", "Scores ontbreken.", "Niet door de tekenaar ingevuld: de groep scoort de eigen schetsen met motivering.",
     "Open", "Tabblad Afweging invullen per groepslid-schets."),
]

MAATSTAAT = [
    ("Hoofdgeul bodembreedte", "m", 220, 220, "Nautiek D20", "rekenuitkomst"),
    ("Bodemhoogte geul en bekkens", "m MLWS", -18.20, -18.20, "Nautiek D25", "voorlopig"),
    ("Geullengte buiten havenmond", "m", round(DO["geullengte_buiten_mond_m"]), None, "Nautiek D31", "VOORLOPIG"),
    ("Vaarafstand geuleinde - draaikom", "m", round(DO["geullengte_totaal_vanaf_draaikom_m"]), None, "Nautiek D31", "VOORLOPIG"),
    ("Vrije draaikom diameter", "m", 720, 720, "Nautiek D28", "vrij getoetst"),
    ("Draaikom tot afgemeerde schepen", "m", round(DO["draaikom_vrij_van_schepen_m"]), ">0", "", "voldoet"),
    ("Draaikom tot kades/dammen", "m", round(DO["draaikom_vrij_van_kades_dammen_m"]), ">0", "", "voldoet"),
    ("Havenmond vrij tussen footprints", "m", round(DO["havenmond_vrij_m"]), 350, "Nautiek D29", "voldoet"),
    ("Stopweg havenmond - draaikom", "m", round(DO["stopweg_mond_draaikom_m"]), 1670, "5 x LOA", "voldoet"),
    ("Sleepbootkoppelpunt buiten mond", "m", round(DO["sleepboot_buiten_mond_m"]), None, "rapport 5.1", "ingetekend"),
    ("Containerkade fase 1", "m", DO["containerkade_m"]["1"], 800, "Containers D18", "gelijk"),
    ("Containerkade fase 2", "m", DO["containerkade_m"]["2"], 1200, "Containers E18", "gelijk"),
    ("Containerkade fase 3", "m", DO["containerkade_m"]["3"], 1600, "Containers F18", "gelijk"),
    ("Containerterrein fase 1", "ha", round(DO["container_ha"]["1"], 1), 72, "Invoer D20 (vraag 40,8)", "gelijk"),
    ("Containerterrein fase 2", "ha", round(DO["container_ha"]["2"], 1), 108, "Invoer E20 (vraag 67,9)", "gelijk"),
    ("Containerterrein fase 3", "ha", round(DO["container_ha"]["3"], 1), 144, "Invoer F20 (vraag 135,9)", "gelijk"),
    ("Graankade", "m", 300, 300, "rapport 8.1", "gelijk"),
    ("Graanterrein", "ha", round(DO["graan_ha"], 1), 30, "Invoer D39 (vraag 5,1)", "gelijk"),
    ("RoRo-kade", "m", 300, 300, "rapport 8.2", "gelijk"),
    ("RoRo-terrein", "ha", round(DO["roro_ha"], 1), 30, "Invoer D46 (vraag 26,9)", "gelijk"),
    ("Draaikom binnenhaven (graan/RoRo)", "m", 460, 458, "2 x LOA graan", "vrij getoetst"),
    ("  afstand tot afgemeerde schepen", "m", round(DO["draaikom_binnen_vrij_van_schepen_m"]), ">0", "", "voldoet"),
    ("LNG-ligplaatsenvelop", "m", 400, 400, "tekenbrief", "dolphins indicatief"),
    ("LNG-envelop tot draaikom", "m", round(DO["lng_ligplaats_tot_draaikom_m"]), ">0", "", "vrij; QRA volgt"),
    ("LNG-tanks tot containerterrein", "m", round(DO["lng_tank_tot_containerterrein_m"]), None, "", "QRA volgt"),
    ("LNG-zone (tanks + hervergassing)", "ha", round(DO["lng_zone_ha"], 1), None, "Invoer D51-D52", "3 tanks + optie 4e"),
    ("Centrale + utilities (reservering)", "ha", round(DO["centrale_ha"], 1), None, "geen vast oppervlak", "reservering"),
    ("STS-kranen F1 / F2 / F3", "st", f"{DT['sts_per_fase']['1']} / {DT['sts_per_fase']['2']} / {DT['sts_per_fase']['3']}", "6 / 12 / 20", "Containers D19-F19", "gelijk"),
    ("TEU-grondslots stackzone F3 (28 m2/slot)", "slots", round(DT["teu_grondslots"]), 40444, "Containers F25", "voldoet"),
    ("Stackzone bruto", "ha", round(DT["stack_bruto_m2"] / 1e4, 1), 113.2, "Containers F26", "voldoet"),
    ("Graansilo's 8 x D 30 m x 40 m", "t", round(DT["graan_silo_ton"]), 154100, "Overige terminals F9", "voldoet"),
    ("RoRo-parkeercapaciteit", "auto's", round(DT["roro_auto_capaciteit"]), 7479, "Overige terminals F15", "voldoet"),
    ("Centrale STEG-eenheden", "MW", DT["centrale_eenheden_mw"], 2256, "Overige terminals F30", "rekenvoorbeeld"),
    ("Havendiensten / sleepboten", "ha", round(DO["havendienst_ha"], 1), None, "", "reservering"),
    ("Vrije breedte hoofdbekken met graanschip aan de kade", "m", round(DO["vrije_breedte_binnenbekken_m"]), 220, "", "voldoet"),
    ("Binnenbekken gebaggerd fase 1", "m2", round(DO["binnenbekken_m2"]["1"]), None, "", ""),
    ("Binnenbekken gebaggerd fase 2 (cumulatief)", "m2", round(DO["binnenbekken_m2"]["2"]), None, "", ""),
    ("Binnenbekken gebaggerd fase 3 (cumulatief)", "m2", round(DO["binnenbekken_m2"]["3"]), None, "", ""),
    ("Voorhaven + LNG-insteek gebaggerd", "m2", round(DO["voorhaven_bagger_m2"]), None, "", ""),
    ("Havenbekken totaal (zone 1)", "m2", round(DO["havenbekken_totaal_m2"]), None, "Grondwerk C6", "ingevuld"),
    ("Geul buiten de mond (zone 2 + 3)", "m2", round(DO["geul_buiten_m2"]), None, "Grondwerk C7 + C8", "splitsing open"),
    ("Terreinophoging (terminals, LNG, centrale, havendienst)", "m2", round(DO["terreinophoging_m2"]), None, "Grondwerk D21", "ingevuld"),
]

THIN = Side(style="thin", color="999999")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD = PatternFill("solid", fgColor="1B4332")


def sheet(ws, title, header, rows, widths):
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append(["Havenontwerp Groep 1 | DO versie 2.0 | 22-10-2026 | SIRGAS 2000 / UTM 24S (EPSG:31984), meter"])
    ws.append([])
    ws.append(header)
    for c in ws[4]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for r in rows:
        ws.append(list(r))
    for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
        for c in row:
            c.border = BOX
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.freeze_panes = "A5"


def write_maatstaat(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Maatstaat DO"
    sheet(ws, "Maatstaat definitief ontwerp - gemeten in de tekening", ["Onderdeel", "Eenheid", "Gemeten DO", "Rekenboek/eis",
          "Cel / bron", "Status"], MAATSTAAT, [48, 9, 14, 14, 26, 22])
    for r in range(5, ws.max_row + 1):
        ws.cell(r, 3).number_format = "#,##0.0" if ws.cell(r, 2).value == "ha" else "#,##0.00" if ws.cell(r, 2).value == "m MLWS" else "#,##0"
    ws = wb.create_sheet("Ankerpunten")
    rows = [(k, a["naam"], round(a["E"], 2), round(a["N"], 2), round(a["lat"], 7), round(a["lon"], 7), round(a["u"], 1), round(a["v"], 1))
            for k, a in ANK.items()]
    sheet(ws, "Ontwerpankerpunten DO", ["Punt", "Omschrijving", "E (m)", "N (m)", "Lat WGS84", "Lon WGS84", "x render (px)", "y render (px)"],
          rows, [7, 34, 14, 14, 13, 13, 12, 12])
    r = ws.max_row + 2
    inf = D["DO"]["info"]
    A = inf["render_affine"]
    for t in [f"DO overgetrokken van de Porto Central-render: schaal {inf['render_schaal_m_per_px']} m/px, draaiing {inf['render_draaiing_graden']} gr, "
              "render (812,5; 275) = A1.",
              f"E = {A[0]:.6f} x + {A[1]:.6f} y + {A[4]:.3f};  N = {A[2]:.6f} x + {A[3]:.6f} y + {A[5]:.3f}  (x, y = renderpixel, y omlaag).",
              "Lat/lon via pyproj (EPSG:31984 -> EPSG:4326)."]:
        ws.cell(r, 1, t)
        r += 1
    ws = wb.create_sheet("Ankerpunten SO")
    rows = [(k, a["naam"], round(a["E"], 2), round(a["N"], 2), round(a["lat"], 7), round(a["lon"], 7)) for k, a in D["SO"]["anker"].items()]
    sheet(ws, "Ontwerpankerpunten SO (ter vergelijking)", ["Punt", "Omschrijving", "E (m)", "N (m)", "Lat", "Lon"], rows, [7, 34, 14, 14, 13, 13])
    ws = wb.create_sheet("Georeferentie")
    rows = [("Kaartbron", "Copernicus Sentinel-2 L2A (ESA), opname 03-07-2026, tegels 24KTB en 24KUB, AWS Open Data (sentinel-cogs), "
                          "geraadpleegd 22-10-2026; bestand CAD/Ondergrond/S2_20260703_TCI_EPSG31984.jpg + .jgw + .prj"),
            ("Bronresolutie", "10 m per pixel"),
            ("Stelsel", "SIRGAS 2000 / UTM zone 24S, EPSG:31984; Sentinel-2 levert WGS84/UTM 24S (EPSG:32724), verschil < 0,1 m"),
            ("Hoogtedatum", "Diepten t.o.v. MLWS (voorlopig); koppeling MLWS - DHN nog vast te leggen"),
            ("Kustlijn", "Waterlijn uit NDWI (B03/B08) van 03-07-2026; geen MLWS-lijn"),
            ("Kustcontrole GSHHS", f"Gemiddeld dE {nl(GS['gemiddeld_m'], 1)} m, sd {nl(GS['std_m'], 1)} m over {len(GS['rijen'])} profielen"),
            ("Bekende afstand", f"Bronpunten: geodetisch {nl(GA['geodetisch_m'], 2)} m; grid {nl(GA['grid_m'], 2)} m; verschil {nl(GA['verschil_m'], 2)} m (k = {GA['schaalfactor']:.6f})"),
            ("Noordrichting", f"Meridiaanconvergentie {GA['meridiaanconvergentie_graden']:.3f} gr; bladen zijn grid-noord"),
            ] + [(f"Bronpunt {k}", f"{v['lat']}, {v['lon']} -> E {nl(v['E'], 2)}, N {nl(v['N'], 2)}; {nl(v['afstand_tot_waterlijn_m'], 1)} m tot waterlijn") for k, v in BRON]
    sheet(ws, "Ondergrond en georeferentiecontrole", ["Onderdeel", "Waarde"], rows, [26, 120])
    r = ws.max_row + 2
    ws.cell(r, 1, "Herkenningspunten in Civil 3D (in te vullen na GEOMAPIMAGE / Map Aerial)").font = Font(bold=True)
    hdr = ["Punt", "Omschrijving", "E tekening", "N tekening", "E Map Aerial", "N Map Aerial", "dE (m)", "dN (m)", "afwijking (m)"]
    for i, h in enumerate(hdr):
        c = ws.cell(r + 1, i + 1, h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEAD
    pts = [("H1", "Wegkruising landinwaarts (kies zelf)"), ("H2", "Hoek bouwterrein fase 1 aan het strand"), ("H3", "Kustbebouwing zuid, wegkruising")]
    for j, (p, o) in enumerate(pts):
        rr = r + 2 + j
        ws.cell(rr, 1, p)
        ws.cell(rr, 2, o)
        ws.cell(rr, 7, f"=IF(COUNT(C{rr},E{rr})=2,E{rr}-C{rr},\"\")")
        ws.cell(rr, 8, f"=IF(COUNT(D{rr},F{rr})=2,F{rr}-D{rr},\"\")")
        ws.cell(rr, 9, f"=IF(COUNT(G{rr},H{rr})=2,SQRT(G{rr}^2+H{rr}^2),\"\")")
        for cc in range(3, 7):
            ws.cell(rr, cc).fill = PatternFill("solid", fgColor="FFF3B0")
    ws = wb.create_sheet("Kustcontrole")
    sheet(ws, "Kustlijncontrole Sentinel-2 tegen GSHHS (full)", ["N (m)", "E waterlijn S2", "E kust GSHHS", "dE (m)"],
          [(r_["N"], round(r_["E_s2"], 1), round(r_["E_gshhs"], 1), round(r_["dE"], 1)) for r_ in GS["rijen"]], [12, 16, 16, 10])
    ws = wb.create_sheet("Besluitenlijst SO-DO")
    sheet(ws, "Besluitenlijst na bespreking schetsontwerp", ["Nr", "Onderwerp", "Schetsontwerp (SO)", "Besluit / definitief ontwerp (DO)",
          "Status", "Vervolgstap"], BESLUITEN, [6, 20, 45, 60, 14, 45])
    wb.save(path)


def update_rekenboek(src, dst):
    wb = openpyxl.load_workbook(src)
    yel = PatternFill("solid", fgColor="FFF3B0")
    n = wb["Nautiek"]
    n["D31"] = round(DO["geullengte_totaal_vanaf_draaikom_m"])
    n["D31"].fill = yel
    n["G31"] = "VOORLOPIG"
    n["H31"] = (f"DO-tekening: {nl(DO['geullengte_buiten_mond_m'])} m buiten de mond (eindpunt A5 nog op -18,2 m MLWS-lijn leggen) "
                f"+ {nl(DO['stopweg_mond_draaikom_m'])} m mond-draaikom")
    g = wb["Grondwerk"]
    g["C6"] = round(DO["havenbekken_totaal_m2"])
    g["H6"] = "DO: binnenbekken F1-F3 + voorhaven + LNG-insteek (gesloten vlakken, Maatstaat). Bestaande diepte nog invullen."
    g["H7"] = f"DO: geul buiten de mond totaal {nl(DO['geul_buiten_m2'])} m2 (220 x {nl(DO['geullengte_buiten_mond_m'])} m); splitsen op DHN -15 m-contour."
    g["H8"] = "Zie H7; oppervlak pas invullen na splitsing op de dieptelijn."
    g["D21"] = round(DO["terreinophoging_m2"])
    g["E21"] = "Gemeten DO"
    g["F21"] = "Terminals, LNG-zone, centrale en havendienst; exclusief reserveterreinen."
    for c in ("C6", "D21"):
        g[c].fill = yel
    inv = wb["Invoer"]
    inv["H20"] = "DO-tekening: 72,0 / 108,0 / 144,0 ha gesloten polygonen (Maatstaat); gelijk aan reservering"
    inv["H39"] = "DO-tekening: 30,0 ha (500 x 600 m), kade 300 m"
    inv["H46"] = "26,93 ha berekend; DO-tekening 30,0 ha (500 x 600 m), kade 300 m"
    k = wb["Keuzes"]
    r = 22
    for b in BESLUITEN:
        k.cell(r, 1, f"K{r - 5:02d}")
        k.cell(r, 2, b[1])
        k.cell(r, 3, b[3])
        k.cell(r, 4, b[4])
        k.cell(r, 5, f"Besluitenlijst {b[0]}; vervolg: {b[5]}")
        r += 1
    ws = wb.create_sheet("Tekening_DO")
    ws.append(["Maatstaat uit Haven_DO (gemeten in de tekening) - zie ook Maatstaat_en_coordinaten.xlsx"])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append(["Onderdeel", "Eenheid", "Gemeten DO", "Rekenboek/eis", "Cel / bron", "Status"])
    for c in ws[2]:
        c.font = Font(bold=True)
    for row in MAATSTAAT:
        ws.append(list(row))
    ws.append([])
    ws.append(["Punt", "Omschrijving", "E (m)", "N (m)", "Lat", "Lon"])
    for kk, a in ANK.items():
        ws.append([kk, a["naam"], round(a["E"], 2), round(a["N"], 2), round(a["lat"], 7), round(a["lon"], 7)])
    for col, w in zip("ABCDEF", (48, 30, 14, 14, 26, 22)):
        ws.column_dimensions[col].width = w
    from openpyxl.workbook.properties import CalcProperties
    wb.calculation = CalcProperties(fullCalcOnLoad=True)
    wb.save(dst)


# --------------------------------------------------------------------------------------
def write_docx(path, figs):
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.2)
    t = doc.add_heading("Havenontwerp Groep 1 - Schetsontwerp en definitief ontwerp", 0)
    doc.add_paragraph("Toelichting bij Haven_SO en Haven_DO | Atelier De Haven A | 22 oktober 2026 | versie 2.0")

    def h(txt, lvl=1):
        doc.add_heading(txt, lvl)

    def p(txt):
        return doc.add_paragraph(txt)

    def bullets(items):
        for i in items:
            doc.add_paragraph(i, style="List Bullet")

    def table(header, rows, widths=None):
        tb = doc.add_table(rows=1, cols=len(header))
        tb.style = "Light Grid Accent 1"
        for i, x in enumerate(header):
            tb.rows[0].cells[i].text = str(x)
        for r in rows:
            cells = tb.add_row().cells
            for i, x in enumerate(r):
                cells[i].text = "" if x is None else (nl(x, 1) if isinstance(x, float) else nl(x) if isinstance(x, int) else str(x))
        for row in tb.rows:
            for c in row.cells:
                for pp in c.paragraphs:
                    for run in pp.runs:
                        run.font.size = Pt(8.5)
        if widths:
            tb.autofit = False
            for i, w in enumerate(widths):
                tb.columns[i].width = Cm(w)
            for row in tb.rows:
                for i, w in enumerate(widths):
                    row.cells[i].width = Cm(w)
        doc.add_paragraph()

    h("1 Wat is opgeleverd")
    table(["Bestand", "Inhoud"], [
        ("CAD/Haven_SO.dxf", "Schetsontwerp in projectcoördinaten EPSG:31984 met lagen, luchtfoto-ondergrond (IMAGE) en A1-layout 1:10.000"),
        ("CAD/Haven_DO.dxf", "Definitief ontwerp naar Porto Central met alleen de opdrachtfuncties; maatvoering, fasegrenzen, ankerpunten, A1-layout 1:12.500, render op laag HV-REFERENTIE"),
        ("CAD/Haven_DO_geul_ontwerpbodem.xml", "LandXML voor Civil 3D: geulas als Alignment en ontwerpbodem -18,20 m MLWS als TIN-oppervlak"),
        ("Referentie/", "Uitsnede Porto Central-masterplan 2016 p. 9 (vormreferentie)"),
        ("CAD/Ondergrond/", "Sentinel-2 luchtfoto (JPG + world file .jgw + .prj), kustlijnen; relatief pad naast de DXF"),
        ("PDF/Haven_SO.pdf", "SO-01 overzicht 1:50.000, SO-02 havenindeling 1:12.500, SO-03 bespreekpunten"),
        ("PDF/Haven_DO.pdf", "DO-01 overzicht, DO-02 havenplan 1:12.500, DO-03 fasering 1:25.000, DO-04 maatstaat/georeferentie, DO-05 overtrek render, DO-06 t/m DO-08 terminaldetails"),
        ("Maatstaat/Maatstaat_en_coordinaten.xlsx", "Maatstaat, ankerpunten E/N, georeferentie, kustcontrole, besluitenlijst"),
        ("Onderbouwing/Rekenboek_herontwerp_bijgewerkt.xlsx", "Rekenboek met gemeten tekenmaten teruggevoerd (Nautiek, Grondwerk, Invoer, Keuzes, Tekening_DO)"),
        ("webkaart/index.html", "Interactieve kaart (Leaflet) met SO en DO op luchtfoto"),
        ("src/", "Python-scripts die alles reproduceerbaar uit één geometriebron genereren"),
    ], [6, 11])
    p("DWG: de bestanden zijn als DXF (AutoCAD 2018) geleverd omdat er geen AutoCAD-licentie in de genereeromgeving was. "
      "Openen in Civil 3D en opslaan als Haven_SO.dwg / Haven_DO.dwg levert de gevraagde DWG's (zie par. 8).")

    h("2 Kaartondergrond en coördinatenstelsel")
    p("Stelsel: SIRGAS 2000 / UTM zone 24S (EPSG:31984), eenheid meter, X = Easting en Y = Northing. Alle objecten staan direct in "
      "projectcoördinaten; er is geen lokale tekening die achteraf verschoven moet worden.")
    p("Ondergrond: Copernicus Sentinel-2 L2A, opname 3 juli 2026 (wolkenbedekking 0,01%), tegels 24KTB en 24KUB, 10 m resolutie, "
      "betrokken via AWS Open Data (Cloud Optimized GeoTIFF), geraadpleegd 22 oktober 2026. Sentinel-2 wordt geleverd in WGS84 / UTM 24S "
      "(EPSG:32724); het verschil met SIRGAS 2000 is kleiner dan 0,1 m en daarmee verwaarloosbaar ten opzichte van de pixelgrootte. "
      "De kustlijn is de waterlijn op de opnamedatum, afgeleid met NDWI (banden B03/B08); dit is geen MLWS-lijn.")
    h("2.1 Georeferentiecontrole", 2)
    table(["Controle", "Resultaat"], [
        ("Kustlijn tegen onafhankelijke GSHHS-kust (full)", f"gemiddeld {nl(GS['gemiddeld_m'], 1)} m, standaardafwijking {nl(GS['std_m'], 1)} m over {len(GS['rijen'])} profielen: geen systematische verschuiving of draaiing"),
        *[(f"Bronpunt {k}", f"E {nl(v['E'], 1)} / N {nl(v['N'], 1)}; ligt {nl(v['afstand_tot_waterlijn_m'], 1)} m van de waterlijn") for k, v in BRON],
        ("Bekende afstand (bronpunten)", f"geodetisch {nl(GA['geodetisch_m'], 1)} m, in grid {nl(GA['grid_m'], 1)} m; verschil {nl(GA['verschil_m'], 2)} m = UTM-schaalfactor {GA['schaalfactor']:.5f}"),
        ("Noordrichting", f"meridiaanconvergentie {GA['meridiaanconvergentie_graden']:.2f} gr; de bladen zijn grid-noord"),
        ("Bronresolutie", "10 m (1 pixel); ESA-geolocatie van orde 1 pixel"),
        ("Nog te doen in Civil 3D", "Drie verspreide herkenningspunten (wegkruisingen, bebouwing) tegen Map Aerial meten; tabel staat klaar in Maatstaat_en_coordinaten.xlsx, tabblad Georeferentie"),
    ], [5, 12])
    p("Diepten: de bodemmaat -18,20 m MLWS is voorlopig. De koppeling MLWS - DHN en de bathymetrie zijn nog niet ingelezen; daarom zijn "
      "het geuleinde en de baggervolumes herkenbaar voorlopig gelaten.")

    h("3 Gekozen havenligging")
    a1 = ANK["A1"]
    p(f"De locatie is vastgesteld: Porto Central, Presidente Kennedy - Espírito Santo, 29350-000, Brazilië. Dit ligt binnen het zoekgebied van "
      f"locatie B, tussen de bronpunten São Francisco de Itabapoana en Rio Marobá. De havenas staat haaks "
      f"op de kust (azimut 110 gr; de kust loopt hier onder {GEO['_kust_azimut_graden']:.1f} gr) en loopt door het bouwterrein van fase 1 dat op de "
      f"luchtfoto van 3 juli 2026 aan het strand zichtbaar is. Het kustpunt op de havenas (A1) ligt op "
      f"E {nl(a1['E'], 1)} / N {nl(a1['N'], 1)} (WGS84 {a1['lat']:.6f}, {a1['lon']:.6f}).")
    bullets([
        "Havenmond, voorhaven en draaikom liggen zeewaarts van het bouwterrein fase 1 aan het strand.",
        "Binnenbekken, containerterminal, graan en RoRo liggen landinwaarts op het kale Porto Central-terrein (restinga).",
        f"LNG en centrale liggen in het zuiden van het terrein; de dichtstbijzijnde kustbebouwing (N ca. 7.646.300) ligt op ruim {nl(DO['lng_tank_tot_kustbebouwing_zuid_m'] / 1000, 1)} km van de tanks.",
        "De rivier en het wetland bij de Itabapoana-monding blijven buiten het plan.",
    ])
    if "DO-01" in figs:
        doc.add_picture(figs["DO-01"], width=Cm(16.5))
        doc.add_paragraph("Figuur 1 Overzicht zoekgebied en havenligging (DO-01).").alignment = WD_ALIGN_PARAGRAPH.CENTER

    h("4 Schetsontwerp (SO)")
    p("Het schetsontwerp is een eerste, grove versie op de Porto Central-render met alleen de functies uit de opdracht. "
      "Bij de bespreking kwamen zeven punten naar voren (hoofdstuk 5), waarvan de belangrijkste de bocht naar het insteekbekken is.")
    table(["Kenmerk SO", "Waarde"], [
        ("Havenmond (hart-hart / vrij)", f"350 m / {nl(SO['havenmond_vrij_m'])} m"),
        ("Draaikom", f"D 720 m; overlapt de containervinger ({nl(SO['draaikom_overlap_land_m2'] / 1e4, 1)} ha)"),
        ("Containerkade", f"1.600 m in een insteekbekken van {nl(SO['breedte_insteek_m'])} m; bocht {nl(SO['bocht_hoofdbekken_insteek_graden'])} gr vanuit een hoofdbekken van {nl(SO['breedte_hoofdbekken_m'])} m"),
        ("Geul", f"220 m, knik 15 gr op 2,2 km buiten de mond; geen sleepbootkoppelpunt"),
        ("Graan + RoRo", f"gedeeld perceel {nl(SO['graan_ha'])} ha aan de noordkade, weg door het perceel"),
        ("LNG + centrale", f"tanks op {nl(SO['lng_tank_tot_containerterrein_m'])} m van het containerterrein"),
        ("Fasering", "containers F1 aan het zuideinde; alle bekkens in fase 1"),
    ], [6, 11])
    h("4.1 Wat we van Porto Central overnemen", 2)
    table(["Porto Central (render / masterplan)", "Ons ontwerp"], [
        ("11 gebogen golfbrekers, 14 ingang naar het OZO", "Overgenomen; havenmond 350 m vrij (render ca. 640 m)"),
        ("Toegang ca. 26 km tot ca. -25 m", f"Geul 220 m tot -18,20 m MLWS, voorlopig {nl(DO['geullengte_buiten_mond_m'])} m"),
        ("-20 m-cirkel in de voorhaven", "Vrije draaikom D 720 m (containerschepen)"),
        ("-16 m-cirkel in het hoofdbekken", "Draaikom binnenhaven D 460 m (graan en RoRo)"),
        ("Hoofdbekken, twee vingers, twee insteekbekkens", "Overgenomen (vorm gelijk aan de render)"),
        ("6 containerterminal", "Containers 144 ha; kraankade aan de voorhavenzijde"),
        ("10 graan aan de noordkade", "Graan 30 ha"),
        ("7/8 tweede vinger", "RoRo 30 ha; rest uitbreidingsruimte eigen terminals"),
        ("9 tankpark, 18 LNG bij de zuiddam", "LNG-zone en centrale; LNG-steiger"),
        ("2 erts, 3 werf, 5 olie, 12/1 industrie", "Niet in de opdracht: weggelaten"),
    ], [7, 10])
    if "SO-03" in figs:
        doc.add_picture(figs["SO-03"], width=Cm(16.5))
        doc.add_paragraph("Figuur 2 Bespreekpunten op het schetsontwerp (SO-03).").alignment = WD_ALIGN_PARAGRAPH.CENTER

    h("5 Bespreking SO en besluitenlijst")
    p("Het schetsontwerp is getoetst op de nautische ruimte, de tekenbrief en de vergelijking met het rekenboek. De bespreekpunten en de "
      "besluiten staan hieronder; het definitieve ontwerp verwerkt ze. Laat de punten met status open of deels open met de begeleider bevestigen.")
    table(["Nr", "Onderwerp", "SO", "Besluit / DO", "Status", "Vervolgstap"], BESLUITEN, [1.0, 2.2, 3.6, 5.0, 1.8, 3.4])

    h("6 Definitief ontwerp (DO)")
    p("Het definitieve ontwerp houdt de vorm van de Porto Central-render aan (dammen, hoofdbekken, twee vingers met insteekbekkens, "
      "tankpark), maar bevat alleen de functies uit de opdracht en is getoetst op manoeuvreerbaarheid: grote schepen draaien alleen in de "
      "draaikommen. De render is op schaal (10,035 m per pixel) op de kust gelegd; blad DO-05 toont de render met het DO erop. In de DXF "
      "staat de render op laag HV-REFERENTIE.")
    bullets([
        f"Voorhaven met twee gebogen golfbrekers (footprint 90 m, voorlopig); havenmond {nl(DO['havenmond_vrij_m'])} m vrij, ingang naar het OZO.",
        f"Rechte toegangsgeul 220 m bodembreedte, -18,20 m MLWS; voorlopig {nl(DO['geullengte_buiten_mond_m'])} m buiten de mond.",
        f"Sleepbootkoppelpunt {nl(DO['sleepboot_buiten_mond_m'])} m buiten de mond; stopweg mond - draaikom {nl(DO['stopweg_mond_draaikom_m'])} m ({nl(DO['stopweg_in_LOA'], 1)} LOA).",
        f"Vrije draaikom D 720 m in de voorhaven ({nl(DO['draaikom_vrij_van_schepen_m'])} m vrij van schepen) en draaikom binnenhaven D 460 m "
        f"({nl(DO['draaikom_binnen_vrij_van_schepen_m'])} m vrij).",
        "Containerterminal (vinger 6): kraankade 800 / 1.200 / 1.600 m aan de voorhaven, terrein 72 / 108 / 144 ha; fase 1 aan de noordkop.",
        f"Hoofdbekken {nl(DO['breedte_hoofdbekken_m'])} m breed, koerswijziging vanaf de geul {nl(DO['bocht_geul_hoofdbekken_graden'])} gr; graan 30 ha aan de noordkade.",
        "RoRo 30 ha op vinger 7/8 met kade aan het insteekbekken; de rest van vinger 7/8 en de tweede insteek zijn uitbreidingsruimte na 2045.",
        f"LNG-zone {nl(DO['lng_zone_ha'], 1)} ha met 3 x 180.000 m3 en ruimte voor een 4e tank; centrale {nl(DO['centrale_ha'], 1)} ha; LNG-steiger achter de zuidelijke dam.",
        "Noordweg en ringweg met spoor, aangesloten op het regionale net aan de westzijde.",
    ])
    if "DO-02" in figs:
        doc.add_picture(figs["DO-02"], width=Cm(16.5))
        doc.add_paragraph("Figuur 3 Definitief havenplan (DO-02).").alignment = WD_ALIGN_PARAGRAPH.CENTER
    if "DO-05" in figs:
        doc.add_picture(figs["DO-05"], width=Cm(16.5))
        doc.add_paragraph("Figuur 4 Overtrek: Porto Central-render op de luchtfoto met het DO (DO-05).").alignment = WD_ALIGN_PARAGRAPH.CENTER
    h("6.4 Uitwerking van de terminals (DO-06 t/m DO-08)", 2)
    p("De terminals zijn uitgewerkt tot op het niveau van stackblokken, kranen, silo's, parkeervakken, tanks en installaties. "
      "De kengetallen zijn gecontroleerd tegen het rekenboek.")
    table(["Terminal", "Uitwerking", "Controle tegen rekenboek"], [
        ("Containers (DO-06)", "Kade-apron 60 m met kraanbaan (30,5 m); STS-kranen per fase; RTG-blokken 24 m breed met rijpaden van 12 m en "
         "blokken van 300 m; reefer- en legecontainervakken; railterminal 4 sporen x 1.300 m met RMG; gate met 12 rijstroken, douane/scan, "
         "truckparking; kantoor en werkplaats",
         f"STS {DT['sts_per_fase']['1']}/{DT['sts_per_fase']['2']}/{DT['sts_per_fase']['3']} (6/12/20); "
         f"TEU-grondslots {nl(DT['teu_grondslots_per_fase']['1'])} / {nl(DT['teu_grondslots_per_fase']['2'])} / {nl(DT['teu_grondslots_per_fase']['3'])} "
         "tegen 12.133 / 20.222 / 40.444 nodig"),
        ("Graan (DO-07)", "8 silo's D 30 m x 40 m, vlakke opslag, 2 shiploaders op de kade, transportband, ontvangst per vrachtauto en per spoor, "
         "kantoor/weegbrug", f"{nl(DT['graan_silo_ton'])} t silocapaciteit tegen 154.100 t piekvoorraad"),
        ("RoRo (DO-07)", "Parkeerstroken binnen het rijcircuit, ramp, inspectie, kantoor",
         f"ca. {nl(DT['roro_auto_capaciteit'])} auto's tegen 7.479 auto's piekvoorraad"),
        ("Havendienst (DO-07)", "Havenkantoor/VTS, VTS-toren, loodsen en sleepdienst, brandweer, 3 sleepbootligplaatsen", "-"),
        ("LNG (DO-08)", "3 full-containment tanks in tankput, plaats 4e tank, hervergassing 4 x 33%, BOG-compressor, meetstation, "
         "controlekamer, fakkel; steiger met 3 laadarmen, breasting- en meerdolphins, pijpleidingbrug", "540.000 m3; N-1 nog te kiezen; QRA volgt"),
        ("Centrale (DO-08)", "4 STEG-eenheden, hoogspanningsstation, gasontvangst, koelwaterpompen, waterbehandeling, kantoor",
         f"{nl(DT['centrale_eenheden_mw'])} MW tegen rekenvoorbeeld 2.256 MW (vermogen nog vast te stellen)"),
    ], [3, 8.5, 5.5])
    for key, cap in (("DO-06", "Figuur 6 Containerterminal (DO-06)."), ("DO-07", "Figuur 7 Graan, RoRo en havendienst (DO-07)."),
                     ("DO-08", "Figuur 8 LNG-terminal en centrale (DO-08).")):
        if key in figs:
            doc.add_picture(figs[key], width=Cm(16.5))
            doc.add_paragraph(cap).alignment = WD_ALIGN_PARAGRAPH.CENTER
    h("6.1 Maatstaat en aansluiting op het rekenboek", 2)
    table(["Onderdeel", "Eenheid", "Gemeten DO", "Rekenboek/eis", "Cel / bron", "Status"], MAATSTAAT, [5, 1.3, 2.2, 2.2, 3.5, 2.6])
    h("6.2 Ontwerpankerpunten", 2)
    table(["Punt", "Omschrijving", "E (m)", "N (m)", "Lat", "Lon"],
          [(k, a["naam"], f"{nl(a['E'], 1)}", f"{nl(a['N'], 1)}", f"{a['lat']:.6f}", f"{a['lon']:.6f}") for k, a in ANK.items()],
          [1.2, 5.5, 2.4, 2.6, 2.3, 2.3])
    h("6.3 Fasering", 2)
    p("Golfbrekers, geul, draaikom, LNG-steiger en de leidingcorridors worden in fase 1 op eindmaat gebouwd. Containerkades en het binnenbekken "
      "groeien in drie stappen landinwaarts, aan het doodlopende eind van het bekken, zodat uitbreiding de vaarroute naar werkende kades niet blokkeert.")
    if "DO-03" in figs:
        doc.add_picture(figs["DO-03"], width=Cm(16.5))
        doc.add_paragraph("Figuur 5 Fasering 2025 - 2035 - 2045 (DO-03).").alignment = WD_ALIGN_PARAGRAPH.CENTER

    h("7 Open punten (herkenbaar voorlopig)")
    bullets([
        "Bathymetrie inlezen: geuleinde op de -18,2 m MLWS-lijn, geul splitsen op DHN -15 m, bestaande diepten in Grondwerk.",
        "Koppeling MLWS - DHN en hoogtemodel land; daarna bagger- en ophoogvolumes (TIN-methode, rapport par. 12.1).",
        "Golfbrekerontwerp (kruin, taluds, golfklimaat): footprint en havenmond opnieuw meten.",
        "QRA LNG en N-1-voorraadbeleid; definitieve dolphins en veiligheidszones.",
        "Vermogen en proceskeuze centrale; koelwaterstudie.",
        "Afstemming met het bouwterrein fase 1 en het officiële Porto Central-masterplan (exacte as en kadeligging).",
        "Variantafweging (tabblad Afweging) met de eigen groepsschetsen en motivering.",
    ])

    h("8 Werkwijze in Civil 3D")
    for i, s in enumerate([
        "Kopieer de map CAD inclusief de submap Ondergrond; de luchtfoto is met een relatief pad gekoppeld.",
        "Open Haven_DO.dxf (en Haven_SO.dxf) in Civil 3D. Controleer met EXTERNALREFERENCES dat S2_20260703_TCI_EPSG31984.jpg gevonden wordt.",
        "Toolspace > Settings > Drawing Settings > Units and Zone: eenheid meter, categorie Brazil (of UTM SIRGAS 2000), "
        "zone SIRGAS2000.UTM-24S (EPSG:31984). Teken niets te verschuiven: de objecten staan al op projectcoördinaten.",
        "Geolocation > Map Aerial of Map Hybrid aanzetten als controle; meet drie herkenningspunten en vul de tabel in het tabblad Georeferentie in.",
        "Leg het online kaartbeeld vast met GEOMAPIMAGE zodat het ook in de PDF wordt geplot (of gebruik de meegeleverde Sentinel-2-ondergrond).",
        "Opslaan als: SAVEAS > AutoCAD 2018 Drawing > Haven_DO.dwg en Haven_SO.dwg.",
        "Insert > Import LandXML: Haven_DO_geul_ontwerpbodem.xml geeft de Alignment 'Hoofdgeul_DO' en het oppervlak 'Ontwerpbodem_DO'. "
        "Lees de bathymetrie in als tweede oppervlak en bereken de baggervolumes met het Volumes Dashboard.",
        "Plotten: layout 'DO-02 A1 1-12500' (viewport 1:12.500, titelblok en legenda staan klaar) naar PDF; of gebruik de meegeleverde PDF's.",
        "Lagen: HV-* (zie legenda). De maatvoering staat op HV-MAAT als echte DIMENSION-objecten; het raster 1 km staat op HV-RASTER (uit).",
    ], 1):
        doc.add_paragraph(f"{s}", style="List Number")
    h("Bronnen", 1)
    for s in [
        "Copernicus Sentinel-2 L2A (ESA), tegels 24KTB/24KUB, 03-07-2026, via AWS Open Data Registry (sentinel-cogs). Geraadpleegd 22-10-2026.",
        "Wessel, P. en Smith, W.H.F., GSHHG - A Global Self-consistent, Hierarchical, High-resolution Geography Database (full resolution), via basemap-data-hires.",
        "Opdrachtomschrijving_Civil3D, Tekenbrief_en_ontwerpkeuzes, Rapport_herontwerp en Rekenboek_herontwerp, Groep 1, 22-10-2026.",
        "J. Ferro da Cunha Lima, O Caso Porto Central, ANTT, 16-06-2016, p. 9 (vormreferentie).",
        "PIANC WG121 (2014), Harbour Approach Channels Design Guidelines.",
    ]:
        doc.add_paragraph(s, style="List Bullet")
    doc.save(path)


def figures(tmp):
    os.makedirs(tmp, exist_ok=True)
    out = {}
    for pdf, page, key in [("Haven_DO.pdf", 1, "DO-01"), ("Haven_DO.pdf", 2, "DO-02"), ("Haven_DO.pdf", 3, "DO-03"), ("Haven_SO.pdf", 3, "SO-03"),
                           ("Haven_DO.pdf", 5, "DO-05"), ("Haven_DO.pdf", 6, "DO-06"), ("Haven_DO.pdf", 7, "DO-07"),
                           ("Haven_DO.pdf", 8, "DO-08")]:
        base = os.path.join(tmp, key)
        subprocess.run(["pdftoppm", "-r", "70", "-jpeg", "-f", str(page), "-l", str(page), "-singlefile",
                        os.path.join(ROOT, "PDF", pdf), base], check=True)
        out[key] = base + ".jpg"
    return out


if __name__ == "__main__":
    write_maatstaat(os.path.join(ROOT, "Maatstaat", "Maatstaat_en_coordinaten.xlsx"))
    if len(sys.argv) > 1:
        update_rekenboek(sys.argv[1], os.path.join(ROOT, "Onderbouwing", "Rekenboek_herontwerp_bijgewerkt.xlsx"))
    tmp = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "build_tmp")
    write_docx(os.path.join(ROOT, "Onderbouwing", "Toelichting_SO_DO.docx"), figures(tmp))
    print("klaar")
