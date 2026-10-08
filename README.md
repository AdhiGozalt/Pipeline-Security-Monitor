# Pipeline Security Monitor


Sistem monitoring keamanan database real-time: laporan ancaman dari Supabase dikirim lewat webhook bertanda tangan HMAC-SHA256, dianalisis paralel oleh 2 model AI (Random Forest + SVM) + NVIDIA NIM, dikirim sebagai alert Telegram, dan ditampilkan di dashboard yang di-deploy otomatis ke Vercel via GitHub Actions.

```
Supabase (INSERT) ─► Trigger pg_net + HMAC ─► /api/webhook (Node.js) ─► Telegram Bot
                                                     ▲
Dashboard (public/index.html) ── Realtime ◄── Supabase
          └── /api/proses_ai (FastAPI: RF ∥ SVM via asyncio.gather + NVIDIA NIM)
GitHub push main ─► GitHub Actions ─► Vercel (production)
```

## Struktur
| Path | Fungsi |
|---|---|
| `api/proses_ai.py` | FastAPI `GET /api/proses_ai?input=a,b,c,d,e&nim=1` — RF (0.3s) + SVM (0.5s) paralel, total ≈0.5s |
| `api/model.json` | Model RF & SVM hasil ekspor `scripts/export_models.py` (inferensi tanpa scikit-learn) |
| `api/webhook.js` | `POST /api/webhook` (ES Module) — validasi `x-signature` HMAC-SHA256 → Telegram |
| `api/config.js` | Konfigurasi publik untuk dashboard |
| `public/index.html` | Dashboard (dark glassmorphism, simulator HMAC Web Crypto, benchmark AI, realtime) |
| `supabase/setup.sql` | Tabel, RLS, realtime, Vault secret, trigger webhook |
| `.github/workflows/deploy.yml` | CI/CD auto-deploy saat push ke `main` |
| `Scraping_data.ipynb`, `Ai_model.ipynb`, `*.csv` | Tahap AI Data Collection |

## Environment variables
Vercel: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NVIDIA_API_KEY`, `HMAC_SECRET`
GitHub Secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`

Tidak ada kredensial di kode; lokal disimpan di `.env` (di-ignore).

## Uji webhook (3 skenario)
```bash
B='{"status":"Waspada","level":2,"pesan":"uji"}'
S=$(printf '%s' "$B" | openssl dgst -sha256 -hmac "$HMAC_SECRET" | awk '{print $2}')
curl -X POST $URL/api/webhook -H "x-signature: $S" -d "$B"            # 200 valid
curl -X POST $URL/api/webhook -H "x-signature: $S" -d '{"x":1}'       # 401 tampered
curl -X POST $URL/api/webhook -d "$B"                                  # 400 missing
```
