# Lena: Connectoren und kontrollierter Kandidatentest

## Ziel und Umfang
Lena im bestehenden Render-Service betreiben. Direkte Supermemory-API, Chatwoot-API plus Bot-Webhook ausschließlich Inbox 12, Linear über eingeschränkten Backend-MCP-Client, technische Traces ohne Inhalte. Keine geheimen Werte im Repository. Kein echter Telefonanruf und kein CRM-Schreibzugriff in dieser Änderung.

## Bindende Entscheidungen
- Browser ist passwortgeschützter Team-Testzugang, kein öffentlicher Kandidatenchat.
- Supermemory ohne festen Namespacefilter; globale Suche nur im Team-Testzugang. Kandidatenakten erst nach belastbarer Identitätszuordnung. Keine automatisch erfundene contact_-Zuordnung.
- Chatwoot nur Inbox 12. Inbound-Text: kontrollierte Aufnahme mit festen Antworten; Dokumente bestätigen und an Menschen geben. Kein Herunterladen fremder URLs. Bei Übergabe Status open, Bot schweigt; Mensch setzt pending und gibt im angemeldeten Browser bewusst frei.
- Webhook mit zufälligem Pfadtoken (AgentBot) und optional HMAC; frische kanonische Nachrichtenprüfung per API. Kein Kontowebhook für andere Inboxes.
- Dauerhaftes Deduplizieren vor Seiteneffekten; mehrdeutige Fehler nicht automatisch wiederholen. PostgreSQL verwenden, falls DATABASE_URL vorhanden; Render ohne dauerhaften Speicher aktiviert den Eingang nicht.
- Linear-Ziel muss ausdrücklich konfiguriert sein. Lesen, Anlegen, Kommentieren; Projekt und Team werden serverseitig fixiert. Änderungen, Löschen, Zuweisen nicht exponiert. Schreiben erst nach Browserfreigabe.
- Telefonie benötigt weiterhin einen echten Telefonieanbieter/Telefonnummer; WebRTC ist kein Telefonanschluss.

## Aufgaben / Nachweis
1. Connector-Verträge, Validierung, technische Traces, Supermemory global/kontextgebunden und Chatwoot-Scope: zunächst fehlschlagende Tests, dann Umsetzung.
2. Linear-MCP-Gateway und Freigaben; keine unbekannten Tools exponieren. Tests auf Scope, fehlende Credentials, verbotene Optionen.
3. Chatwoot-Bot-Eingang, Authentisierung, Replay-Schutz, Übergabe und Prozessausfälle: Tests vor Implementierung; gleiche feste Kandidatenregeln für Voice.
4. Voice-Anbindung, Statusanzeige und lokale Traces ohne Transkriptpersistenz; Regression der bestehenden Sprach-/Bewertungsfunktionen.
5. Frische Gesamtprüfung und unabhängiger Review; atomarer GitHub-Push, private Render-Umgebung ergänzen, Deployment und Health prüfen. Nur Inbox 12 verbinden. Synthetischer Test, keine echten Bewerber kontaktieren.
6. Einrichtung, tatsächliche Prüfevidenz und fehlende Angaben dokumentieren. Nichts als einsatzbereit darstellen, das nicht live geprüft ist.

## Ausführungsprotokoll
- Ausgang: b262bcb6dc229c31bf3a8cd87122f2fcdc3fc522; Render noch fba6401a. GitHub-Snapshot lokal unter work/lena.
- Zugangstest: Chatwoot-Profil erfolgreich; funktionierenden vorhandenen Token privat übernommen. Inbox 12 freigegeben. Supermemory GET /namespaces zuvor 200. Linear-Laufzeitdaten fehlen.
- Ruling: Keine neue Plattform/Agent-SDK-Umschreibung des vorhandenen Live-Responses-Backends — vorhandenen offiziellen Delegationsweg nutzen; reduziert Deploymentänderungen.

- Connector-/Webhook-Tests zunächst wegen fehlender Implementierung rot, anschließend grün; Erweiterung um Schutztests für Signaturen, IDs, Freigaben, Deduplizierung, Übergabe und Queue.
- Ruling: Supermemory v5 benötigt je Suche einen Namespace. Für ausdrücklich gewünschte globale Teamsuche wird der erreichbare v3-Kompatibilitätsendpunkt ohne containerTags genutzt; Kandidaten erhalten dieses Tool nicht. Verifiziert: POST /v3/search HTTP200. Keine fixe Namespace-Konfiguration.
- Unabhängiger Review: vier Befunde behoben (Teilchunk-JSON, Status-Callback-Replay, Freigaberennen nach async Vorprüfung, Übergabe bei unklarem Nachrichten-POST). Tests ergänzt.
- Ruling: Signierter AgentBot-Webhook von Bot2 statt kontoweitem Webhook; offizieller Chatwoot-Quellcode bestätigt HMAC-SHA256(timestamp.raw) und kurzes5s-Timeout. Queue speichert ausschließlich IDs, keine Texte/Dateien.
- Ruling: Verarbeitungseinträge bei Prozessverlust frühestens nach300s in needs_review; keine automatische Nachrichtenwiederholung. Abstand schützt überlappende Render-Deployments.
- Laufzeit-Chatwoot: vorhandener Bot2-Token liefert401. Persönlicher vorhandener CLI-Zugang funktioniert; benötigt später einen dedizierten eingeschränkten technischen Benutzer. Keine Berechtigungsisolierung als bereits umgesetzt behaupten.
- Postgres-SQL-Style-Skill an katalogisierten lokalen Skill-Pfaden nicht gefunden. Einfache neue Tabellen ausschließlich parameterisiert, keine destruktiven Migrationen.

- Korrektur aufgrund Live-Evidenz: HTTP200 des v3-Defaults war kein Beleg für organisationsweite Suche (0 Treffer, v5 hat Daten). Namespace-Listing bestätigt9275. Multi-Tag-Suche mit100 Tags funktioniert, mit9275 Tags503. Finaler Ruling: v5-Suche mit dynamischem Kontextverzeichnis, alle bestehenden Bereiche zugänglich ohne festen Filter; keine organisationsweite Vollständigkeit pro Suchantwort behaupten. Kein teures93-Suchaufrufe-Fanout pro Voice-Frage. Diese Grenze ist in Prompt und Einrichtung dokumentiert.
- Zwei weitere Review-Funde mit roten/grünen Tests behoben: Scope erneut vor Fehler-Übergabe prüfen; Cancellation persistiert Pause und ungelöste Queue-Einträge blockieren neue Nachrichten. Explizite menschliche Freigabe quittiert geprüfte Fehlerfälle; laufende Verarbeitung nicht freigebbar.
- Aktuell40 lokale Tests bestanden; Browser-JavaScript Syntaxprüfung bestanden. Echte Telefonie und Linear-Laufzeit-OAuth nicht geprüft.
