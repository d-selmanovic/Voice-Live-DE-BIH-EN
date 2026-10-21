# ADR0001: Direkte Connectoren und begrenzte Kandidatenaufnahme

Status: umgesetzt, externe Abnahme teilweise offen. Datum21.10.2026.

Kontext: Bestehender Live-Responses-Voice-Agent auf Render; schnell prüfbare Integration von Supermemory, Chatwoot und Linear ohne Composio. Kandidatenakten und Teamzugriff haben unterschiedliche Vertrauensgrenzen.

Entscheidung: vorhandenen Delegationspfad behalten; direkte HTTP-Adapter für Supermemory/Chatwoot, projektbeschränkter MCP-Client für Linear. Browser ist Team-Testzugang. Kandidaten-Webhook verarbeitet ausschließlich Inbox12; dauerhafte Queue mit IDs vor Ack, kanonische Daten aus Chatwoot, keine fremden URL-Downloads. Menschenübergabe pausiert dauerhaft; Rückgabe nur explizit authentisiert. Alle Team-Schreibaktionen erfordern Freigabe unmittelbar vor dem noch nicht abgesandten Zugriff. Technische Traces ohne Gesprächsinhalte.

Supermemory: alle9275 vorhandenen Bereiche dynamisch ermitteln; kein fester fachlicher Namespace. Aktuelle v5-Suche mit dynamischer Kontextwahl aus allen vorhandenen Bereichen; v3 ohne Tags erreichte keine vorhandenen Daten und eine einzelne Suchabfrage mit9275 Tags lieferte503. Deshalb keine globale Suchvollständigkeit behaupten und kein kostspieliges93-Abfragen-Fanout stillschweigend aktivieren. Fehlende Vollständigkeit nicht als leeres Ergebnis maskieren. Globale Suche ausschließlich Team; Kandidatenzuordnung bleibt vor persönlichem Gedächtnis erforderlich.

Folgen: schneller inkrementeller Ausbau, keine zweite Agentenschleife nötig. Kontextzuordnung, Suchlatenz, persönlicher Chatwoot-Token und bisher ungetestete Linear-OAuth müssen vor echtem Betrieb nachgeprüft beziehungsweise ersetzt werden. Keine Telefonie- oder Mandantenisolation durch reines Deployen. PostgreSQL ist für den produktiven Eingang erforderlich.

Alternativen: Hosted-MCP direkt im Modell würde globale Tools und schwer kontrollierbare Schreiboperationen exponieren. Eine zusätzliche komplette SDK-Neuimplementierung würde den vorhandenen Sprachpfad unnötig ersetzen. Volle generative Chatantworten ohne freigegebene FAQ/Identitätsmapping wurden für diese Testfreigabe nicht aktiviert.
