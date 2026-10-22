# Havenontwerp Groep 1: schetsontwerp en definitief ontwerp

Atelier De Haven A, NHL Stenden. Haven voor containers, graan, voertuigen (RoRo), LNG en een gascentrale, met het
Porto Central-masterplan als vormreferentie.
**Locatie: Porto Central, Presidente Kennedy - Espírito Santo, 29350-000, Brazilië.** Alles staat in **SIRGAS 2000 / UTM zone 24S (EPSG:31984), meter**.

## Opgeleverd

| Map / bestand | Inhoud |
|---|---|
| `CAD/Haven_SO.dxf` | Schetsontwerp (SO) in projectcoördinaten, lagen `HV-*`, luchtfoto als gekoppeld beeld, A1-layout 1:10.000 |
| `CAD/Haven_DO.dxf` | Definitief ontwerp (DO): de Porto Central-render op schaal overgetrokken, met maatvoering, fasegrenzen, ankerpunten en de render op laag `HV-REFERENTIE` (uit) |
| `CAD/Haven_DO_geul_ontwerpbodem.xml` | LandXML voor Civil 3D: geulas (Alignment) en ontwerpbodem −18,20 m MLWS (TIN-oppervlak) |
| `Referentie/` | Porto Central-render (basis DO) en uitsnede masterplan 2016 p. 9 |
| `CAD/Ondergrond/` | Sentinel-2 luchtfoto 03-07-2026 (JPG + `.jgw` + `.prj`), waterlijn en GSHHS-kust (JSON) |
| `PDF/Haven_SO.pdf` | SO-01 overzicht 1:40.000 · SO-02 havenindeling 1:10.000 · SO-03 bespreekpunten |
| `PDF/Haven_DO.pdf` | DO-01 overzicht · DO-02 havenplan 1:15.000 · DO-03 fasering 1:30.000 · DO-04 maatstaat en georeferentie · DO-05 overtrek render op luchtfoto |
| `Maatstaat/Maatstaat_en_coordinaten.xlsx` | Maatstaat, ankerpunten (E/N + lat/lon), georeferentie, kustcontrole, besluitenlijst SO→DO |
| `Onderbouwing/Rekenboek_herontwerp_bijgewerkt.xlsx` | Rekenboek met de gemeten tekenmaten teruggevoerd (Nautiek D31, Grondwerk C6/D21, Invoer, Keuzes K17–K29, tabblad `Tekening_DO`) |
| `Onderbouwing/Toelichting_SO_DO.docx` | Toelichting: ondergrond, ligging, SO, bespreking en besluitenlijst, DO, open punten, werkwijze in Civil 3D |
| `webkaart/index.html` | Interactieve Leaflet-kaart met SO en DO op luchtfoto (dubbelklikken of via GitHub Pages) |

## DWG maken in Civil 3D

1. Kopieer de map `CAD` inclusief `Ondergrond` (de luchtfoto is met een relatief pad gekoppeld).
2. Open `Haven_DO.dxf` en `Haven_SO.dxf` en stel bij *Drawing Settings > Units and Zone* `SIRGAS2000.UTM-24S` en meter in.
   Je hoeft niets te verschuiven: de objecten staan al op projectcoördinaten. Zet laag `HV-REFERENTIE` aan om de render als overtrek te zien.
3. Zet *Map Aerial* aan ter controle en leg het beeld vast met `GEOMAPIMAGE`.
4. *Insert > Import LandXML*: `Haven_DO_geul_ontwerpbodem.xml` (geulas en ontwerpbodem voor de baggervolumes).
5. Sla op met `SAVEAS` als `Haven_DO.dwg` en `Haven_SO.dwg`. De layout `DO-02 A1 1-10000` plot je direct naar PDF.

## Belangrijkste maten (DO)

* Geul 220 m bodembreedte, −18,20 m MLWS. Lengte buiten de mond is voorlopig 10.000 m: het eindpunt moet nog op de −18,2 m-lijn van de bathymetrie komen.
* Havenmond 350 m vrij tussen de golfbrekerfootprints. Vrije draaikom D 720 m. Stopweg van mond tot draaikom 1.700 m (5,1 LOA). Sleepbootkoppelpunt 1.500 m buiten de mond.
* Het DO is de Porto Central-render, overgetrokken op 10,035 m per pixel en 10° gedraaid op de kust (kustfit gemiddeld 31 m). Blad DO-05 toont de render op de luchtfoto met het DO erop.
* Containervinger (6) 144 ha met 1.600 m kraankade aan het insteekbekken (fasen 72 / 108 / 144 ha), graan 30 ha aan de noordkade (10), RoRo 30 ha op vinger 7/8, havendiensten op de noordoosthoek.
* Tankpark langs de zuidrand (9): LNG-zone met 3 × 180.000 m³ en ruimte voor een 4e tank, centrale ernaast. LNG-steiger (18) achter de zuidelijke dam.
* Olie- en droge-bulksteigers (4, 5) vallen buiten het programma en zijn weggelaten; erts, werf en industrie zijn reserveterrein.

## Reproduceren

```
pip install ezdxf pyproj shapely matplotlib rasterio scikit-image pikepdf python-docx openpyxl basemap-data-hires
python3 src/01_ondergrond_ophalen.py <map>     # Sentinel-2 uitsnede (AWS Open Data)
python3 src/02_kustlijn_ndwi.py <map>          # waterlijn uit NDWI
python3 src/03_kustcontrole_gshhs.py <map>     # onafhankelijke kustcontrole
python3 src/haven.py                           # DXF, PDF, GeoJSON, maatstaat.json
python3 src/documenten.py <Rekenboek_herontwerp.xlsx>   # maatstaat, rekenboek, toelichting
```

De geometrie staat op één plek (`src/haven.py`, functies `build_so` en `build_do`) in een lokaal havenstelsel
(u = zeewaarts langs de havenas, azimut 110°; v = langs de kust). Eén vaste transformatie zet dat stelsel om naar EPSG:31984.

Bron luchtfoto: Copernicus Sentinel-2 L2A (ESA), tegels 24KTB en 24KUB, opname 03-07-2026.
