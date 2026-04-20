# Reference 01 — Product Page Analysis

Framework completo per analizzare una pagina prodotto (Shopify o altro)
esistente e dire esattamente come riempire/riscrivere ogni sezione.

L'obiettivo è consegnare al dropshipper un **audit operativo**: cosa è
rotto, perché è rotto, e il testo esatto con cui sostituirlo.

---

## 1. STRUTTURA DI ANALISI

Ogni pagina prodotto va mappata sulle 12 sezioni che seguono. Per
OGNI sezione devi produrre 4 campi:

1. **Status attuale**: `Presente / Assente / Debole`
2. **Cosa c'è che non va** (max 2 righe, operativo)
3. **Come riscriverla** (testo esatto pronto da incollare, nella
   lingua del brand)
4. **Priorità fix**: `Alta / Media / Bassa` basata su impatto CVR

---

## 2. LE 12 SEZIONI DA CONTROLLARE

### 1. Titolo prodotto (hero / H1)
- Deve contenere: nome prodotto + keyword chiave + benefit o
  differenziatore in ≤10 parole.
- Errori comuni: nome del fornitore AliExpress ("Portable Mini
  Humidifier USB 2.0 Desktop"), solo il nome generico ("Crema viso"),
  tecnicismi ("ABS + Silicon 150ml").
- Formula vincente: `[Categoria] [Nome] — [Benefit principale]`
- Priorità fix: **sempre Alta** se assente o generico.

### 2. Sottotitolo / Value Proposition
- Una frase sotto il titolo che risponde a "perché questo, perché
  ora, perché questo brand".
- Errori comuni: assente, o frase di marketing vuota ("qualità
  premium").
- Formula vincente: `[Outcome specifico] in [timeframe] — [unique
  mechanism o reason to believe]`
- Priorità: Alta.

### 3. Hero image / video
- Non è copy puro, ma il copy sotto la hero deve riferirsi a ciò
  che la hero mostra. Se la hero è un packshot su sfondo bianco, il
  copy deve compensare con storytelling. Se la hero è lifestyle, il
  copy può essere più tecnico.
- Priorità: Media (è un problema visual, non copy).

### 4. Bullet benefici (3–5)
- Devono essere **benefit-first, non feature-first**.
- Formula: `[Benefit concreto] + [meccanismo breve] + [outcome emotivo]`.
- Errori comuni: feature dump ("100% cotone, 220gsm, lavabile a 30°"),
  benefit astratti ("ti sentirai meglio").
- Priorità: Alta.

### 5. Descrizione long-form (300–500 parole)
- Struttura obbligatoria:
  1. Hook / problema (50–80 parole)
  2. Soluzione + mechanism (80–120 parole)
  3. Benefit stack (100–150 parole)
  4. Proof (50–80 parole)
  5. CTA + garanzia (30–50 parole)
- Errori comuni: paragrafo unico generato da AI generica, mancanza
  di mechanism, zero proof.
- Priorità: Alta.

### 6. Trust badges / garanzie
- Copy breve, visibile sopra il CTA principale.
- Format: `[Icona] + [Testo 3–6 parole]`
- Esempi ottimi: "Spedizione gratuita in 48h", "30 giorni soddisfatti
  o rimborsati", "Pagamento sicuro SSL", "10.000+ clienti soddisfatti".
- Priorità: Media (impatto diretto su conversion, ma fix rapido).

### 7. Social proof (reviews, testimonial, UGC)
- Sezione reviews: minimo 20 review, distribuzione realistica
  (65% 5★, 25% 4★, 8% 3★, 2% 1–2★ gestite con risposta).
- UGC: minimo 3 foto clienti se disponibili.
- Errori comuni: review finte ovvie, tutte 5 stelle, tutte dello
  stesso mese, nomi stranieri su un brand italiano.
- Priorità: **Alta** — è il driver di CVR #1 dopo il prezzo.

### 8. FAQ
- 5–7 domande. Devono coprire:
  - Spedizione (tempi, costi, tracking)
  - Resi (procedura, costi)
  - Uso (come si usa, compatibilità, istruzioni)
  - Materiali / safety
  - 2 obiezioni specifiche del prodotto (es. "funziona anche su
    capelli ricci?", "è sicuro per bambini sotto i 3 anni?")
- Priorità: Media-Alta (raccoglie obiezioni pre-checkout).

### 9. Urgency / scarcity elements
- Tipi: stock countdown, timer offerta, "X persone stanno
  guardando", "Ultimo acquisto X minuti fa".
- Regola: **realismo**. Scarcity finta (countdown che riparte) è
  detectata dal 40% dei clienti e brucia il brand.
- Priorità: Media (incrementale su CVR, ma rischioso se finto).

### 10. CTA (Call to Action)
- Posizioni minime:
  - Sopra la piega (immediato)
  - Sotto i bullet benefici
  - Fine descrizione long-form
  - Sticky sul mobile (scrollando)
- Testo CTA: mai "Acquista ora" generico. Usare:
  - "Aggiungi al carrello — Spedizione gratis oggi"
  - "Prendi il mio [prodotto]"
  - "Voglio provarlo"
- Priorità: **Alta** (testare varianti = win facile).

### 11. Upsell / bundle
- Pre-checkout: "Compra 2, risparmia X%"; "Aggiungi [complementare]
  al 50%".
- Copy deve spiegare **perché l'upsell ha senso**, non solo mostrarlo.
- Priorità: Media (impatta AOV, non CVR).

### 12. Shipping / returns info
- Sezione breve, chiara, senza legalese nascosto.
- Deve rispondere: "quando arriva?" + "posso tornare indietro?" +
  "quanto costa?".
- Priorità: Media-Alta (rimuove frizione finale).

---

## 3. ORDINE LOGICO AIDA + SCHWARTZ

Quando riscrivi la pagina, segui l'ordine AIDA:

- **A**ttention → Titolo + hero
- **I**nterest → Subtitle + bullet benefici
- **D**esire → Long-form description + social proof + mechanism
- **A**ction → CTA + garanzia + urgency

Calibra il messaggio sull'**awareness level** (Schwartz):

- **Unaware**: il lettore non sa di avere il problema. Devi
  partire raccontando il problema, non il prodotto. Titolo =
  problema. Esempio: "Il motivo per cui ti svegli stanco non è il
  materasso."
- **Problem-aware**: sa del problema, non della soluzione. Titolo
  = identificazione del problema + promessa. Esempio: "Mal di
  schiena cronico? La causa è nella postura notturna."
- **Solution-aware**: sa che esiste una categoria di soluzioni.
  Titolo = perché LA TUA soluzione è diversa. Esempio: "I
  correttori posturali rigidi non funzionano. Ecco cosa funziona."
- **Product-aware**: conosce il tuo prodotto. Titolo = offerta +
  differenziatore + urgency. Esempio: "[Brand] Posture Pro —
  spedizione gratuita fino a domani."
- **Most-aware**: cliente esistente o che ha già provato simili.
  Titolo = nuova offerta, bundle, re-engagement.

**Regola pratica dropshipping**: per prodotti in cold-traffic
(Meta/TikTok) la pagina di destinazione deve trattare il lettore
come **problem-aware** o **solution-aware**. Mai come product-aware.

---

## 4. OUTPUT FORMAT DELL'ANALISI

Consegna sempre così:

```
## 📊 Audit Pagina Prodotto — [Nome prodotto dedotto]

**Diagnosi in 3 righe:** [cosa è rotto, cosa funziona, priorità #1]

---

### Sezione 1 — Titolo prodotto
- **Status:** Debole
- **Cosa non va:** "[titolo attuale]" è un dump di feature senza benefit.
- **Riscrittura:**
  - Variante A: "[testo]"
  - Variante B (contrarian): "[testo]"
- **Priorità fix:** Alta

[ripeti per tutte le 12 sezioni presenti o mancanti]

---

### 🎯 Piano d'azione (ordine di fix)
1. [Fix più alto impatto, eseguibile in 15min]
2. [Fix #2]
3. [Fix #3]
...

### Stima impatto CVR atteso
Baseline attuale stimata: [X%]. Post-fix realistico: [Y%]. Confidence:
[alta/media/bassa].
```

---

## 5. REGOLE QUALITÀ AUDIT

- Non dire mai "la pagina va bene". Anche le pagine buone hanno 3+
  fix da fare.
- Non elencare problemi senza fix. Ogni problema → testo sostitutivo
  pronto.
- Se mancano screenshot/link e l'utente chiede un audit, chiedi UNA
  volta il link/screenshot. Se non arriva, fai un audit generico sulla
  categoria prodotto dichiarata.
- Non inventare metriche ("il tuo CVR è 1.2%"). Usa stime qualitative
  giustificate.
