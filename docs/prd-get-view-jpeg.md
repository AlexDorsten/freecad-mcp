# PRD: JPEG-Unterstützung für alle Screenshot-Funktionen (PNG bleibt Default)

## 1. Hintergrund
- Aktuell liefern Screenshot-Antworten immer `image/png` zurück.
- Die Kodierung ist in der MCP-Server-Schicht hart auf PNG gesetzt:
  - `get_view` gibt `mimeType="image/png"` zurück.
  - `add_screenshot_if_available` nutzt ebenfalls `image/png`.
- Es existiert derzeit keine Teststruktur im Repository (`tests/` fehlt).

Relevante Stellen:
- `src/freecad_mcp/server.py` (`get_view`, CLI-Flags, MIME-Type-Setzung)
- `addon/FreeCADMCP/rpc_server/rpc_server.py` (Screenshot-Erzeugung via FreeCAD GUI)

## 2. Problemstellung
- Nutzer wollen optional JPEG-Ausgabe für alle Screenshot-Rückgaben, um Payload/Tokenkosten zu reduzieren.
- PNG soll weiterhin Standard bleiben (abwärtskompatibel).
- Es soll nachgewiesen werden, dass JPEG-Screenshots bei sinnvoller Kompression weiterhin hochwertige visuelle Resultate liefern.

## 3. Ziele
- Optionales globales Umschalten von PNG auf JPEG für alle Screenshot-Rückgaben.
- Default-Verhalten unverändert: PNG.
- Definierte Qualitätsgrenze für JPEG, damit Screenshots in CAD-Workflows zuverlässig nutzbar bleiben.
- Automatisierte Tests für Funktion und Qualitätsnähe.

## 4. Nicht-Ziele
- Keine UI-Änderungen im FreeCAD-Addon.
- Keine Änderung der eigentlichen CAD-Geometrie-/Objektlogik.

## 5. Anforderungen

### 5.1 Funktional
1. Neuer optionaler CLI-Flag, ähnlich `--only-text-feedback`, für `get_view`-Bildformat.
2. Unterstützte Formate in v1:
   - `png` (Default)
   - `jpeg` (optional)
3. Bei JPEG-Ausgabe muss für alle Screenshot-Antworten korrekt `mimeType="image/jpeg"` gesetzt werden.
4. Falls JPEG-Konvertierung fehlschlägt, soll robust auf PNG zurückgefallen werden (mit Warning-Log).

### 5.2 Qualitätsanforderung
1. JPEG-Qualität in v1 als fester Wert (Empfehlung: `92`).
2. JPEG-Resultate sollen in objektiven Metriken nahe PNG liegen:
   - PSNR >= 38 dB gegen PNG-Referenz
   - Visuelle Kanten/Labels bleiben lesbar (manueller Gate-Test)
3. Dateigröße gegenüber PNG soll im Mittel signifikant sinken (Zielwert: mindestens 20% Reduktion auf Referenz-Set).

### 5.3 Abwärtskompatibilität
1. Bestehende Nutzer ohne neuen Flag erhalten unverändert PNG.
2. Bestehende Integrationen, die `image/png` erwarten, bleiben unverändert solange JPEG-Flag nicht gesetzt ist.
3. `--only-text-feedback` hat Vorrang und unterdrückt weiterhin Bildantworten vollständig.

## 6. UX / CLI-Design

### 6.1 Flag-Design (v1)
- Empfohlen:
  - `--jpeg-screenshots`
- Verhalten:
  - nicht gesetzt => alle Screenshot-Antworten liefern PNG
  - gesetzt => alle Screenshot-Antworten liefern JPEG

Alternative:
- `--screenshot-format {png,jpeg}` (erweiterbarer, aber etwas ausführlicher)

### 6.2 Kompression (v1)
- Empfehlung: **fester Qualitätswert** statt user-konfigurierbarer Rate.
- Initialwert: `JPEG_QUALITY = 92`.
- Begründung:
  - einfachere Bedienung
  - weniger Fehlkonfiguration
  - reproduzierbare Ergebnisse im Test

## 7. Technisches Design

## 7.1 Architekturentscheidung
- **v1-Konvertierung in MCP-Schicht** (`src/freecad_mcp/server.py`), nicht im FreeCAD-Addon:
  1. RPC liefert wie bisher PNG-base64.
  2. Bei aktivem JPEG-Flag wird PNG -> JPEG umgewandelt.
  3. Rückgabe mit passendem MIME-Type für alle screenshot-liefernden Tools.

Vorteile:
- Keine Protokolländerung RPC.
- Keine Abhängigkeit von FreeCAD-internem JPEG-Encoder-Verhalten.
- Kontrollierte Qualität über festen Wert.

Nachteile:
- Neue Python-Abhängigkeit für Bildkonvertierung (Pillow) im MCP-Package.

## 7.2 Konkrete Codeänderungen
1. `src/freecad_mcp/server.py`
   - Neue globale Konfiguration:
     - `_use_jpeg_screenshots: bool = False`
     - `DEFAULT_JPEG_QUALITY = 92`
   - Neues CLI-Argument:
     - `--jpeg-screenshots` (store_true)
   - Helper für Konvertierung:
     - `convert_png_base64_to_jpeg_base64(data_b64: str, quality: int = 92) -> str`
   - `add_screenshot_if_available` und `get_view`:
     - bei Flag aus: unverändert PNG
     - bei Flag an: Konvertierung + `mimeType="image/jpeg"`
     - Fallback auf PNG bei Fehler
