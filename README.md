# Activi GPT-Live Voice Agent

Private, lokal startbare erste Version. Browser-Audio per WebRTC, GPT-Live für
Gespräche und ein Responses-Backend für Websuche und Demo-Tickets.
Implementiert nach der offiziellen Dokumentation vom 1. Oktober 2026.

## Starten

Python 3.11 oder neuer wird benötigt.

```bash
cd voice-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
```

Trage deinen OpenAI-Key in `.env.local` als `OPENAI_API_KEY` ein.
Der während der Einrichtung erstellte Key liegt in der ursprünglichen
Arbeitsumgebung eine Ebene darüber; er ist absichtlich nicht im ZIP enthalten.

```bash
python server.py
```

Öffne **http://localhost:3000**, drücke „Gespräch starten“ und erlaube das Mikrofon.
Die Oberfläche wird erst nach `session.started` als verbunden markiert.
OpenAI-API-Nutzung wird separat abgerechnet; ChatGPT Plus deckt sie nicht ab.

## Ausprobieren

- „Hallo, antworte mir auf Bosnisch.“
- „Suche aktuelle Informationen zu Pipecat und fasse sie kurz zusammen.“
- „Erstelle ein Demo-Ticket für Kunde Test: Mein Mikrofon funktioniert nicht.“
  Der Agent fragt fehlende Angaben ab. Bestätige den Entwurf im Browser.
- Lehne ein Ticket ab. Es darf nicht gespeichert werden.
- Setze eine offene Aufgabe zurück und beschreibe die Korrektur.
  Der alte Ticketentwurf darf nicht gespeichert werden.
- Schalte das Mikrofon aus und wieder ein; beende das Gespräch.

## Was enthalten ist

- Getrennte Live- und Backend-Prompts in `prompts.py`, Deutsch/Bosnisch/Englisch.
- Server hält API-Key und Tool-Ausführung; Sideband beobachtet echte API-Events.
- Gehostete Websuche; ein eng validiertes Demo-Ticket-Tool.
- Zustimmung über die authentifizierte Oberfläche, nicht über Modellargumente.
- SQLite für Demo-Tickets und Audit-Ereignisse; keine Audioaufzeichnungen.
- Sitzungsbesitz, Origin/Host-Prüfung, HttpOnly-Cookie, Rate Limits, Größenlimits.
- Auftragsrevision per „Aufgabe zurücksetzen“, Ablehnung veralteter Entwürfe.
- Keine automatischen Wiederholungen schreibender Aktionen. Operation-ID verhindert
  doppelte Speicherung bei demselben Tool-Aufruf.
- Alle Tool-Ergebnisse einer Response werden vor `response.create` zurückgegeben.
- 90 Sekunden Bestätigungsfrist, 10 Minuten maximale Gesprächsdauer,
  Session-Schließung mit finaler Usage oder protokolliertem fehlendem Abschluss.

## Tests

### Wenn HTTP 401 erscheint

OpenAI lehnt die Authentifizierung ab. Das ist kein Nachweis für fehlendes Guthaben.
Prüfe den aktiven, vollständigen API-Key in `voice-agent/.env.local`.
Die Zeile enthält `OPENAI_API_KEY=` gefolgt vom Key, ohne `Bearer `.
Der Key aus der ursprünglichen Arbeitsumgebung ist nicht im Download enthalten.
Eine bereits gesetzte Prozessvariable `OPENAI_API_KEY` hat Vorrang vor der Datei;
die Datei im Projektordner hat Vorrang vor einer Datei im übergeordneten Ordner.
Starte den Python-Server nach jeder Key-Änderung neu. Nur die Webseite neu zu laden
reicht nicht. Poste den Key nicht im Chat. Falls es weiter 401 gibt, prüfe
Key-Berechtigungen und konfigurierte IP-Freigaben im OpenAI-Projekt.

```bash
python -m unittest discover -s tests -v
node --check public/app.js
```

Validiert: Schemafehler, unzulässige Modellbestätigung, Idempotenz, Schutz vor
unberechtigtem Session-Zugriff, falsche Origin, Secrets als statische Dateien,
Zustimmung vor Schreiben und Revision während offener Zustimmung.
Die Tests benutzen keine kostenpflichtigen OpenAI-Aufrufe.

## Grenzen der ersten Version

Kein veröffentlichter Dienst, keine Telefonie, kein CRM und keine echte
Kundenidentitätsprüfung. Demo-Tickets sind nur lokale SQLite-Datensätze.
Revisionen werden ausdrücklich im Browser ausgelöst; automatische Erkennung
gesprochener Korrekturen und Stornierung laufender Suchaufträge sind nicht implementiert.
Gleiche Inhalte in unterschiedlichen, neu erzeugten Tool-Aufrufen können separate
Entwürfe ergeben; jeder benötigt eine eigene Zustimmung.
Browser-Captions verwenden Event-IDs, sofern vorhanden, sonst fortlaufenden Text.
Kein Audio-Playback-Guardrail: das Backend kann bereits ausgegebene Sprache nicht
zurücknehmen. Eine unterbrochene Audioverbindung wird beendet und muss neu gestartet werden.

Vor Produktion fehlen reale Audiotests (Barge-in, Mehrsprachigkeit, Echo),
Jeff-Auswertung, p50/p95-Latenzen, Kostenvergleich, Lasttest und ein Betriebskonzept.
Ein erreichter 80-%-Jeff-Wert wird nicht behauptet.

Der neue Key wurde erstellt; Zugriff auf GPT-Live und Guthaben müssen durch eine
echte Session geprüft werden. Ein durchgängiger Live-Test konnte in der
Erstellungsumgebung wegen eingeschränkter Netzwerkverbindungen nicht erfolgen.

## Privater Serverbetrieb

Für Zugriff außerhalb localhost: HTTPS-Reverse-Proxy, `APP_ORIGIN` mit exaktem
Hostnamen, `HOST=0.0.0.0`, starkes `APP_PASSWORD`. Der Server verweigert Remote-Bindung
ohne Passwort und HTTPS-Origin. Ein Passwort entspricht einem einzelnen Betreiber,
nicht einer vollständigen Benutzerverwaltung. Für Produktion OIDC und zentrale
Session-/Rate-Limit-Verwaltung ergänzen. Keine offene öffentliche Freigabe.

`data/agent.sqlite` enthält Transkriptfragmente, Auditdaten und Demo-Tickets.
Dateizugriff begrenzen, Retention festlegen und Backups verschlüsseln.
Das selbst gehostete Backend ersetzt nicht die Verarbeitung von Audio bei OpenAI;
EU-Datenhaltung ist mit diesem Paket allein nicht zugesichert.

## Quellen

- https://developers.openai.com/api/docs/guides/live
- https://developers.openai.com/api/docs/guides/voice-webrtc
- https://developers.openai.com/api/docs/guides/live-delegation
- https://developers.openai.com/api/docs/guides/voice-server-controls
