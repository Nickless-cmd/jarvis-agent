# Jarvis — Lokal AI-assistent

## UI routes
- `/` → redirect til `/login`
- `/login` → login/register
- `/app` → chat UI
- `/admin` → admin panel (kun admin)
- `/docs` → dokumentation (funktioner og kommandoer)
- `/tickets` → support/tickets (bruger)

## Funktioner
- Web‑søgning, nyheder, vejr, valuta
- Systeminfo, ping og proces‑oversigt
- Noter og påmindelser
- CV og tekst‑generering med download‑link
- Ticket‑system med status og svar (bruger + admin)
- **Billedanalyse med hallucination-beskyttelse**
- Cookie‑samtykke for sprog/tidszone/by
- Topbanner med drift‑beskeder
- Logning med rotation og admin‑visning

## Demo‑bruger
- Brugernavn: `demo`
- Email: `demo@example.com`
- Password: `demo`

## Admin‑kommandoer (chat)
- `/banner <tekst>` → opdater topbanner
- `/banner clear` → ryd topbanner
- `/system-prompt` → opdater system‑prompt fra `personality.py`
- `/opret bruger ...` → opret bruger (kun admin)
  Eksempel:
  ```
  /opret bruger
  brugernavn: test
  email: test@example.com
  password: test123
  navn: Test Bruger
  by: Svendborg
  admin: nej
  ```

## Noter & påmindelser
- Opret note: `note: ...`
- Vis noter: `vis noter`
- Slet note: `slet note 3`
- Påmindelse: `mind mig om ... i morgen kl 10:00`
- Vis påmindelser: `vis påmindelser`
- CV: `hjælp mig med et CV`, `gem docx`, `gem permanent`
- Historie: `skriv en historie om ...`, `vis tekst`

## Langtids-hukommelse
Jarvis husker automatisk høj-signals bruger-facts og kontekst på tværs af sessioner. Hukommelsen er privat per bruger og redigerer automatisk følsomme data.

### Automatisk hukommelse
- **Præferencer**: "Jeg kan godt lide kaffe" → huskes som præference
- **Projekt-kontekst**: Arbejds-relaterede samtaler → huskes som projekt-info
- **Identitet (let)**: Grundlæggende info som navn → huskes som identity-lite
- **TODOs**: Påmindelser og opgaver → huskes som todo

### Manuel kontrol
- `husk dette: <tekst>` → gem tekst i hukommelse
- `glem det` → slet specifik hukommelse (interaktiv)
- `vis hvad du husker om mig` → se gemt hukommelse
- `ryd hukommelse` → slet al hukommelse for brugeren

### Regler
- Kun høj-signals indhold gemmes (min. 50 tegn svar)
- Følsomme data (API-nøgler, passwords, emails) redigeres automatisk
- Hukommelse søges når relevant (personlige spørgsmål, kontekst-afhængige)
- Maks 4-8 relevante minder pr. samtale
- Stil: `skriv en stil om ...`, `vis tekst`
- Tickets: `opret ticket ...`

## 🖼️ **Billedanalyse med Hallucination-beskyttelse**

Jarvis understøtter billedanalyse med avancerede sikkerhedsfunktioner mod hallucinationer.

### Billed-upload og -analyse
- Upload billeder via chat: `analyser billede.png`
- Upload via web-UI: Drag & drop i chat
- Understøttede formater: PNG, JPG, JPEG, GIF, SVG

### Vision-modeller
- **moondream:1.8b** (standard, let og hurtig)
- **llava:7b** (god balance)
- **llava:13b** (bedste kvalitet)

### Hallucination-beskyttelse
Jarvis har flere lag af beskyttelse mod usikre AI-svar:

#### **1. Streng Prompt**
```
BESKRIV KUN DET DU KAN SE DIREKTE PÅ BILLEDET.
INGEN GÆT, INGEN FORMODNINGER, INGEN STEDNAVNE, INGEN PERSONER, INGEN AKTIVITETER.
Hvis du er usikker på noget, sig 'Jeg kan ikke se det klart'.
Vær kort og præcis.
```

#### **2. Sprog-detektion**
Blokere svar på andre sprog end dansk/engelsk:
- ❌ Norsk: "det er ikke et bilde"
- ❌ Svensk: "det är inte en bild"
- ❌ Tysk: "es ist kein bild"

#### **3. Undvigelses-detektion**
Blokere svar der undviger billedbeskrivelse:
- ❌ "det er ikke mulig"
- ❌ "kvalitetsproblem"
- ❌ "rett frem"

#### **4. Kritisk Indholds-filtering**
Blokere hallucinationer med:
- 🏙️ Stednavne (København, Danmark, Europa)
- 👥 Personer og sociale kontekster
- 🎭 Følelser og aktiviteter
- ⏰ Tidsrelaterede gæt

### Debug og Logning
Aktiver detaljeret logning:
```bash
JARVIS_DEBUG_IMAGE=1 python3 -c "
import sys
sys.path.insert(0, 'src')
from jarvis.agent import _describe_image_ollama
# Test kode...
"
```

