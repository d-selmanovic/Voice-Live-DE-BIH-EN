# Die Voice-Demo auf Render veröffentlichen

Das Paket ist vorbereitet, aber noch nicht online. Zuerst muss ein Render-Konto
verbunden und ein Quellcode-Repository angelegt bzw. ausgewählt werden.

## Einfacher Weg

1. Erstelle ein privates GitHub-Repository und lade den INHALT des Ordners
   `voice-agent` hoch. `server.py` und `render.yaml` müssen direkt im
   Repository-Hauptverzeichnis liegen. Keine `.env.local`, Keys oder `data/` hochladen.
2. Melde dich unter https://dashboard.render.com an und verbinde dein GitHub-Konto.
3. Wähle **New → Blueprint** und das Repository. Render liest `render.yaml`.
4. Trage bei der Einrichtung ein:
   - `OPENAI_API_KEY`: deinen funktionierenden OpenAI-Key, ohne „Bearer “.
   - `APP_PASSWORD`: ein eigenes Testpasswort mit mindestens 12 Zeichen.
5. Starte die Bereitstellung. Verwende zunächst den vorbereiteten Free-Plan.
6. Sobald Render „Live“ anzeigt, öffne die von Render angezeigte HTTPS-Adresse.
7. Melde dich mit deinem Testpasswort an und teste ein Sprachgespräch.
8. Gib die HTTPS-Adresse und das Testpasswort an deine Tester weiter.
   Der API-Key wird nicht an die Tester weitergegeben.

## Falls du manuell einen Web Service anlegst

| Einstellung | Wert |
|---|---|
| Runtime | Python |
| Region | Frankfurt |
| Plan | Free für erste Tests |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python server.py` |
| Health Check Path | `/healthz` |
| HOST | `0.0.0.0` |
| OPENAI_API_KEY | Direkt bei Render eintragen |
| APP_PASSWORD | Eigenes Passwort mit mindestens 12 Zeichen |

Die App übernimmt ihre HTTPS-Adresse automatisch aus `RENDER_EXTERNAL_URL` und
den Port aus `PORT`. Keine localhost-Adresse bei Render eintragen.
Es läuft genau ein Python-Prozess; keine zusätzlichen Gunicorn-Worker oder
mehrere Instanzen für diese Demo konfigurieren.

## Prüfen nach Veröffentlichung

- Öffne den Link in einem privaten Browserfenster. Ohne Anmeldung dürfen keine
  Voice-Sessions erstellt werden.
- Falsches Passwort muss abgelehnt werden. Richtiges Passwort erlaubt den Start.
- Mikrofon erlauben, „Hallo“ sagen, Antwort anhören und den Agenten unterbrechen.
- Ein Demo-Ticket vorbereiten; Ablehnen darf nichts speichern. Bestätigen legt
  einen lokalen Demo-Datensatz an.
- „Aufgabe zurücksetzen“ verwirft eine offene Ticketbestätigung.
- „Beenden“ stoppt die Session. Nach spätestens zehn Minuten endet sie automatisch.
- Bei HTTP 401 den bei Render eingetragenen Key prüfen und erneut deployen.

## Grenzen des kostenlosen Tests

Render Free geht nach Inaktivität schlafen. Beim nächsten Öffnen kann der Start
ungefähr eine Minute dauern. Demo-Tickets und Auditdaten im lokalen SQLite-Speicher
gehen bei Neustart, Ruhezustand oder erneutem Deploy verloren. Für erste
Funktionstests ist das vorgesehen; für dauerhafte Testdaten später eine bezahlte
Instanz mit Persistent Disk oder eine externe Datenbank einrichten.
Die OpenAI-API-Nutzung bleibt kostenpflichtig, auch wenn das Hosting kostenlos ist.
Die Demo ist per URL erreichbar und durch ein gemeinsames Passwort geschützt;
sie ist keine vollständige Benutzerverwaltung.

## Quellen

- https://render.com/docs/blueprint-spec
- https://render.com/docs/environment-variables
- https://render.com/docs/free
- https://render.com/docs/configure-environment-variables
