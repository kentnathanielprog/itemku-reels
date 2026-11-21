# Template Teks Video itemku (Hook → Pesan → Hype → CTA)

Durasi ideal 12–16 detik. Maks 3 baris per caption, ±22 huruf per baris, HURUF BESAR.

| Bagian | Waktu | Tugas | Contoh (berita MLBB) |
|---|---|---|---|
| 1. HOOK | 0–3 dtk | Bikin penasaran, JANJIKAN sesuatu (open loop) | MLBB BARU SAJA PECAHKAN REKOR DUNIA / TUNGGU ANGKANYA |
| 2. PESAN | 3–9 dtk | Fakta utama, 1–2 caption, satu ide per caption | DI ESPORTS AWARDS 2026 MLBB DINOBATKAN MOBILE GAME OF THE YEAR |
| 3. HYPE / GONG | 9–13 dtk | Bayar janji hook: angka, twist, reveal | 5,68 JUTA PENONTON PUNCAK DI M7, TURNAMEN ESPORTS MOBILE TERBESAR |
| 4. CTA | 2 dtk terakhir | Satu ajakan saja | FOLLOW ITEMKU UNTUK BERITA GAME |

## Rumus HOOK (pilih satu)
- Rekor/angka: "[GAME] BARU SAJA PECAHKAN REKOR / TUNGGU ANGKANYA"
- Pertanyaan: "KENAPA [HAL] BISA JADI VIRAL? / JAWABANNYA DI AKHIR"
- Kontras: "DULU DIREMEHKAN / SEKARANG JADI JUARA DUNIA"
- FOMO: "JANGAN TOP UP DULU / SEBELUM LIHAT INI"
- Kabar besar: "KABAR BESAR UNTUK PEMAIN [GAME]"
Aturan: hook TIDAK membocorkan gong. Sebut janji ("tunggu angkanya", "sampai akhir"), jangan jawabannya.

## Rumus PESAN
- Satu caption = satu fakta. Kalimat pendek, kata kerja aktif ("DINOBATKAN", "RILIS", "DIPANGKAS").
- Urut dari konteks → alasan penting. Jangan taruh angka terbesar di sini (simpan untuk gong).

## Rumus HYPE / GONG
- Angka terbesar / rekor / twist / tanggal rilis / hadiah.
- Pakai kata penutup kuat: "TERBESAR SEPANJANG MASA", "PERTAMA DALAM SEJARAH", "GRATIS".
- Beri jeda 3–3,5 dtk supaya terbaca dan terasa "dentuman".

## Trik supaya penonton nonton sampai akhir
1. Open loop di hook ("tunggu angkanya", "ini yang bikin heboh") lalu bayar di gong (jangan lebih awal dari 70% durasi).
2. Gong di 65–80% durasi, bukan di detik pertama. CTA singkat sesudahnya.
3. Ganti caption tiap 3 dtk (ritme) + efek masuk tiap ganti, supaya mata terus bergerak.
4. Hook dan akhir nyambung (video terasa berulang/loop), mis. hook "REKOR DUNIA" → gong "TERBESAR SEPANJANG MASA".
5. Visual berubah di tengah (ganti gambar/klip) agar tidak monoton.
6. Pasang suara/ musik punya drop tepat di momen gong.
7. Hindari sebut "follow" di awal; CTA hanya di 2 detik terakhir.
8. Tulis hanya fakta yang sudah dicek ke sumber; angka dan klaim harus ada di artikel.

## Pakai
```
cd /home/user/itemku-news/short
cp story_template.json story_baru.json   # isi hook / message / gong / cta
python3 story.py story_baru.json
```
Hasil: ../out/<out>/short.mp4. Timing dapat diubah di "timing".
