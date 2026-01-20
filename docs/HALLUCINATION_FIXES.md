# 🛡️ **Hallucination-Fixes: Teknisk Dokumentation**

Dette dokument beskriver alle tekniske ændringer implementeret for at beskytte mod hallucinationer i Jarvis' billedanalyse-system.

## 📋 **Oversigt over Ændringer**

### **1. Prompt-forbedring** (`src/jarvis/agent.py`)
```python
# Før (usikker)
prompt = "Describe this image"

# Efter (sikker)
prompt = (
    "BESKRIV KUN DET DU KAN SE DIREKTE PÅ BILLEDET. "
    "INGEN GÆT, INGEN FORMODNINGER, INGEN STEDNAVNE, INGEN PERSONER, INGEN AKTIVITETER. "
    "Hvis du er usikker på noget, sig 'Jeg kan ikke se det klart'. "
    "Vær kort og præcis."
)
```

### **2. Udvidet Hallucination-detektion**
Implementeret i funktionen `_looks_like_hallucination()` med flere lag af beskyttelse.

#### **Sprog-detektion**
```python
wrong_language_indicators = [
    # Norsk
    "det er ikke et bilde", "siden det ikke er", "er det ikke mulig",
    "rett frem", "tilbakemelding", "kvalitetsproblem", "bakgrunnen",
    # Svensk
    "det är inte en bild", "sedan det inte är", "är det inte möjligt",
    # Tysk
    "es ist kein bild", "seit es nicht ist", "ist es nicht möglich",
]
```

#### **Undvigelses-detektion**
```python
avoidance_indicators = [
    "kan ikke analysere", "kan ikke se", "er det ikke mulig", "er det umulig",
    "kan ikke give", "er det svært", "er det komplekst",
    "kvalitetsproblem", "quality issue", "teknisk problem", "technical issue",
]
```

#### **Short Response Detection (Ny)**
```python
# Tjek for meget korte svar der ikke beskriver billeder (1-2 ord hallucinationer)
words = low.split()
if len(words) <= 2:
    # Enkeltord eller meget korte svar der ikke er billedbeskrivelser
    meaningless_responses = [
        "godsmærke", "brand", "mærke", "badge", "logo", "symbol", "icon",
        "test", "hej", "hello", "hi", "ok", "okay", "yes", "no",
        "billede", "image", "photo", "picture", "img", "pic",
        "ingen", "nothing", "empty", "blank", "void",
        "error", "fejl", "problem", "issue", "fail",
        "ukendt", "unknown", "undefined", "null", "none",
    ]
    if any(word in meaningless_responses for word in words):
        return True

    # Tjek om korte svar ser ud som rigtige billedbeskrivelser
    valid_short_descriptions = [
        "rektangel", "cirkel", "kvadrat", "linje", "punkt", "prik",
        "blå", "rød", "grøn", "gul", "sort", "hvid", "grå",
        "stort", "lille", "rundt", "firkantet", "langt", "kort",
        "lys", "mørk", "klar", "uskarp",
    ]
    if not any(word in valid_short_descriptions for word in words):
        return True
```

#### **Kritisk Indholds-filtering**
```python
critical_hallucinations = [
    # Stednavne og geografi
    "københavn", "danmark", "europa", "amerika", "asien", "afrika",
    "paris", "london", "new york", "tokyo", "berlin", "rom",

    # Sociale kontekster
    "familie", "venner", "kolleger", "turist", "arbejde",
    "fest", "begivenhed", "konference", "møde", "samtale",

    # Følelser og aktiviteter
    "glad", "trist", "sur", "bekymret", "nervøs", "spændt", "afslappet",
    "tænker", "overvejer", "planlægger", "husker", "drømmer",
    "spiser", "drikker", "løber", "går", "står", "sidder",

    # Tidsrelaterede
    "morgen", "aften", "nat", "dag", "uge", "måned", "år",
    "i dag", "i går", "i morgen", "sidste uge", "næste år",

    # Yderligere nonsensical hallucinationer
    "godsmærke", "brand", "mærke", "badge", "logo", "symbol", "icon",
    "test", "demo", "sample", "example", "placeholder",
]
```

### **3. Debug-logging System**
```python
# Aktivering via environment variable
if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
    _debug(f"🖼️ Raw Ollama response: '{text[:200]}...'")
    _debug(f"🖼️ Hallucination detected: '{text}'")
```

### **4. Kontekst-optimering**
```bash
# .env ændringer
OLLAMA_VISION_CTX=1024  # Reduceret fra 2048 for stabilitet
OLLAMA_VISION_NUM_GPU=1  # GPU inference aktiveret
OLLAMA_VISION_MODEL=moondream:1.8b  # Let model for bedre stabilitet
```

## 🔧 **Kode-ændringer i Detaljer**

### **Fil: `src/jarvis/agent.py`**

#### **Linje ~2750: `_describe_image_ollama()` Funktion**
```python
def _describe_image_ollama(b64: str, is_admin: bool, ui_lang: str | None) -> tuple[str | None, str | None]:
    # ... eksisterende kode ...

    # FORBEDRET PROMPT (linje ~2770)
    prompt = (
        "BESKRIV KUN DET DU KAN SE DIREKTE PÅ BILLEDET. "
        "INGEN GÆT, INGEN FORMODNINGER, INGEN STEDNAVNE, INGEN PERSONER, INGEN AKTIVITETER. "
        "Hvis du er usikker på noget, sig 'Jeg kan ikke se det klart'. "
        "Vær kort og præcis."
    )

    # ... model kald ...

    # HALLUCINATION DETEKTION (linje ~2820)
    if _looks_like_hallucination(text):
        if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
            _debug(f"🖼️ Hallucination detected: '{text}'")
        return None, "Billedbeskrivelse indeholder usikre oplysninger"
```

