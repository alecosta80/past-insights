# Past Insights - pubblicazione automatica Facebook

Questo progetto pubblica ogni giorno sulla pagina Facebook **Past Insights** un post in inglese con 3 eventi storici globali accaduti nella stessa data.

Il principio importante e': **Wikipedia e' la fonte dei fatti; Gemini riscrive soltanto il testo**.

## File inclusi

- `post_past_insights.py`: legge gli eventi da Wikipedia in inglese, seleziona 3 eventi, li fa riscrivere da Gemini e pubblica su Facebook.
- `.github/workflows/daily.yml`: esegue lo script ogni mattina con GitHub Actions.
- `requirements.txt`: dipendenze Python.
- `.env.example`: esempio delle variabili da configurare.

## Come funziona

1. Lo script chiama Wikimedia On This Day per la data del giorno.
2. Tiene solo eventi con anno e testo utilizzabile.
3. Seleziona 3 eventi globali in modo stabile per quella data.
4. Passa a Gemini solo i dati verificati.
5. Controlla che Gemini non abbia rimosso o aggiunto anni non presenti negli eventi scelti.
6. Aggiunge le fonti Wikipedia in fondo al post.
7. Pubblica sulla pagina Facebook tramite Meta Graph API.

## Variabili richieste

Queste variabili vanno salvate come **GitHub Secrets**:

- `GEMINI_API_KEY`
- `FACEBOOK_PAGE_ID`
- `FACEBOOK_PAGE_ACCESS_TOKEN`
- `WIKIMEDIA_USER_AGENT`

Queste possono essere salvate come **GitHub Variables** oppure lasciate ai valori predefiniti:

- `GEMINI_MODEL`: predefinito `gemini-2.5-flash`
- `META_GRAPH_API_VERSION`: predefinito `v25.0`

## Ottenere la Gemini API key

1. Vai su [Google AI Studio](https://aistudio.google.com/).
2. Accedi con il tuo account Google.
3. Apri la sezione **API keys**.
4. Crea una nuova API key per Gemini.
5. Copia la chiave e salvala in GitHub Secrets come `GEMINI_API_KEY`.

Nota: Gemini API offre un free tier, ma limiti e disponibilita' possono cambiare. Per 1 post al giorno dovrebbe essere sufficiente.

## Ottenere Facebook Page ID e Page Access Token

Questa e' la parte piu' delicata, perche' Meta cambia spesso schermate e permessi.

1. Vai su [developers.facebook.com](https://developers.facebook.com/).
2. Crea una nuova app.
3. Aggiungi Facebook Login o il prodotto necessario per usare la Graph API.
4. Apri **Graph API Explorer**.
5. Seleziona la tua app.
6. Genera un User Access Token con permessi:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
7. Chiama l'endpoint:

```text
GET /me/accounts
```

8. Trova la pagina **Past Insights** nella risposta.
9. Copia:
   - `id`: questo e' `FACEBOOK_PAGE_ID`
   - `access_token`: questo e' il Page Access Token
10. Trasforma il token in un token long-lived usando gli strumenti Meta, come **Access Token Debugger** o il flusso OAuth long-lived token.
11. Verifica il token con:

```text
POST /{FACEBOOK_PAGE_ID}/feed
message=Test Past Insights
```

Se il post e' visibile solo a te o agli utenti collegati all'app, l'app potrebbe essere ancora in modalita' sviluppo o potrebbero servire permessi/app review.

## Inserire i token in GitHub

1. Apri il repository GitHub.
2. Vai in **Settings > Secrets and variables > Actions**.
3. In **Secrets**, aggiungi:
   - `GEMINI_API_KEY`
   - `FACEBOOK_PAGE_ID`
   - `FACEBOOK_PAGE_ACCESS_TOKEN`
   - `WIKIMEDIA_USER_AGENT`
4. In **Variables**, opzionalmente aggiungi:
   - `GEMINI_MODEL`
   - `META_GRAPH_API_VERSION`

## Test manuale su GitHub

1. Apri il repository su GitHub.
2. Vai in **Actions**.
3. Seleziona **Daily Past Insights post**.
4. Premi **Run workflow**.
5. Per il primo test imposta `dry_run` a `true`, cosi' non pubblica su Facebook.
6. Controlla i log.
7. Quando il risultato va bene, rilancia con `dry_run` a `false`.

## Test locale opzionale

Installa le dipendenze:

```bash
pip install -r requirements.txt
```

Imposta le variabili d'ambiente e prova senza pubblicare:

```bash
set DRY_RUN=true
python post_past_insights.py
```

Su macOS/Linux:

```bash
DRY_RUN=true python post_past_insights.py
```

## Orario

Il workflow gira ogni giorno alle `06:15 UTC`, cioe':

- `07:15` in Italia durante l'ora solare
- `08:15` in Italia durante l'ora legale

GitHub Actions puo' partire con qualche minuto di ritardo.