2. `pyproject.toml`
   - Dependency ergänzen: `Pillow` (Runtime), da Konvertierung im MCP-Prozess läuft.
3. `README.md`
   - Neuer Abschnitt zum Flag inkl. Beispielkonfiguration.
   - Hinweis: PNG bleibt Standard.
   - Dokumentation: Flag wirkt auf `get_view`, `create_object`, `edit_object`, `delete_object`, `execute_code`, `insert_part_from_library`, `get_objects`, `get_object`.
4. Laufzeit-Metriken (MCP-Server-Logs)
   - Bei jeder JPEG-Konvertierung Logeintrag mit:
     - `png_kb`, `jpeg_kb`, `saved_kb`, `saved_percent`
   - Formatbeispiel:
     - `JPEG screenshot converted: png_kb=512.4 jpeg_kb=141.7 saved_kb=370.7 saved_percent=72.3`
   - Vorteil:
     - keine API-Änderung, keine zusätzlichen Tokens im Tool-Response.

## 8. Teststrategie

## 8.1 Test-Setup
- Neue Teststruktur mit `pytest`:
  - `tests/test_get_view_image_format.py`
  - `tests/fixtures/` mit 2-3 CAD-ähnlichen Referenzbildern (Linien, Kanten, kleine Beschriftungen, Farbflächen).

## 8.2 Unit-Tests
1. Screenshot-Tools ohne Flag:
   - MIME ist `image/png`.
2. Screenshot-Tools mit JPEG-Flag:
   - MIME ist `image/jpeg`.
   - base64 decodierbar.
3. Fehlerpfad:
   - Bei Konvertierungsfehler Fallback zu PNG + Warning-Log.
4. Keine Regression:
   - `--only-text-feedback` Verhalten bleibt unverändert.

Hinweis: Für deterministische Tests wird `get_freecad_connection().get_active_screenshot` gemockt (keine FreeCAD-Laufzeit nötig).

## 8.3 Qualitäts-/Vergleichstests (automatisiert)
1. Fixture-PNGs werden via Konvertierungsfunktion zu JPEG verarbeitet.
2. Metriken:
   - PSNR pro Bild gegen PNG-Referenz.
   - Dateigrößenvergleich PNG vs JPEG.
3. Akzeptanz:
   - PSNR >= 38 dB für alle Fixtures.
   - Durchschnittliche Dateigrößenreduktion >= 20%.

## 8.4 Manueller FreeCAD-Abnahmetest
1. Identische Szene in FreeCAD öffnen.
2. `get_view` einmal in PNG, einmal in JPEG erfassen.
3. Prüfen:
   - Lesbarkeit kleiner Kanten/Skizzenlinien
   - Artefakte an Kontrastkanten
   - subjektive Gleichwertigkeit für Modellinterpretation
4. Dokumentation mit Vorher/Nachher-Beispielen.

## 8.5 Persistente Ergebnisdokumentation (Ersparnis)
1. Testlauf erzeugt einen kleinen Report:
   - `docs/reports/jpeg-savings.md`
2. Inhalt:
   - Tabelle pro Fixture (`png_kb`, `jpeg_kb`, `saved_kb`, `saved_percent`, `psnr_db`)
   - Mittelwerte über alle Fixtures
3. Zweck:
   - Nachvollziehbare, versionierbare Evidenz der Ersparnis und Qualitätsnähe für PRs.

## 9. Rollout-Plan
1. Implementierung + Unit-Tests.
2. Qualitätstests auf Fixture-Set.
3. Manueller FreeCAD-Gate-Test.
4. Merge hinter optionalem Flag (Default unverändert).

## 10. Risiken und Gegenmaßnahmen
- Risiko: JPEG-Artefakte bei dünnen CAD-Linien.
  - Maßnahme: konservative Qualität 92 + PSNR-Gate + manueller Check.
- Risiko: Zusätzliche Runtime-Dependency.
  - Maßnahme: minimale, etablierte Library (Pillow), klar in `pyproject.toml` dokumentieren.
- Risiko: Verwechslung, ob Flag global oder nur `get_view`.
  - Maßnahme: klar im README und in Help-Texten als globales Screenshot-Flag spezifizieren.

## 11. Dependency-Optionen für JPEG-Konvertierung
1. Option A: `Pillow` in MCP-Schicht (empfohlen)
   - Vorteile:
   - stabile, weit verbreitete Bildkonvertierung
   - kontrollierbare JPEG-Qualität (z. B. 92)
   - volle Kontrolle über MIME/Output, unabhängig von FreeCAD-Interna
   - Nachteile:
   - zusätzliche Runtime-Dependency
   - minimal mehr CPU für PNG->JPEG-Konvertierung im MCP-Prozess
2. Option B: JPEG direkt im FreeCAD-RPC speichern (Dateiendung `.jpg`)
   - Vorteile:
   - keine neue Dependency im MCP-Paket
   - potenziell weniger Konvertierungsschritte
   - Nachteile:
   - Qualitätseinstellung evtl. nicht steuerbar (abhängig von FreeCAD/Qt-Save-API)
   - Verhalten kann FreeCAD-/Qt-versionsabhängig sein
   - MIME-/Format-Konsistenz muss sorgfältig abgesichert werden
3. Option C: Externes Tool wie ImageMagick (`convert`)
   - Vorteile:
   - gute Qualität/Kontrolle möglich
   - Nachteile:
   - externe Systemabhängigkeit (Installationsaufwand, Portabilität schlechter)
   - mehr Betriebs-/CI-Komplexität als `Pillow`