### Eksempler på Sikre Svar
✅ **Godkendt**: "Der er et blåt rektangel i midten"
✅ **Godkendt**: "Billedet viser geometriske former"
❌ **Blokeret**: "det er ikke et bilde av noe klart"
❌ **Blokeret**: "scene med mennesker i en by"

### Fejlfinding
Hvis billedanalyse fejler:
1. **Opgrader Ollama**: `curl -fsSL https://ollama.ai/install.sh | sh`
2. **Tjek model**: `ollama pull moondream:1.8b`
3. **CPU fallback**: `OLLAMA_VISION_NUM_GPU=0`
4. **Debug logging**: `JARVIS_DEBUG_IMAGE=1`

### Teknisk Konfiguration
```bash
# .env konfiguration
OLLAMA_VISION_MODEL=moondream:1.8b
OLLAMA_VISION_NUM_GPU=1
OLLAMA_VISION_CTX=1024
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

## Filer
- Download‑links bliver automatisk slettet efter download.
- Brug “gem permanent”, hvis filen skal bevares.

## Cookie‑samtykke
Hvis brugeren accepterer cookies, gemmer UI sprog/tidszone/valgt by, så Jarvis kan:
- vise korrekt tid
- foreslå lokale vejrdata
- tilpasse bannerets tidsformat

## CV‑spørgsmål (typisk)
- Stilling + branche
- Arbejdstid og hensyn
- Erfaring og ansvarsområder
- Uddannelse og kurser
- Kompetencer og certifikater

## CV‑skabelon (overskrifter)
- Kontaktoplysninger
- Profil
- Erfaring
- Uddannelse
- Kompetencer
- Kurser/Certifikater
- Andet (sprog, kørekort, IT)

## CV‑eksempel (kort)
```
Navn Efternavn
Telefon · Email · By

Profil
Serviceminded pedel med fokus paa drift, vedligehold og sikkerhed paa skoler.

Erfaring
Pedelassistent, Kommune (2021-2024)
- Daglig vedligehold og smareparationer
- Kontakt med laerere og teknisk support

Uddannelse
AMU-kurser i forstehjaelp og arbejdsmiljo

Kompetencer
- Handvaerk og praktisk fejlfinding
- Service og dialog med brugere

Andet
Korekort B · Dansk/Engelsk
```

## CV‑eksempel (generisk)
```
Navn Efternavn
Telefon · Email · By

Profil
Paalidelig medarbejder med fokus paa kvalitet, samarbejde og kundeservice.

Erfaring
Medarbejder, Virksomhed (2020-2024)
- Koordinerede daglige opgaver og prioriterede tid
- Loste praktiske udfordringer og forbedrede flow

Uddannelse
Relevante kurser og intern oplaering

Kompetencer
- Planlaegning og struktur
- Service og kommunikation

Andet
Korekort B · Dansk/Engelsk
```

## Historie‑skabelon (kort)
```
Titel

Indledning
Kort praesentation af hovedpersonen og situationen.

Konflikt
Det problem eller den udfordring, historien drejer sig om.

Vendepunkt
Noget sker, som aendrer situationen.

Afslutning
Konsekvens og afrunding.
```

## Stil‑opbygning (kort)
- Indledning: Praesenter emnet og vinklen
- Hoveddel: Argumenter og fakta i 2-3 afsnit
- Afslutning: Konklusion og perspektiv

## Stil‑eksempel (kort)
```
Emne: Genbrug i hverdagen

Genbrug handler ikke kun om affald, men om vaner. Naar vi sorterer, laerer vi at se
vaerdi i det, vi ellers ville smide ud. Det giver mindre spild og mere omtanke.

Samtidig er det let at goere rigtigt: en lille indsats i hjemmet kan spare store
ressourcer i samfundet. Det kraever kun klare rammer og lidt tillaerning.

Derfor boer genbrug vaere en fast del af hverdagen. Det er en simpel vane med en
stor effekt.
```

## HTTPS (Caddy)
Brug Caddy som lokal reverse-proxy for HTTPS.

### Install (Ubuntu)
```bash
sudo apt install -y caddy
```

### Kør
```bash
uvicorn jarvis.server:app --host 127.0.0.1 --port 8000
caddy run --config Caddyfile
```

Åbn: `https://localhost:8443`

### Trust lokal CA (kun første gang)
```bash
sudo caddy trust
```

## Embeddings (offline-first)
Som standard bruger Jarvis Ollama til embeddings (ingen HuggingFace download ved startup).

### Første gang
```bash
ollama pull nomic-embed-text
```

### Miljøvariabler
```
EMBEDDINGS_BACKEND=ollama
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_EMBED_URL=http://127.0.0.1:11434/api/embeddings
```

## Database (skrivbar)
Som standard bruges `data/jarvis.db`. Du kan overstyre placering:
```
JARVIS_DB_PATH=/tmp/jarvis.db
# eller
JARVIS_DATA_DIR=/tmp/jarvis_data
```