# Havenontwerp Groep 1: schetsontwerp en definitief ontwerp

Atelier De Haven A, NHL Stenden. Haven voor containers, graan, voertuigen (RoRo), LNG en een gascentrale, met het
Porto Central-masterplan als vormreferentie.
**Locatie: Porto Central, Presidente Kennedy - Espírito Santo, 29350-000, Brazilië.** Alles staat in **SIRGAS 2000 / UTM zone 24S (EPSG:31984), meter**.

## Opgeleverd

| Map / bestand | Inhoud |
|---|---|
| `CAD/Haven_SO.dxf` | Schetsontwerp (SO) in projectcoördinaten, lagen `HV-*`, luchtfoto als gekoppeld beeld, A1-layout 1:10.000 |
| `CAD/Haven_DO.dxf` | Definitief ontwerp (DO): de Porto Central-render op schaal overgetrokken, met maatvoering, fasegrenzen, ankerpunten en de render op laag `HV-REFERENTIE` (uit) |
| `CAD/Haven_DO_geul_ontwerpbodem.xml` | LandXML voor Civil 3D: geulas (Alignment) en ontwerpbodem per dieptezone (−18,20 / −16,20 / −13,70 m MLWS) |
| `Referentie/` | Porto Central-render (basis DO) en uitsnede masterplan 2016 p. 9 |
| `CAD/Ondergrond/` | Sentinel-2 luchtfoto 03-07-2026 (JPG + `.jgw` + `.prj`), waterlijn en GSHHS-kust (JSON), bestaand bodemmodel `bestaand_bodem_MLWS_EPSG31984.tif` (GEBCO 2026 + Copernicus DEM, 30 m) |
| `PDF/Haven_SO.pdf` | SO-01 overzicht 1:40.000 · SO-02 havenindeling 1:10.000 · SO-03 bespreekpunten |
| `PDF/Haven_DO.pdf` | DO-01 overzicht · DO-02 havenplan 1:15.000 · DO-03 fasering 1:30.000 · DO-04 maatstaat en georeferentie · DO-05 overtrek render · DO-06 containerterminal 1:5.000 · DO-07 graan, RoRo, havendienst 1:6.000 · DO-08 LNG en centrale 1:8.000 · DO-09 golftoets ligplaatsen 1:14.000 · DO-10 toegangsgeul, bodemprofiel en grondwerk 1:75.000 |
| `Maatstaat/Maatstaat_en_coordinaten.xlsx` | Maatstaat, ankerpunten (E/N + lat/lon), georeferentie, kustcontrole, besluitenlijst SO→DO |
| `Onderbouwing/Rekenboek_herontwerp_bijgewerkt.xlsx` | Rekenboek met de gemeten tekenmaten teruggevoerd (Nautiek D31, Grondwerk C6/D21, Invoer, Keuzes K17–K29, tabblad `Tekening_DO`) |
| `Onderbouwing/Toelichting_SO_DO.docx` | Toelichting: ondergrond, ligging, SO, bespreking en besluitenlijst, DO, open punten, werkwijze in Civil 3D |
| `webkaart/index.html` | Interactieve Leaflet-kaart met SO en DO op luchtfoto (dubbelklikken of via GitHub Pages) |

## Tekenbladen (NHL Stenden-template)

Alle bladen (PDF en de DXF-layouts) volgen layout `A1_841x594` van `Template_NHL_Stenden_v1.dwt`: A1-tekenblad,
hoofdviewport (30-621 x 30-574 mm), onderschrift met schaal, legendavak, overzichtskaartje (1:200.000) met de
uitsnede van het blad in rood, wijzigingsblok en `TITELBLOK_NHL` met het NHL Stenden-logo. De onderdelen staan in
`Referentie/NHL_template_onderdelen.dxf`; het logo (in het template een OLE-object) als `Referentie/nhl_logo.png`.
Teksten worden automatisch geplaatst zonder overlap (`src/labels.py`, `src/annotatie.py`): horizontaal of leesbaar
langs de maatlijn, met een verwijslijn als er in het vlak geen ruimte is; NLCS-hoogtes 1,8 / 2,5 / 3,5 mm.
In de DXF staan de teksten van het havenplan in Model (laag `HV-TEKST-02`); de teksten van de detailbladen staan in
de layout van dat blad, zodat Model rustig blijft. Ankerpunten staan alleen in de maatstaat (DO-04).

## Golftoets op een aangepaste DXF

`Haven_DO.dxf` bevat de invoer voor de golftoets op lagen `HV-TOETS-*` (in de layouts bevroren):
`HV-TOETS-OPENING-1-MOND`, `-2-HOOFDBEKKEN`, `-3-INSTEEK` (openingen van zee naar binnen),
`HV-TOETS-WAND-<VH|HB|INS>-<KADE|OPEN|TALUD>` (reflecterende wanden; Cr 0,9 / 0,45 / 0,4) en
`HV-TOETS-LIGPLAATS-<CONTAINERS|GRAAN|RORO|LNG>` (hartlijn van elk schip). Verschuif deze lijnen mee als je in
Civil 3D dammen, kades of ligplaatsen aanpast, sla op als DXF en draai:

