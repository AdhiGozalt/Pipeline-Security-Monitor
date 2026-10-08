// GET /api/config — konfigurasi publik untuk dashboard (anon key memang publik, dilindungi RLS).
import { readFileSync } from 'node:fs';

const model = JSON.parse(readFileSync(new URL('./model.json', import.meta.url), 'utf8'));

export default function handler(req, res) {
  res.status(200).json({
    supabaseUrl: process.env.SUPABASE_URL || '',
    supabaseAnonKey: process.env.SUPABASE_ANON_KEY || '',
    telegram: Boolean(process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID),
    hmac: Boolean(process.env.HMAC_SECRET),
    features: model.features,
    example: model.scaler.mean.map((m, i) => +(m + model.scaler.scale[i]).toFixed(2)),
  });
}
