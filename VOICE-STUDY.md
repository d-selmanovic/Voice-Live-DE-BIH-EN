# Stimmenvergleich – Deutsch, Bosnisch, Englisch

## Testablauf

Alle Tester öffnen denselben Demo-Link und melden sich mit dem Zugangspasswort an.
Die App erzeugt einen persönlichen Testcode und merkt ihn auf dem Gerät.
Wer ein anderes Gerät verwendet, trägt dort denselben Code ein. Codes sind
selbst gewählte Kennungen, keine verifizierten Personenidentitäten.

1. Stimme und Testsprache wählen.
2. Gespräch starten, Antworten anhören und mindestens eine kurze Frage stellen.
3. Eine Stimme in genau der gewählten Sprache bewerten. Für eine andere Sprache
   oder Stimme Gespräch beenden und neu starten.
4. Aussprache, Verständlichkeit und Natürlichkeit jeweils von 1 bis 5 bewerten.
5. Optional konkrete Ausspracheprobleme beschreiben, ohne persönliche Daten.
6. Speichern und in der gemeinsamen Tabelle vergleichen.

Bewertungen sind nach einer serverseitig beobachteten Antwort möglich. Ein
geheimer Testnachweis bindet die Bewertung an die tatsächlich konfigurierte
Stimme, Sprache und Version. Browserdaten können diese Zuordnung nicht ändern.
Die App überprüft nicht, ob der Lautsprecher hörbar war oder ob ein Nutzer die
Testsprache während des Gesprächs gewechselt hat. Das ist eine Testanweisung.

## Auswertung

Pro Testcode, Stimme, Sprache und Version zählt die neueste Bewertung einmal.
Der Gesamtwert ist der gleichgewichtete Mittelwert der drei Kriterien; für die
Auswahl einer bosnischen Stimme wird nach Aussprache sortiert. Die Tabelle zeigt
die Anzahl eindeutiger Testcodes pro Stimme und Sprache, außerdem insgesamt.
Ein Tester kann mehrere Stimmen bewerten, ohne die Gesamtzahl der Tester zu erhöhen.
Das sind subjektive Bewertungen, keine garantierte akzentfreie Sprachqualität.

Änderungen an den Live-/Backend-Prompts oder konfigurierten Modellnamen erzeugen
automatisch eine andere Testversion. Alte Bewertungen bleiben gespeichert und
über die Versionsauswahl sichtbar. Änderungen am Verhalten eines gleichnamigen
Upstream-Modells sind damit nicht automatisch erkennbar. Bei Änderungen an
Bewertungsskala oder Auswertungsverfahren VERSION in voices.py erhöhen.

## Dauerhafte Speicherung auf Render

DATABASE_URL muss eine separate PostgreSQL-Datenbank erreichen. Keine Datenbank
im kostenlosen lokalen Render-Dateisystem verwenden. Ohne DATABASE_URL sind
Bewertungen auf Render deaktiviert und die UI zeigt den fehlenden Speicher an.
Für lokale Entwicklung ist SQLite ausreichend; Neustart desselben lokalen
Ordners behält Bewertungen. Die App initialisiert ausschließlich neue Tabellen
mit CREATE TABLE IF NOT EXISTS und löscht keine bestehenden Bewertungen.

Die Datenbank enthält gehashte Testcodes, Testzuordnungen, Bewertungen, Kommentare
und Bewertungsänderungen. Die Statistik zeigt keine Codes oder Kommentare an.
Audio und Gesprächsinhalte werden nicht in die Bewertungsdatenbank übertragen.
Der bisherige lokale Ticket-/Audit-Speicher bleibt unabhängig und auf Render
weiterhin flüchtig. Passwort und OPENAI_API_KEY bleiben in den Render-Einstellungen.

## Veröffentlichung und Rückkehr

Entwicklung: feature/voice-ratings. Bisheriger Live-Stand: Backup-Branch
backup/render-before-voice-selector und Tag
backup-render-2026-10-01-before-voice-selector (Commit 01c25a8).

Vor Veröffentlichung DATABASE_URL bei Render setzen, PostgreSQL-Anbindung prüfen
und den Entwicklungsbranch nach main übernehmen. Render deployt main automatisch.
Nach dem Deploy /healthz, Anmeldung, Statistik, zwei Tester mit derselben Stimme,
erneute Bewertung sowie Wechsel der Stimme/Sprache prüfen. API-Keys und
Datenbank-Verbindungsdaten niemals committen. Eine Rückkehr des App-Codes auf den
Backup-Stand löscht keine Bewertungstabellen der separaten Datenbank.

## Automatisierte Prüfung

python3 -m unittest discover -s tests -v
node --check public/app.js

Die Tests prüfen Login/Origin, sichere Tool-Bestätigung, persistente Bewertungen,
Mittelwerte ohne Mehrfachgewichtung, getrennte Sprachen/Versionen und gefälschte
Testnachweise. OpenAI wird im Integrationstest simuliert; echte Aussprache wird
von den Testern bewertet. Vor Veröffentlichung ist PostgreSQL zusätzlich mit
der echten Zielverbindung zu prüfen.
