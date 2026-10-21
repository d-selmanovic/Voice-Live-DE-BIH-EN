# Lena – Einrichtung, Rechte und Übergabe

Stand: 21.10.2026. Diese Änderung ergänzt den bestehenden OpenAI-Live-Sprachtest um Connectoren. Lena ist damit noch kein freigeschalteter Telefonanschluss. Echte Kandidaten erst nach der unten genannten Abnahme anschließen.

## Architektur und Laufzeit
Browser → passwortgeschützter aiohttp-Server → OpenAI Live gpt-live-1 → Responses-Backend gpt-6-luna → serverseitige Connector-Funktionen. Die Browser-Freigabe ist die Zustimmung des Team-Operators. Kandidaten bekommen diese Oberfläche und die Speicher- und Verwaltungstools nicht. Bestehende SDK-/Deployment-Manager-Vorarbeiten der separaten Agentenplattform bleiben davon getrennt.

Supermemory wird direkt per HTTP-API angebunden. Chatwoot verwendet eine direkte API und einen signierten AgentBot-Webhook. Linear wird durch einen eingeschränkten MCP-Client im Backend angebunden; Render bewahrt nur seine Konfiguration/Geheimnisse auf. Composio ist dafür nicht notwendig. Codex-Skills helfen bei Entwicklung und Prüfung; sie sind keine automatisch im Sprachmodell laufenden Plugins.

## Verbindungen und Konfiguration
Geheime Werte ausschließlich in der privaten lokalen Eingabedatei beziehungsweise den Render-Umgebungsvariablen. `.env.example` enthält nur Platzhalter. OPENAI_API_KEY, APP_PASSWORD, DATABASE_URL nicht beim Ergänzen überschreiben. Nie Tokens, Webhook-Pfadtoken oder Signaturen in Tickets/Logs/Repository speichern.

| Dienst | Benötigte Werte | Verhalten |
| --- | --- | --- |
| Supermemory | SUPERMEMORY_API_KEY, offizielle Basis-URL | Bestehende Bereiche automatisch vollständig ermitteln; kein fester fachlicher Namespacefilter. |
| Chatwoot | BASE_URL, ACCOUNT_ID, API_TOKEN, TEST_INBOX_ID=12 | Ausschließlich Inbox12, bestehender Bot2. |
| Bot-Eingang | WEBHOOK_ENABLED, zufälliger WEBHOOK_PATH_TOKEN, WEBHOOK_SIGNING_SECRET | HMAC-SHA256 über timestamp.raw, Zeitfenster5min; dauerhafte Queue vor Bestätigung. |
| Linear | MCP_ACCESS_TOKEN, ALLOWED_TEAM_ID, ALLOWED_PROJECT_ID | Ohne alle drei Werte keine Linear-Tools und keine Linear-Schreibzugriffe. |
| Tracing | technische JSON-Ereignisse in Render-Logs | Keine Audios, Transkripte, Suchinhalte, Dateiinhalte, Tokens oder Tool-Argumente in Traces. Externer Trace-Dienst noch nicht verbunden. |
| Dauerhafter Eingang | DATABASE_URL | PostgreSQL-Queue enthält nur IDs und Bearbeitungszustände. Render ohne DB aktiviert keinen Webhook-Worker. |

Die bestehende persönliche Chatwoot-CLI-Anmeldung funktioniert. Der Bot2-Zugriffstoken lieferte401. Vor echtem Betrieb ist ein eigener technischer Benutzer mit passenden Inboxrechten nötig. Die serverseitige Inboxprüfung begrenzt Lenas Tools, reduziert aber nicht die Berechtigungen des zugrunde liegenden persönlichen Tokens.

## Supermemory und alle bestehenden Bereiche
Die API meldet9275 Namespaces. v5 sucht jeweils einen Namespace. Der alte Suchendpunkt ohne containerTags lieferte hier leere Ergebnisse, obwohl v5 vorhandene Daten fand; eine einzelne Abfrage mit allen9275 Tags scheiterte mit503. Das ist kein belastbarer globaler Suchweg.