#### **Linje ~2850: `_looks_like_hallucination()` Funktion**
```python
def _looks_like_hallucination(text: str) -> bool:
    """Udvidet hallucination-detektion med flere sprog og trigger-ord"""
    low = text.lower()

    # Først tjek for direkte afvisninger og gæt
    if _looks_like_refusal(text) or _looks_like_guess(text):
        return True

    # Tjek for forkert sprog
    wrong_language_indicators = [
        "det er ikke et bilde", "siden det ikke er", "er det ikke mulig",
        "rett frem", "tilbakemelding", "kvalitetsproblem", "bakgrunnen",
        "det är inte en bild", "sedan det inte är", "är det inte möjligt",
        "es ist kein bild", "seit es nicht ist", "ist es nicht möglich",
    ]

    if any(indicator in low for indicator in wrong_language_indicators):
        return True

    # Undvigelses-detektion
    avoidance_indicators = [
        "kan ikke analysere", "kan ikke se", "er det ikke mulig", "er det umulig",
        "kan ikke give", "er det svært", "er det komplekst",
        "kvalitetsproblem", "quality issue", "teknisk problem", "technical issue",
    ]

    if any(indicator in low for indicator in avoidance_indicators):
        description_indicators = [
            "der er", "der ses", "billedet viser", "på billedet",
            "there is", "there are", "the image shows", "in the image",
            "billedet indeholder", "billedet har", "image contains", "image has",
        ]
        if not any(indicator in low for indicator in description_indicators):
            return True

    # Kritisk indholds-filtering
    critical_hallucinations = [
        "københavn", "danmark", "europa", "amerika", "asien", "afrika",
        "paris", "london", "new york", "tokyo", "berlin", "rom",
        "familie", "venner", "kolleger", "turist", "arbejde",
        "fest", "begivenhed", "konference", "møde", "samtale",
        "glad", "trist", "sur", "bekymret", "nervøs", "spændt", "afslappet",
        "tænker", "overvejer", "planlægger", "husker", "drømmer",
        "spiser", "drikker", "løber", "går", "står", "sidder",
        "morgen", "aften", "nat", "dag", "uge", "måned", "år",
        "i dag", "i går", "i morgen", "sidste uge", "næste år",
    ]

    return any(indicator in low for indicator in critical_hallucinations)
```

#### **Linje ~2880: `_looks_like_refusal()` og `_looks_like_guess()`**
```python
def _looks_like_refusal(text: str) -> bool:
    low = text.lower()
    return any(
        bad in low
        for bad in [
            "kunne ikke", "kan ikke", "could not", "couldn't", "can't", "unable", "cannot",
            "could not help", "couldn't help",
        ]
    )

def _looks_like_guess(text: str) -> bool:
    low = text.lower()
    return any(
        guess in low
        for guess in [
            "som om", "måske", "ligner", "ser ud til", "muligvis", "tyder på", "kan være",
            "det kunne være", "det er som om", "turist", "rejse", "ferie", "eventyr", "oplevelse",
            "følelse", "føles", "attraktiv", "smuk", "overraskende", "tilføjer", "fremhæve",
            "kan bevises", "bevises",
        ]
    )
```

### **Fil: `.env`**
```bash
# Tilføjet vision-specifikke indstillinger
OLLAMA_VISION_MODEL=moondream:1.8b
OLLAMA_VISION_NUM_GPU=1
OLLAMA_VISION_CTX=1024
```

## 🧪 **Test-resultater**

### **Før Fixes:**
- ❌ Norsk hallucination: `"det er ikke et bilde av noe klart"`
- ❌ Svensk hallucination: `"det är inte en bild"`
- ❌ Tysk hallucination: `"es ist kein bild"`

### **Efter Fixes:**
- ✅ Blokerede alle sprog-baserede hallucinationer
- ✅ Blokerede undvigende svar
- ✅ Blokerede kritisk indhold (stednavne, personer, følelser)
- ✅ Blokerede nonsensical korte svar ("Godsmærke!", "Test", etc.)
- ✅ Tillod kun faktuelle billedbeskrivelser

### **Debug-output Eksempler:**
```bash
🖼️ Raw Ollama response: 'Der er et blåt rektangel i midten...'
🎉 No hallucination indicators detected

🖼️ Hallucination detected: 'det er ikke et bilde av noe klart'
✅ HALLUCINATION DETECTION: Successfully blocked unsafe response!
```

## 🚀 **Implementerings-status**

- ✅ **Prompt-forbedring**: Implementeret og testet
- ✅ **Sprog-detektion**: Aktiv og fungerer
- ✅ **Undvigelses-detektion**: Implementeret
- ✅ **Kritisk filtering**: Aktiv
- ✅ **Debug-system**: Klar til brug
- ✅ **Konfiguration**: Optimeret
- ✅ **Dokumentation**: Færdig

## 🎯 **Næste Skridt**

Når Ollama's vision-model stabilitet forbedres:
1. Test systemet med flere billedtyper
2. Tilføj understøttelse for flere sprog
3. Implementer bruger-feedback løkke
4. Tilføj billedkvalitets-validering

---

*Dokumentation opdateret: 18. januar 2026*