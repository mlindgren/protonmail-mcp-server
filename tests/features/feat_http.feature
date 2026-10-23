Feature: Servern kan nås över HTTP med en API-nyckel
  Som användare av Perplexity, som bara kan ansluta till MCP-servrar via en URL,
  vill jag kunna köra servern över HTTP (Streamable HTTP) bakom Cloudflare Tunnel och Cloudflare Access
  eftersom Perplexity inte kan starta ett lokalt program — men brevlådan får aldrig
  bli nåbar utan nyckel, och stdio ska fortsätta vara standard för Claude.

  Scenario: Ett anrop utan API-nyckel nekas
    Given servern körs i HTTP-läge med en API-nyckel
    When en klient anropar /mcp utan nyckel
    Then ska svaret vara 401
    And ska svaret inte innehålla något från MCP-servern

  Scenario: Ett anrop med fel API-nyckel nekas
    Given servern körs i HTTP-läge med en API-nyckel
    When en klient anropar /mcp med fel nyckel
    Then ska svaret vara 401

  Scenario: Med rätt nyckel som Bearer ser klienten alla verktyg
    Given servern körs i HTTP-läge med en API-nyckel
    When en MCP-klient ansluter över HTTP med nyckeln som "Authorization: Bearer"
    Then ska klienten se 29 verktyg

  Scenario: Med rätt nyckel i X-API-Key ser klienten alla verktyg
    Given servern körs i HTTP-läge med en API-nyckel
    When en MCP-klient ansluter över HTTP med nyckeln i "X-API-Key"
    Then ska klienten se 29 verktyg

  Scenario: Det publika värdnamnet tillåts, ett okänt nekas
    Given servern körs i HTTP-läge med en API-nyckel och värdnamnet "protonmail-mcp.example.eu"
    When en MCP-klient ansluter över HTTP via "protonmail-mcp.example.eu" med nyckeln som "Authorization: Bearer"
    Then ska klienten se 29 verktyg
    When en klient anropar /mcp via "angripare.example" med rätt nyckel
    Then ska svaret inte vara 200

  Scenario: HTTP-läget startar inte utan API-nyckel
    Given ingen API-nyckel är satt
    When servern startas med "--http"
    Then ska den avsluta med ett fel som nämner "PROTONMAIL_HTTP_TOKEN"
    And ska ingen HTTP-server ha startats

  Scenario: En för kort API-nyckel vägras
    Given API-nyckeln är "kort"
    When servern startas med "--http"
    Then ska den avsluta med ett fel som nämner "minst 32 tecken"

  Scenario: HTTP-läget lyssnar bara på den här datorn som standard
    Given servern körs i HTTP-läge med en API-nyckel
    When servern startas med "--http"
    Then ska den lyssna på 127.0.0.1

  Scenario: Utan flagga körs stdio som förut
    When servern startas utan flaggor
    Then ska den köras över stdio