Deshalb werden alle bestehenden Bereiche seitenweise entdeckt, Vollständigkeit geprüft und zehn Minuten im Prozess zwischengespeichert. Das Backend findet mit memory_contexts den passenden bestehenden Kontext anhand von Kontakt/Thema und sucht über die aktuelle v5-API darin. Alle Bereiche sind zugänglich; es gibt keinen festen Konfigurationsfilter und der Nutzer muss keinen Namespace in der Einrichtung eintragen. Das Modell darf keine IDs erfinden. Eine konkrete Suchantwort betrifft den gewählten Bereich und wird ausdrücklich nicht als vollständige Suche in allen9275 Bereichen ausgegeben. Eine vollständige parallele Suche würde viele kostenpflichtige Suchaufrufe und erhebliche Voice-Latenz verursachen und ist nicht stillschweigend aktiviert. Wenn die fachliche Zuordnung fehlt, wird nach Kontakt/Thema gefragt.

Dieser organisationsweite Verzeichniszugriff mit bereichsbezogenen Suchaufrufen ist ausschließlich für den angemeldeten Team-Testzugang. Kandidaten bekommen vor verifizierter Telefonnummer/E-Mail und serverseitiger Kontaktzuordnung keine Akten aus anderen Gesprächen. Es wird keine contact_-ID geraten oder automatisch ein vorhandener Kandidat zusammengeführt. Persönliches Kandidatengedächtnis ist bis zur bestätigten Mapping-Regel nicht aktiviert. Kurze Team-Notizen können nach Browserfreigabe gespeichert werden; keine vollständigen Bewerbungsunterlagen oder Audioaufnahmen.

## Chatwoot-Kandidatenfluss
Nur message_created, Account und Inbox12, incoming, private=false. Die signierte Nachricht wird nur mit IDs in PostgreSQL eingereiht; der Worker holt den aktuellen Inhalt über Chatwoots API. So können Inhalte im Webhook keine Tools/Prompts überschreiben und das kurze5s-Zeitlimit blockiert die Verarbeitung nicht. Anhänge werden nicht heruntergeladen. Der Worker prüft die Inbox und pending-Status erneut vor dem Schreiben. Bei neueren eingegangenen Nachrichten wird eine alte Auslieferung nicht verspätet beantwortet.

Die erste freigegebene Aufnahme ist absichtlich regelbasiert: CV, Beruf und Deutschniveau anfragen; Anhänge nur als eingegangen bestätigen. Fragen zu Gehalt, Unterkunft, Gebühren, Visa, verbindlichen Fristen, Rechtsfragen oder unklare Anliegen gehen an Menschen. Keine Beträge/Zusagen oder Prozentbewertungen. B/H/S mit Ijekavica, Deutsch und Englisch anhand der Nachricht; die automatische Sprachwahl ist eine einfache Heuristik und noch keine geprüfte Sprachidentifikation.

Bei Übergabe wird eine dauerhafte Pause gespeichert und die Konversation auf open gesetzt. Lena schweigt danach. Zum Fortsetzen muss das Team die Konversation in Chatwoot auf pending setzen und im angemeldeten Lena-Browser die Konversations-ID mit „Lena nach Übergabe freigeben“ bestätigen. Alte Status-Webhooks heben die Pause niemals auf.

Doppelte Nachrichten-IDs werden dauerhaft dedupliziert. Ein mehrdeutiger Schreibfehler wird nicht automatisch erneut gesendet. Solche Fälle werden pausiert, nach Möglichkeit auf open gestellt und als needs_review sichtbar. Nach Prozessverlust werden processing-Jobs frühestens nach300s zur menschlichen Prüfung gegeben; neue Nachrichten desselben Gesprächs bleiben bei ungelösten Vorgängen blockiert. Bei Stoppen während einer Anfrage wird eine Pause gespeichert. PostgreSQL und die Queue müssen in Backups/Betriebsüberwachung aufgenommen werden. Normale Bereitstellung: eine Instanz. Skalierung benötigt eine gesonderte Abnahme des Mehrprozessverhaltens.

