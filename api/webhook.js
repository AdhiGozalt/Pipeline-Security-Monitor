// POST /api/webhook — penerima laporan Supabase, validasi HMAC-SHA256 (header x-signature), lalu alert Telegram.
import crypto from 'node:crypto';

const readRaw = (req) =>
  new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (c) => (data += c));
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });

const safeEqual = (a, b) => {
  const x = Buffer.from(a, 'hex');
  const y = Buffer.from(b, 'hex');
  return x.length === y.length && crypto.timingSafeEqual(x, y);
};

async function sendTelegram(text) {
  const { TELEGRAM_BOT_TOKEN: token, TELEGRAM_CHAT_ID: chat } = process.env;
  if (!token || !chat) return { ok: false, reason: 'telegram env belum diset' };
  const r = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chat, text, parse_mode: 'HTML' }),
  });
  return { ok: r.ok };
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const raw = await readRaw(req);
  const signature = req.headers['x-signature'];
  if (!signature) return res.status(400).json({ error: 'Header x-signature tidak ada' });

  const expected = crypto.createHmac('sha256', process.env.HMAC_SECRET || '').update(raw).digest('hex');
  if (!/^[0-9a-f]+$/i.test(signature) || !safeEqual(signature, expected)) {
    return res.status(401).json({ error: 'Signature HMAC tidak valid' });
  }

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return res.status(400).json({ error: 'Body bukan JSON valid' });
  }
  // Format Supabase trigger: { type, table, record }; format simulator: { status, level, pesan }
  const rec = payload.record || payload;
  const status = rec.status || 'Tidak diketahui';
  const level = rec.level ?? '-';
  const pesan = rec.pesan || '-';
  const icon = /bahaya|intervensi|critical/i.test(status) ? '🚨' : '✅';

  const tg = await sendTelegram(
    `${icon} <b>LAPORAN SENTINEL SECURITY</b>\nStatus: <b>${status}</b>\nLevel: ${level}\nDetail: ${pesan}\n` +
      `Sumber: ${payload.table ? 'Supabase (' + payload.table + ')' : 'Simulator'}\nWaktu: ${new Date().toISOString()}\n\n🔐 Pesan terverifikasi HMAC-SHA256`
  );
  return res.status(200).json({ status: 'verified', telegram: tg.ok, diterima: { status, level, pesan } });
}