```
python3 src/toets_dxf.py CAD/Haven_DO.dxf
```

Uitvoer naast de DXF: `<naam>_golftoets.pdf` (tabel en kleurenkaart) en `<naam>_met_golftoets.dxf`
(golfhoogte-contouren 0,3 / 0,5 / 1,0 / 1,5 / 2,0 m op lagen `HV-GOLF-HS-112_5` en `HV-GOLF-HS-45_0`).

## DWG maken in Civil 3D

1. Kopieer de map `CAD` inclusief `Ondergrond` (de luchtfoto is met een relatief pad gekoppeld).
2. Open `Haven_DO.dxf` en `Haven_SO.dxf` en stel bij *Drawing Settings > Units and Zone* `SIRGAS2000.UTM-24S` en meter in.
   Je hoeft niets te verschuiven: de objecten staan al op projectcoördinaten. Zet laag `HV-REFERENTIE` aan om de render als overtrek te zien.
3. Zet *Map Aerial* aan ter controle en leg het beeld vast met `GEOMAPIMAGE`.
4. *Insert > Import LandXML*: `Haven_DO_geul_ontwerpbodem.xml` (geulas en ontwerpbodem per dieptezone). Lees `Ondergrond/bestaand_bodem_MLWS_EPSG31984.tif` in als bestaand oppervlak (*Create Surface from DEM*) en vergelijk in het Volumes Dashboard.
5. Sla op met `SAVEAS` als `Haven_DO.dwg` en `Haven_SO.dwg`. De layout `DO-02 A1 1-10000` plot je direct naar PDF.

## Belangrijkste maten (DO)

* Geul 220 m bodembreedte, −18,20 m MLWS: 2,5 km recht vanaf de mond, bocht R 3.400 m naar 145°, dan recht tot de natuurlijke −18,2 m MLWS (GEBCO 2026): ca. 20 km buiten de mond in plaats van 35 km rechtdoor. Geen peiling: indicatief.
* Dieptezones (diepgang + 3,7 m): containers, graan en geul −18,20; LNG-vaarweg en -ligplaats −16,20; RoRo −13,70 m MLWS. Baggervolumes per vak in DO-10 (celmethode, indicatief).
* Golftoets (diffractie + reflectie, Hs buiten 2,5 m): alle ligplaatsen voldoen met open graan-/havendienstkade, RoRo dieper in de insteek en LNG op de gunstigste plek langs de dam (DO-09).
* LNG: 250 m veiligheidszone rond schip/steiger en tanks, 500 m nautische controlezone (indicatief, QRA volgt).
* Havenmond 350 m vrij tussen de golfbrekerfootprints. Vrije draaikom voorhaven D 720 m, zwaaiplaats binnenhaven D 670 m (2 × LOA). Stopweg van mond tot draaikom 1.700 m (5,1 LOA). Sleepbootkoppelpunt 1.500 m buiten de mond.
* Het DO is de Porto Central-render, overgetrokken op 10,035 m per pixel en 10° gedraaid op de kust (kustfit gemiddeld 31 m). Blad DO-05 toont de render op de luchtfoto met het DO erop.
* Containervinger (6) 144 ha met 1.600 m kraankade aan het insteekbekken (fasen 72 / 108 / 144 ha), graan 30 ha aan de noordkade (10), RoRo 30 ha op vinger 7/8, havendiensten op de noordoosthoek.
* Tankpark langs de zuidrand (9): LNG-zone met 3 × 180.000 m³ en ruimte voor een 4e tank, centrale ernaast. LNG-steiger (18) achter de zuidelijke dam.
* Vorm van de render (dammen, hoofdbekken, twee vingers met insteekbekkens, tankpark) met alleen functies uit de opdracht. Containerkade aan de westzijde van vinger 6 in het insteekbekken (beschut tegen golven).

## Reproduceren

```
pip install ezdxf pyproj shapely matplotlib rasterio scipy scikit-image pikepdf python-docx openpyxl basemap-data-hires
python3 src/01_ondergrond_ophalen.py <map>     # Sentinel-2 uitsnede (AWS Open Data)
python3 src/02_kustlijn_ndwi.py <map>          # waterlijn uit NDWI
python3 src/03_kustcontrole_gshhs.py <map>     # onafhankelijke kustcontrole
python3 src/04_gebco_ophalen.py; python3 src/05_copdem_ophalen.py; python3 src/bodem.py <gebco.tif> <copdem.tif>   # bodemmodel
python3 src/haven.py                           # DXF, PDF, GeoJSON, maatstaat.json
python3 src/documenten.py <Rekenboek_herontwerp.xlsx>   # maatstaat, rekenboek, toelichting
```

De geometrie staat op één plek (`src/haven.py`, functies `build_so` en `build_do`) in een lokaal havenstelsel
(u = zeewaarts langs de havenas, azimut 110°; v = langs de kust). Eén vaste transformatie zet dat stelsel om naar EPSG:31984.

Bron luchtfoto: Copernicus Sentinel-2 L2A (ESA), tegels 24KTB en 24KUB, opname 03-07-2026.