## Tools und Rechte
- Supermemory: alle vorhandenen Kontexte nur für Team zugänglich; bereichsbezogene Suche; kurze Notiz nach Zustimmung.
- Chatwoot: Gespräch in Inbox12 lesen; ausschließlich private Team-Notiz nach Zustimmung. Externe Kandidatenantworten nur im kontrollierten Inbox-Worker.
- Linear: projektgebundene Liste, neues Issue, Kommentar. Team/Projekt fest aus Serverkonfiguration; keine frei wählbaren Projekte. Kommentar nur nach erneutem Nachweis des Issue-Projekts. Keine Statusänderung, Zuweisung, Aktualisierung oder Löschung exponiert. Toolverfügbarkeit wird per MCP ermittelt; nicht unterstützte Tools/Antwortformen schlagen geschlossen fehl.
- Schreiben: konkrete Argumente im Browser vorlegen,90s Freigabefrist. Ablehnung, Ablauf, Zurücksetzen und Schließen verhindern den noch nicht abgesandten Zugriff. Bereits gesendete Anfragen können nicht zurückgenommen werden.
- MySQL/ClickUp, E-Mail, Viber und Telefonie sind in dieser Änderung nicht verbunden. Keine solche Fähigkeit behaupten.

Projektprüfung im Gateway schützt nur diesen Dienst. Um fremden Codex-Agenten Schreibzugriffe auf das Linear-Projekt technisch zu verwehren, braucht es eine getrennte Dienstidentität beziehungsweise einen Gateway, den alle diese Agenten zwingend verwenden. Ein gemeinsamer persönlicher Workspace-Token isoliert Projekte nicht.

## Prüfung und Betriebsabnahme
Lokale Tests decken Auth/Origin, Signaturen und Zeitfenster, Inboxgrenzen auch in Fehlerbehandlung, kanonische Daten statt Webhooktext, Deduplizierung, Queue-Wiederanlauf, Abbruch, veraltete Freigaben, fehlende Linear-Konfiguration sowie Inhaltsausschluss in Auditdaten ab. JavaScript-Syntax separat prüfen. Das sind Mock-/lokale Tests, keine Behauptung erfolgreicher Telefonie oder Linear-OAuth.

Vor echten Kandidaten: synthetischer Testkontakt in Inbox12, Intake-Antwort, Gehaltsfrage → open + Schweigen, bewusstes Fortsetzen, Anhang-Eingangsbestätigung; Browser-Audio und Toolfreigabe mit Testdaten. Freigegebenes FAQ mit aktueller Quelle und Verantwortlichem ist weiterhin nötig. Keine automatischen Versprechen aus ungeprüften alten Chatdaten.

## Noch benötigte Angaben
1. Linear: technischer Laufzeitzugang/OAuth für den MCP und bestätigtes Kandidaten-Zielprojekt plus Team-ID. Entwicklungsprojekt nicht automatisch für Kandidaten verwenden.
2. Telefonie: Anbieter und Rufnummer/SIP-Zugang, Zuordnung zu Inbox12 oder eigener später freigegebener Telefon-Inbox, gewünschter Inbound/Outbound-Ablauf. WebRTC allein ist kein Telefon; Chatwoot allein ersetzt keinen Telefonieanbieter.
3. Identität: verlässliche Zuordnung Telefonnummer/E-Mail ↔ Kandidaten-ID ↔ bestehende Supermemory-Daten ↔ MySQL/ClickUp. MySQL-MCP-Ziel und Rollen erst im nächsten freigegebenen Schritt.
4. Betrieb: Übergabeteam, Arbeitszeiten/Zeitzone, freigegebene FAQ, Aufbewahrung/Löschung und dedizierte technische Zugänge.
5. Später: Mail-/Viber-Zugang sowie optional externer Tracing-Anbieter, Projekt und Aufbewahrung. Diese Zugänge nicht hier ins Chatfenster schreiben.

## Rücknahme und Übergabe
Bei Störung zuerst CHATWOOT_WEBHOOK_ENABLED=false setzen und deployen; betroffene Konversationen menschlich übernehmen. Vorherige Bot2-Konfiguration ist lokal privat gesichert und darf nicht ins Repository. Vorherigen Render-Deploy nur zurückrollen, wenn die geänderte Bot-Zieladresse mit berücksichtigt wird. Datenbanktabellen werden bei Rollback nicht gelöscht.

Einrichtung, Testnachweise und offene Punkte im Projekt-Outputbericht beziehungsweise in den Entwicklungstickets halten; keine Kandidatendaten in Linear-Entwicklungstickets übernehmen.
